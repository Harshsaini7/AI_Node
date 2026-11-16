"""
Agent
=====
The core Agent class that manages the customer processing workflow.

Handles:
- Agent state (IDLE, RUNNING, CALLING, STOPPING, STOPPED, COMPLETED, ERROR)
- Start/Stop controls
- Sequential processing of PENDING customers
- Gemini LLM conversation for interest classification
- Thread-safe stop mechanism
- Error handling: technical failures never falsely classify customers

Phase 3.3/3.4 - Gemini LLM with Text Conversation
"""

import json
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


class Agent:
    """
    AI Loan Customer Agent that processes PENDING customers.

    Usage:
        agent = Agent("loan_leads.xlsx")
        agent.start()   # Starts processing in a background thread
        agent.stop()    # Signals the agent to stop after current customer
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
        self.summary = {
            "total_processed": 0,
            "interested": 0,
            "not_interested": 0,
            "skipped": 0,
            "errors": 0,
        }

        # LLM Provider
        self._llm = None
        self._llm_fatal_error = None  # Set when the LLM cannot work at all (bad key, daily quota)

        # Threading
        self._thread = None
        self._stop_event = threading.Event()  # Thread-safe stop signal

    @property
    def is_running(self):
        """Check if the agent is actively running."""
        return self.status in (STATE_RUNNING, STATE_CALLING, STATE_PROCESSING)

    def start(self):
        """
        Start the agent in a background thread.

        The agent will process PENDING customers sequentially until:
        - All PENDING customers are done, or
        - stop() is called
        """
        if self.is_running:
            log.warning("Agent is already running!")
            return

        # Reset state
        self._stop_event.clear()
        self._llm_fatal_error = None
        self.summary = {
            "total_processed": 0,
            "interested": 0,
            "not_interested": 0,
            "skipped": 0,
            "errors": 0,
        }
        self.current_customer = None

        # Start processing in a background thread
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info("Agent started.")

    def stop(self):
        """
        Signal the agent to stop after the current customer finishes.

        This is a graceful stop - the current call (if any) will complete,
        but no new calls will be started.
        """
        if not self.is_running:
            log.warning("Agent is not running.")
            return

        log.info("Stopping agent... (will finish current customer first)")
        self.status = STATE_STOPPING
        self._stop_event.set()  # Signal the thread to stop

    def _run(self):
        """
        Internal method that runs in the background thread.
        Handles the full processing workflow with error handling.
        """
        self.status = STATE_RUNNING

        try:
            # Step 1: Initialize LLM (provider chosen by LLM_PROVIDER in .env)
            log.info("Initializing LLM provider...")
            try:
                self._llm = get_llm_provider()
            except ValueError as e:
                log.error(f"LLM initialization failed: {e}")
                self.status = STATE_ERROR
                return

            # Step 2: Load spreadsheet
            log.info("Loading spreadsheet...")
            workbook = self._load_and_validate()
            if workbook is None:
                return  # Error already logged, status already set

            # Step 2: Find pending customers
            pending = get_pending_customers(workbook)

            if not pending:
                log.info("No PENDING customers found. All done!")
                self.status = STATE_COMPLETED
                return

            log.info(f"Found {len(pending)} PENDING customers to process.")

            # Step 4: Process each customer
            for i, customer in enumerate(pending, 1):
                # Check if stop was requested BEFORE starting a new call
                if self._stop_event.is_set():
                    if self._llm_fatal_error:
                        log.error(f"Stopped: {self._llm_fatal_error}. "
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
                self.status = STATE_ERROR
            else:
                self.status = STATE_COMPLETED
            self._print_summary()

        except Exception as e:
            log.critical(f"Fatal error in agent: {e}")
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
            self.status = STATE_ERROR
            return None
        except Exception as e:
            log.error(f"Could not open spreadsheet: {e}")
            self.status = STATE_ERROR
            return None

        try:
            validate_spreadsheet(workbook)
            log.info(f"Spreadsheet loaded and validated: {self.spreadsheet_path}")
        except ValueError as e:
            log.error(f"Invalid spreadsheet format: {e}")
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
        self.status = STATE_CALLING

        log.info(f"--- Customer {index}/{total} ---")
        log.info(f"  Name:  {name}")
        log.info(f"  Phone: {phone}")
        log.info(f"  Status: CALLING...")

        try:
            # Have a text conversation with the AI acting as bank agent
            result = self._conduct_conversation(customer)

            # Validate the result before updating spreadsheet
            if result not in ("INTERESTED", "NOT_INTERESTED"):
                log.warning(f"  Result '{result}' for {name}. Keeping PENDING.")
                self.summary["errors"] += 1
                return

            # Update spreadsheet
            self.status = STATE_PROCESSING
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

        except LLMFatalError as e:
            # LLM unusable (bad key / daily quota gone): customer stays PENDING, stop the run
            log.error(f"  LLM unavailable: {e}. '{name}' remains PENDING.")
            self._llm_fatal_error = f"LLM unavailable ({e})"
            self._stop_event.set()

        except Exception as e:
            # SAFETY: On ANY error, customer stays PENDING
            log.error(f"  Error processing {name}: {e}")
            log.error(f"  Customer '{name}' remains PENDING (safe failure).")
            self.summary["errors"] += 1

        finally:
            self.status = STATE_RUNNING

    def _conduct_conversation(self, customer):
        """
        Conduct a text-based conversation with the AI as the bank agent.
        The user types as the customer in the terminal.

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
        ai_greeting = get_fixed_greeting(name)
        print(f"\n  AI Agent: {ai_greeting}")
        conversation_history.append(f"AI: {ai_greeting}")

        # Step 2: Multi-turn conversation
        for turn in range(max_turns):
            # Get customer response from terminal
            try:
                customer_input = input(f"  You ({name}): ").strip()
            except EOFError:
                log.warning("Input ended. Classifying as UNCLEAR.")
                return "UNCLEAR"

            if not customer_input:
                print("  (Please type a response)")
                continue

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
            print(f"  AI Agent: {reply}")
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
