# 🚀 AI Loan Customer Agent — Development Phases

> Each phase is small, self-contained, and testable. After every phase you'll have a **working piece** you can run, see, and learn from.

---

## 🏗️ Phase 1 — Project Setup & Excel Basics

### Phase 1.1 — Project Skeleton
**What you'll build:**
- Create the project folder structure
- Set up a Python virtual environment
- Create `requirements.txt` with initial dependencies (`openpyxl`)
- Create a `.env.example` and `.gitignore` (to keep API keys safe)
- Create a basic `main.py` that just prints `"AI Loan Agent Starting..."`

**What you'll learn:**
- Python project structure best practices
- Virtual environments (`venv`)
- Dependency management
- Environment variable safety from Day 1

**Verify:** Run `python main.py` → see the print message ✅

---

### Phase 1.2 — Create Sample Spreadsheet
**What you'll build:**
- A Python script (`create_sample_data.py`) that generates `loan_leads.xlsx`
- Spreadsheet with columns: `Name`, `Phone Number`, `Status`
- 6–8 rows of fake customer data, all with status `PENDING`
- Header row styled with bold font

**What you'll learn:**
- `openpyxl` basics — creating workbooks, sheets, rows
- Writing Excel files from Python
- Working with fake/synthetic data

**Verify:** Open `loan_leads.xlsx` in Excel → see formatted data ✅

---

### Phase 1.3 — Read Spreadsheet & Find PENDING Customers
**What you'll build:**
- A module `spreadsheet_manager.py` with functions:
  - `load_spreadsheet(filepath)` → returns workbook
  - `get_pending_customers(workbook)` → returns list of `{name, phone, row_number}`
- Call these from `main.py` and print the pending customers

**What you'll learn:**
- Reading Excel files with `openpyxl`
- Iterating over rows and columns
- Filtering data based on cell values
- Structuring code into modules

**Verify:** Run `main.py` → see all PENDING customers printed ✅

---

### Phase 1.4 — Update Spreadsheet with Color Coding
**What you'll build:**
- Add functions to `spreadsheet_manager.py`:
  - `update_customer_status(workbook, row, status)` → writes status + applies color
  - `save_spreadsheet(workbook, filepath)`
- `INTERESTED` → green row fill
- `NOT_INTERESTED` → red row fill
- `PENDING` → no fill (neutral)
- Test by manually updating one row and saving

**What you'll learn:**
- Writing/modifying Excel cells
- `openpyxl` styling — `PatternFill` for cell colors
- Saving modified workbooks without data loss

**Verify:** Run script → open Excel → see one row turned green or red ✅

---

## 🔄 Phase 2 — Processing Loop & Simulated Agent

### Phase 2.1 — Sequential Processing Loop
**What you'll build:**
- In `main.py`, build the core loop:
  ```
  for each PENDING customer:
      print "Processing: {name}"
      simulate a random result (INTERESTED / NOT_INTERESTED)
      update spreadsheet
      print "Result: {status}"
  ```
- Add a 2-second delay between customers (to simulate a real call)
- Print a summary at the end

**What you'll learn:**
- Building a sequential processing pipeline
- Using `time.sleep()` for pacing
- The core agent loop pattern

**Verify:** Run → watch customers get processed one by one → check Excel ✅

---

### Phase 2.2 — Simple Terminal UI (Start/Stop)
**What you'll build:**
- A simple command-line interface using Python's `threading`:
  - User types `start` → agent begins processing
  - User types `stop` → agent stops after current customer
  - Display current status: `IDLE`, `RUNNING`, `CALLING`, `COMPLETED`, `STOPPED`
  - Display current customer name
- Create an `agent.py` module with an `Agent` class that manages state

**What you'll learn:**
- Python `threading` basics
- Shared state between threads (agent running flag)
- Clean start/stop patterns
- State machine basics (IDLE → RUNNING → COMPLETED)

**Verify:** Start agent → see it process → type `stop` → it stops gracefully ✅

---

### Phase 2.3 — Error Handling & Safe Failures
**What you'll build:**
- Handle these cases gracefully:
  - Excel file not found → clear error message
  - Missing columns → clear error message
  - Empty name or phone number → skip customer, log warning
  - Crash during processing → customer stays `PENDING` (never wrongly marked)
- Add a `logger.py` module with basic logging to console

**What you'll learn:**
- Python exception handling (`try/except`)
- Defensive programming
- Why failures should **never** falsely classify a customer
- Basic logging patterns

**Verify:** Delete the Excel file → run → see friendly error instead of crash ✅

---

