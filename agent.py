"""
Agent
=====
The core Agent class that manages the customer processing workflow.

Handles:
- Agent state (IDLE, RUNNING, CALLING, STOPPING, STOPPED, COMPLETED, ERROR)
- Start/Stop controls
- Sequential processing of PENDING customers
- LLM conversation for interest classification (Groq / Gemini / Ollama)
- Customer replies arrive through submit_reply() (used by the web UI)
- Thread-safe stop mechanism
- Error handling: technical failures never falsely classify customers

Phase 2.4 - Flask web UI (replaces terminal input)
"""

import json
import queue
import time
import threading

from logger import log
from llm_provider import get_llm_provider, LLMFatalError
from prompts import TURN_SYSTEM_PROMPT, get_fixed_greeting, get_turn_prompt
from spreadsheet_manager import (
    load_spreadsheet,
    validate_spreadsheet,
    get_pending_customers,
    update_customer_status,
    save_spreadsheet,
)


# Agent states
STATE_IDLE = "IDLE"
STATE_RUNNING = "RUNNING"
STATE_CALLING = "CALLING"
STATE_PROCESSING = "PROCESSING RESULT"
STATE_STOPPING = "STOPPING"
STATE_STOPPED = "STOPPED"
STATE_COMPLETED = "COMPLETED"
STATE_ERROR = "ERROR"

# States in which the agent thread is still working
ACTIVE_STATES = (STATE_RUNNING, STATE_CALLING, STATE_PROCESSING, STATE_STOPPING)

# Conversation limits
MAX_REPLY_CHARS = 500         # longest customer reply accepted
REPLY_TIMEOUT_SECONDS = 300   # give up on a call if the customer never replies
MAX_TRANSCRIPT_LINES = 200    # keep the in-memory transcript bounded