### Phase 2.4 — Web UI with Flask (Simple Dashboard)
**What you'll build:**
- Replace the terminal UI with a minimal Flask web app
- Single page with:
  - **Start Agent** button
  - **Stop Agent** button
  - **Agent Status** display (IDLE / RUNNING / COMPLETED etc.)
  - **Current Customer** display
  - **Pending Count** display
- Use Server-Sent Events (SSE) or polling to update status in real-time

**What you'll learn:**
- Flask basics — routes, templates, static files
- Connecting a web frontend to a Python backend
- Real-time status updates
- HTML/CSS/JS basics for a simple control panel

**Verify:** Open browser → click Start → watch status update live → click Stop ✅

---

## 🤖 Phase 3 — Add Gemini LLM

### Phase 3.1 — Gemini API Integration (Hello World)
**What you'll build:**
- Create an `llm_provider.py` module with:
  - `GeminiProvider` class
  - A simple `chat(message)` method
- Load `GEMINI_API_KEY` from `.env` using `python-dotenv`
- Test with a simple prompt: *"Say hello in one sentence"*

**What you'll learn:**
- Gemini API setup and authentication
- Making API calls to an LLM
- Environment variable management with `python-dotenv`
- Modular AI provider design (so you can swap to Ollama later)

**Verify:** Run → see Gemini respond with a greeting ✅

---

### Phase 3.2 — Loan Agent Prompt Engineering
**What you'll build:**
- Design the system prompt for the loan qualification agent
- The AI should:
  - Introduce itself as a bank's customer success partner
  - Ask about loan interest politely
  - Handle "yes", "no", "maybe" responses
  - Follow AI safety rules (no guarantees, no pressure, no sensitive data requests)
- Create a `prompts.py` module with the system prompt
- Test with hardcoded customer responses

**What you'll learn:**
- Prompt engineering fundamentals
- System prompts vs user prompts
- AI safety guardrails in practice
- Conversation design

**Verify:** Send test messages → AI responds naturally and professionally ✅

---

### Phase 3.3 — Structured AI Decision Output
**What you'll build:**
- Make Gemini return a structured JSON decision:
  ```json
  { "status": "INTERESTED" }
  ```
- Add validation in `agent.py`:
  - Parse the JSON
  - Validate status is one of: `INTERESTED`, `NOT_INTERESTED`, `UNCLEAR`
  - If `UNCLEAR` → customer stays `PENDING`
  - If JSON is invalid → customer stays `PENDING` (safe failure)
- The **Python app** updates Excel, never the LLM

**What you'll learn:**
- Getting structured output from LLMs
- JSON parsing and validation
- The principle: **LLM decides, app acts**
- Handling edge cases in AI responses

**Verify:** Run with simulated inputs → see correct status updates in Excel ✅

---

### Phase 3.4 — Text-Based Conversation Loop
**What you'll build:**
- Replace simulation with a real text conversation in the terminal:
  ```
  AI: "Hello Rahul, I'm calling from XYZ Bank..."
  You (as customer): "What is this about?"
  AI: "We have a loan program..."
  You: "I'm interested"
  AI: "Great! Someone will connect with you shortly."
  → Status: INTERESTED → Excel updated
  ```
- Multi-turn conversation support
- Conversation ends when AI determines interest level

**What you'll learn:**
- Multi-turn LLM conversations
- Conversation history management
- When to end a conversation programmatically
- The full pipeline: Input → LLM → Decision → Excel

**Verify:** Have a text chat with the AI → see Excel update correctly ✅

---

## 🎙️ Phase 4 — Add Voice Pipeline

### Phase 4.1 — Speech-to-Text (Microphone Input)
**What you'll build:**
- Install and set up `faster-whisper` (or `whisper`)
- Create a `stt_provider.py` module:
  - `listen()` → records from microphone → returns text
- Test standalone: speak into mic → see your words printed

**What you'll learn:**
- Speech-to-Text technology
- Audio recording from microphone in Python
- Whisper model usage
- Audio processing basics

**Verify:** Speak → see your words accurately printed ✅

---

### Phase 4.2 — Text-to-Speech (Speaker Output)
**What you'll build:**
- Set up a local TTS solution (e.g., `pyttsx3`, `edge-tts`, or `gTTS`)
- Create a `tts_provider.py` module:
  - `speak(text)` → converts text to speech → plays through speaker
- Test standalone: pass text → hear it spoken

**What you'll learn:**
- Text-to-Speech technology
- Audio playback in Python
- Comparing TTS engines (quality vs speed vs cost)

**Verify:** Run → hear the AI speak your text aloud ✅

---

### Phase 4.3 — Full Voice Conversation
**What you'll build:**
- Wire everything together in a `voice_pipeline.py`:
  ```
  AI speaks (TTS) → User speaks (STT) → Gemini processes → AI speaks (TTS) → ...
  ```
- Replace the text input in the agent loop with the voice pipeline
- The full flow:
  1. AI greets customer (TTS)
  2. Customer responds (STT → microphone)
  3. Gemini processes response
  4. AI replies (TTS)
  5. Repeat until interest is determined
  6. Excel updated

**What you'll learn:**
- Building a real-time voice pipeline
- Coordinating STT + LLM + TTS
- Handling voice conversation flow
- Turn-taking in voice agents

**Verify:** Have a spoken conversation with the AI → Excel updates correctly ✅

---

### Phase 4.4 — Voice Polish & Edge Cases
**What you'll build:**
- Handle voice-specific edge cases:
  - Silence detection (customer doesn't respond)
  - Background noise handling
  - Speech recognition errors → ask customer to repeat
  - TTS interruption handling
- Add a "listening" indicator in the web UI
- Add conversation timeout

**What you'll learn:**
- Real-world voice agent challenges
- Graceful degradation
- UX considerations for voice interfaces

**Verify:** Test with noisy environment, silence, mumbling → agent handles gracefully ✅

---

## 📞 Phase 5 — Optional: Real Phone Calling

### Phase 5.1 — Telephony Provider Integration
**What you'll build:**
- Create a `telephony_provider.py` module
- Integrate with one provider (Twilio / Vapi / Retell AI)
- Make a test call to your own phone number
- Play a simple greeting message

> [!CAUTION]
> This phase involves **paid services** and **real phone calls**. Only proceed when Phases 1–4 are solid.

**What you'll learn:**
- Telephony APIs
- Making real phone calls from code
- Webhook handling
- Cost management for API services

**Verify:** Your phone rings → you hear the AI greeting ✅

---

### Phase 5.2 — Full Phone Call Loop
**What you'll build:**
- Connect the voice pipeline to real phone calls
- Full flow: Read Excel → Call phone → AI conversation → Determine interest → Update Excel
- Handle call failures (no answer, busy, disconnected)

**What you'll learn:**
- End-to-end telephony integration
- Real-world call handling
- The complete agent pipeline

**Verify:** Agent calls your phone → you have a conversation → Excel updates ✅

---

## 📊 Phase Summary

| Phase | What You Build | AI? | Voice? | Phone? |
|-------|---------------|-----|--------|--------|
| **1.1** | Project skeleton | ❌ | ❌ | ❌ |
| **1.2** | Sample spreadsheet | ❌ | ❌ | ❌ |
| **1.3** | Read & find PENDING | ❌ | ❌ | ❌ |
| **1.4** | Update with colors | ❌ | ❌ | ❌ |
| **2.1** | Processing loop | ❌ | ❌ | ❌ |
| **2.2** | Terminal Start/Stop | ❌ | ❌ | ❌ |
| **2.3** | Error handling | ❌ | ❌ | ❌ |
| **2.4** | Flask Web UI | ❌ | ❌ | ❌ |
| **3.1** | Gemini hello world | ✅ | ❌ | ❌ |
| **3.2** | Prompt engineering | ✅ | ❌ | ❌ |
| **3.3** | Structured decisions | ✅ | ❌ | ❌ |
| **3.4** | Text conversation | ✅ | ❌ | ❌ |
| **4.1** | Speech-to-Text | ✅ | ✅ | ❌ |
| **4.2** | Text-to-Speech | ✅ | ✅ | ❌ |
| **4.3** | Full voice conversation | ✅ | ✅ | ❌ |
| **4.4** | Voice polish | ✅ | ✅ | ❌ |
| **5.1** | Telephony test | ✅ | ✅ | ✅ |
| **5.2** | Full phone loop | ✅ | ✅ | ✅ |

---

## 🎯 Golden Rules

> [!IMPORTANT]
> 1. **Complete and test each phase before moving to the next**
> 2. **Each phase should produce something you can run and see**
> 3. **Ask questions — understanding > speed**
> 4. **Keep it simple — resist the urge to add extras**
> 5. **The spreadsheet is your database — no Postgres, no MongoDB**

---

## 💰 Cost at Each Phase

| Phase | Cost |
|-------|------|
| Phase 1 (1.1–1.4) | ₹0 |
| Phase 2 (2.1–2.4) | ₹0 |
| Phase 3 (3.1–3.4) | ₹0 (Gemini Free Tier) |
| Phase 4 (4.1–4.4) | ₹0 (local Whisper + local TTS) |
| Phase 5 (5.1–5.2) | 💸 Paid (Twilio/Vapi credits) |

> You can build a fully working voice AI agent for **₹0** through Phase 4!

---

*Ready? Let's start with **Phase 1.1 — Project Skeleton** 🚀*