class Agent:
    """
    AI Loan Customer Agent that processes PENDING customers.

    Usage:
        agent = Agent("loan_leads.xlsx")
        agent.start()              # Starts processing in a background thread
        agent.submit_reply("yes")  # Answer when get_status()["awaiting_reply"] is True
        agent.stop()               # No new call will start after this
    """

    def __init__(self, spreadsheet_path):
        """
        Initialize the Agent.

        Args:
            spreadsheet_path (str): Path to the loan_leads.xlsx file
        """
        self.spreadsheet_path = spreadsheet_path
        self.status = STATE_IDLE
        self.current_customer = None
        self.message = ""  # Short, generic message for the UI (errors, stop reason)
        self.summary = self._empty_summary()

        # Conversation state shown in the UI
        self.transcript = []  # list of {"role": "agent|customer|system", "text": str}
        self.awaiting_reply = False
        self._reply_queue = queue.Queue()
        self._pending_total = None  # PENDING customers found when the run started

        # LLM Provider
        self._llm = None
        self._llm_fatal_error = None  # Set when the LLM cannot work at all (bad key, daily quota)

        # Threading
        self._thread = None
        self._stop_event = threading.Event()  # Thread-safe stop signal
        self._lock = threading.Lock()  # Guards status, transcript and reply hand-off

    @staticmethod
    def _empty_summary():
        return {
            "total_processed": 0,
            "interested": 0,
            "not_interested": 0,
            "skipped": 0,
            "errors": 0,
        }

    @property
    def is_running(self):
        """Check if the agent is actively running (including while stopping)."""
        if self.status in ACTIVE_STATES:
            return True
        return self._thread is not None and self._thread.is_alive()

    def _set_status(self, status):
        """Set an active state, but never hide a pending Stop request."""
        with self._lock:
            if status in ACTIVE_STATES and self._stop_event.is_set():
                status = STATE_STOPPING
            self.status = status

    def _add_transcript(self, role, text):
        """Append one line to the conversation transcript."""
        with self._lock:
            self.transcript.append({"role": role, "text": text})
            self.transcript = self.transcript[-MAX_TRANSCRIPT_LINES:]

    def start(self):
        """
        Start the agent in a background thread.

        The agent will process PENDING customers sequentially until:
        - All PENDING customers are done, or
        - stop() is called

        Returns:
            bool: True if started, False if the agent is already running
        """
        with self._lock:
            if self.is_running:
                log.warning("Agent is already running!")
                return False

            # Reset state
            self._stop_event.clear()
            self._llm_fatal_error = None
            self.summary = self._empty_summary()
            self.current_customer = None
            self.message = ""
            self.transcript = []
            self.awaiting_reply = False
            self._pending_total = None
            self._drain_replies()
            self.status = STATE_RUNNING

            # Start processing in a background thread
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

        log.info("Agent started.")
        return True

    def stop(self):
        """
        Signal the agent to stop.

        No new customer call is started after this. A call that is waiting for the
        customer's reply is ended (the customer stays PENDING). A call whose LLM
        answer is already in flight finishes first.

        Returns:
            bool: True if a stop was requested, False if the agent was not running
        """
        with self._lock:
            if self.status not in ACTIVE_STATES:
                log.warning("Agent is not running.")
                return False
            self._stop_event.set()  # Signal the thread to stop
            self.status = STATE_STOPPING

        log.info("Stopping agent... (no new calls will be started)")
        return True

    def submit_reply(self, text):
        """
        Give the agent the customer's reply for the current call.

        Args:
            text (str): What the customer said

        Returns:
            tuple: (ok, error_message). error_message is None when ok is True.
        """
        text = text.strip() if isinstance(text, str) else ""
        if not text:
            return False, "Reply is empty."
        if len(text) > MAX_REPLY_CHARS:
            return False, f"Reply is too long (max {MAX_REPLY_CHARS} characters)."

        with self._lock:
            if not self.awaiting_reply:
                return False, "The agent is not waiting for a reply right now."
            self.awaiting_reply = False  # Accept exactly one reply per question
            self.transcript.append({"role": "customer", "text": text})
            self.transcript = self.transcript[-MAX_TRANSCRIPT_LINES:]
            self._reply_queue.put(text)
        return True, None

    def refresh_pending_count(self):
        """
        Count PENDING customers by reading the spreadsheet.

        Returns:
            int or None: The count, or None if the spreadsheet cannot be read
        """
        try:
            workbook = load_spreadsheet(self.spreadsheet_path)
            validate_spreadsheet(workbook)
            return len(get_pending_customers(workbook))
        except Exception:
            return None

    def get_status(self):
        """
        Snapshot of the agent for the UI.

        Returns:
            dict: status, current_customer, pending_count, awaiting_reply,
                  is_running, message, summary and transcript
        """
        running = self.is_running
        with self._lock:
            snapshot = {
                "status": self.status,
                "current_customer": self.current_customer,
                "awaiting_reply": self.awaiting_reply,
                "message": self.message,
                "summary": dict(self.summary),
                "transcript": list(self.transcript),
            }

        if not running:
            snapshot["pending_count"] = self.refresh_pending_count()
        elif self._pending_total is not None:
            remaining = self._pending_total - snapshot["summary"]["total_processed"]
            snapshot["pending_count"] = max(remaining, 0)
        else:
            snapshot["pending_count"] = None

        snapshot["is_running"] = running
        return snapshot

    def _drain_replies(self):
        """Discard any reply left over from an earlier call."""
        while True:
            try:
                self._reply_queue.get_nowait()
            except queue.Empty:
                return

    def _wait_for_reply(self):
        """
        Block until the customer's reply arrives.

        Returns:
            str or None: The reply, or None if Stop was pressed or the wait timed out
        """
        deadline = time.monotonic() + REPLY_TIMEOUT_SECONDS
        with self._lock:
            self.awaiting_reply = True
        try:
            while not self._stop_event.is_set():
                if time.monotonic() > deadline:
                    log.warning("  No reply received before the timeout.")
                    return None
                try:
                    return self._reply_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
            return None
        finally:
            with self._lock:
                self.awaiting_reply = False

    def _run(self):
        """
        Internal method that runs in the background thread.
        Handles the full processing workflow with error handling.
        """
        try:
            # Step 1: Initialize LLM (provider chosen by LLM_PROVIDER in .env)
            log.info("Initializing LLM provider...")
            try:
                self._llm = get_llm_provider()
            except ValueError as e:
                log.error(f"LLM initialization failed: {e}")
                self.message = "Could not start the AI service. Check the server log."
                self.status = STATE_ERROR
                return

            # Step 2: Load spreadsheet
            log.info("Loading spreadsheet...")
            workbook = self._load_and_validate()
            if workbook is None:
                return  # Error already logged, status already set

            # Step 3: Find pending customers
            pending = get_pending_customers(workbook)
            self._pending_total = len(pending)

            if not pending:
                log.info("No PENDING customers found. All done!")
                self.status = STATE_COMPLETED
                return

            log.info(f"Found {len(pending)} PENDING customers to process.")

            # Step 4: Process each customer
            for i, customer in enumerate(pending, 1):
                # Check if stop was requested BEFORE starting a new call
                if self._stop_event.is_set():
                    self.current_customer = None
                    if self._llm_fatal_error:
                        log.error(f"Stopped: {self._llm_fatal_error}. "
                                  "Remaining customers stay PENDING.")
                        self.message = ("The AI service is unavailable (check the API key or quota). "
                                        "Remaining customers stay PENDING.")
                        self.status = STATE_ERROR
                    else:
                        log.info("Stop requested. Not starting new calls.")
                        self.status = STATE_STOPPED
                    self._print_summary()
                    return

                # Process this customer with error handling
                self._process_single_customer(workbook, customer, i, len(pending))

            # All done
            self.current_customer = None
            if self._llm_fatal_error:
                log.error(f"Stopped: {self._llm_fatal_error}. "
                          "Remaining customers stay PENDING.")
                self.message = ("The AI service is unavailable (check the API key or quota). "
                                "Remaining customers stay PENDING.")
                self.status = STATE_ERROR
            elif self._stop_event.is_set():
                log.info("Stop requested. Not starting new calls.")
                self.status = STATE_STOPPED
            else:
                self.status = STATE_COMPLETED
            self._print_summary()

        except Exception as e:
            log.critical(f"Fatal error in agent: {e}")
            self.message = "Unexpected error. Check the server log."
            self.status = STATE_ERROR

    def _load_and_validate(self):
        """
        Load and validate the spreadsheet.

        Returns:
            Workbook or None: The workbook if successful, None if error
        """
        try:
            workbook = load_spreadsheet(self.spreadsheet_path)
        except FileNotFoundError:
            log.error(f"Spreadsheet not found: '{self.spreadsheet_path}'")
            log.error("Run 'python create_sample_data.py' to create it.")
            self.message = "Spreadsheet not found. Check the server log."
            self.status = STATE_ERROR
            return None
        except Exception as e:
            log.error(f"Could not open spreadsheet: {e}")
            self.message = "Could not open the spreadsheet. Check the server log."
            self.status = STATE_ERROR
            return None

        try:
            validate_spreadsheet(workbook)
            log.info(f"Spreadsheet loaded and validated: {self.spreadsheet_path}")
        except ValueError as e:
            log.error(f"Invalid spreadsheet format: {e}")
            self.message = "The spreadsheet format is invalid. Check the server log."
            self.status = STATE_ERROR
            return None

        return workbook

    def _process_single_customer(self, workbook, customer, index, total):
        """
        Process a single customer with full error handling.

        CRITICAL SAFETY RULE:
            If ANY error occurs during processing, the customer stays PENDING.
            A technical failure must NEVER mark a customer as NOT_INTERESTED.

        Args:
            workbook: The openpyxl Workbook object
            customer (dict): Customer data (name, phone, row_number)
            index (int): Current customer index (for display)
            total (int): Total customers to process (for display)
        """
        name = customer["name"]
        phone = customer["phone"]
        row = customer["row_number"]

        # Validate customer data before processing
        if not name or not str(name).strip():
            log.warning(f"Row {row}: Skipping - empty customer name.")
            self.summary["skipped"] += 1
            return

        if not phone or not str(phone).strip():
            log.warning(f"Row {row}: Skipping '{name}' - empty phone number.")
            self.summary["skipped"] += 1
            return

        # Update state
        self.current_customer = name
        self._set_status(STATE_CALLING)

        log.info(f"--- Customer {index}/{total} ---")
        log.info(f"  Name:  {name}")
        log.info(f"  Phone: {phone}")
        log.info(f"  Status: CALLING...")
        self._add_transcript("system", f"Calling {name}...")

        try:
            # Have a text conversation with the AI acting as bank agent
            result = self._conduct_conversation(customer)

            # Validate the result before updating spreadsheet
            if result not in ("INTERESTED", "NOT_INTERESTED"):
                log.warning(f"  Result '{result}' for {name}. Keeping PENDING.")
                self.summary["errors"] += 1
                self._add_transcript("system", f"Call ended without a clear result. {name} stays PENDING.")
                return

            # Update spreadsheet
            self._set_status(STATE_PROCESSING)
            update_customer_status(workbook, row, result)
            save_spreadsheet(workbook, self.spreadsheet_path)

            # Track counts
            self.summary["total_processed"] += 1
            if result == "INTERESTED":
                self.summary["interested"] += 1
                log.info(f"  Result: INTERESTED  [GREEN]")
            else:
                self.summary["not_interested"] += 1
                log.info(f"  Result: NOT_INTERESTED  [RED]")

            log.info(f"  Spreadsheet updated.")
            self._add_transcript("system", f"{name}: {result}. Spreadsheet updated.")

        except LLMFatalError as e:
            # LLM unusable (bad key / daily quota gone): customer stays PENDING, stop the run
            log.error(f"  LLM unavailable: {e}. '{name}' remains PENDING.")
            self._llm_fatal_error = f"LLM unavailable ({e})"
            self._stop_event.set()
            self._add_transcript("system", f"The AI service is unavailable. {name} stays PENDING.")

        except Exception as e:
            # SAFETY: On ANY error, customer stays PENDING
            log.error(f"  Error processing {name}: {e}")
            log.error(f"  Customer '{name}' remains PENDING (safe failure).")
            self.summary["errors"] += 1
            self._add_transcript("system", f"Something went wrong. {name} stays PENDING.")

        finally:
            self._set_status(STATE_RUNNING)

    def _conduct_conversation(self, customer):
        """
        Conduct a text-based conversation with the AI as the bank agent.
        The customer's replies arrive through submit_reply() (from the web UI).

        The conversation continues until the AI can determine interest.
        Maximum 10 turns to prevent infinite loops.

        Args:
            customer (dict): Customer info (name, phone, row_number)

        Returns:
            str: 'INTERESTED', 'NOT_INTERESTED', or 'UNCLEAR'
        """
        name = customer["name"]
        max_turns = 10

        # Conversation history for context
        conversation_history = []

        # Step 1: Fixed opening greeting (no LLM call, saves API quota)
        self._drain_replies()
        ai_greeting = get_fixed_greeting(name)
        self._add_transcript("agent", ai_greeting)
        conversation_history.append(f"AI: {ai_greeting}")

        # Step 2: Multi-turn conversation
        for turn in range(max_turns):
            # Wait for the customer's reply (None = Stop pressed or timed out)
            customer_input = self._wait_for_reply()
            if customer_input is None:
                log.warning("  No customer reply (stopped or timed out). Customer stays PENDING.")
                return "UNCLEAR"

            conversation_history.append(f"Customer: {customer_input}")

            # ONE LLM call returns both the reply and the classification
            raw_response = self._llm.chat(
                message=get_turn_prompt(conversation_history),
                system_instruction=TURN_SYSTEM_PROMPT,
                json_mode=True,
            )
            reply, result = self._parse_turn(raw_response)

            if reply is None:
                # Invalid AI response: show a safe generic line, keep the conversation going
                reply = "Sorry, could you please repeat that?"
            self._add_transcript("agent", reply)
            conversation_history.append(f"AI: {reply}")

            if result in ("INTERESTED", "NOT_INTERESTED"):
                return result

        # Max turns reached — couldn't determine
        log.warning(f"  Max conversation turns reached for {name}. Classifying as UNCLEAR.")
        return "UNCLEAR"

    def _parse_turn(self, raw_response):
        """
        Parse and validate the AI's JSON response for one turn.

        Expected format: {"reply": "...", "status": "INTERESTED"}
        The Python app validates this — the LLM never touches the spreadsheet.

        Args:
            raw_response (str): Raw text from the AI

        Returns:
            tuple: (reply or None, status) where status is
                   'INTERESTED', 'NOT_INTERESTED', or 'UNCLEAR'.
                   Any invalid response gives (None, 'UNCLEAR').
        """
        try:
            # Clean the response (remove markdown code blocks if present)
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                # Remove ```json ... ``` wrapping
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1])

            data = json.loads(cleaned)

            reply = str(data.get("reply", "")).strip() or None
            status = str(data.get("status", "")).strip().upper()

            if status not in ("INTERESTED", "NOT_INTERESTED", "UNCLEAR"):
                log.warning(f"  Unknown classification: '{status}'")
                return reply, "UNCLEAR"

            return reply, status

        except (json.JSONDecodeError, AttributeError):
            log.warning(f"  Could not parse AI response as JSON: {raw_response[:100]}")
            return None, "UNCLEAR"

    def _print_summary(self):
        """Print the processing summary."""
        log.info("=" * 46)
        log.info("   PROCESSING SUMMARY")
        log.info("=" * 46)
        log.info(f"  Total processed:  {self.summary['total_processed']}")
        log.info(f"  Interested:       {self.summary['interested']}")
        log.info(f"  Not Interested:   {self.summary['not_interested']}")
        log.info(f"  Skipped:          {self.summary['skipped']}")
        log.info(f"  Errors:           {self.summary['errors']}")
        log.info(f"  Agent Status:     {self.status}")
        log.info("=" * 46)
