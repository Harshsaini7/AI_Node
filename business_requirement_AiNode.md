# Business Requirements — AI Loan Qualification Voice Agent

## 1. Project Overview

This is a personal R&D project to build a simple AI Voice Agent that acts as a Customer Success Partner for a bank's loan-program outreach.

The application has **one primary purpose**:

> When the user presses the **Start** button, the AI Agent reads the spreadsheet, finds customers whose call status is `PENDING`, calls them one by one, has a natural conversation, determines whether the customer is interested in the loan, and updates the spreadsheet accordingly.

The user should be able to press **Stop** to stop the agent from processing further customers.

This is a learning project and should remain intentionally simple.

---

# 2. Core User Experience

The application should have a very simple interface:

```text
┌─────────────────────────────────────────────┐
│           AI LOAN CUSTOMER AGENT            │
│                                             │
│   Spreadsheet: loan_leads.xlsx             │
│                                             │
│        [ START AGENT ]   [ STOP AGENT ]     │
│                                             │
│   Agent Status: IDLE                        │
│   Current Customer: -                       │
│                                             │
└─────────────────────────────────────────────┘
```

There should be **no unnecessary dashboard, analytics system, complex navigation, or separate CRM UI** in the initial version.

The spreadsheet itself is the main data interface.

---

# 3. Primary Workflow

When the user presses `START AGENT`:

```text
START
  |
  v
Read Spreadsheet
  |
  v
Find PENDING Customer
  |
  v
Call Customer
  |
  v
AI Voice Conversation
  |
  v
Determine Customer Interest
  |
  +----------------------------+
  |                            |
  v                            v
INTERESTED                 NOT INTERESTED
  |                            |
  v                            v
Mark GREEN                  Mark RED
  |                            |
  +-------------+--------------+
                |
                v
        Find next PENDING
                |
                v
             Repeat
```

The agent continues until:

- There are no `PENDING` customers left, or
- The user presses `STOP`.

---

# 4. Spreadsheet Requirements

The spreadsheet is the primary source of lead data and the primary place where results are stored.

For the initial version, use an Excel file:

```text
loan_leads.xlsx
```

Example:

| Name | Phone Number | Status |
|---|---|---|
| Rahul Sharma | 9000000001 | PENDING |
| Amit Kumar | 9000000002 | PENDING |
| Priya Singh | 9000000003 | INTERESTED |
| Neha Verma | 9000000004 | NOT INTERESTED |

The minimum required columns are:

```text
Name
Phone Number
Status
```

---

# 5. Spreadsheet Color Requirements

The `Status` column should also have a visual color.

### PENDING

Use a neutral/default color.

```text
PENDING
```

### INTERESTED

The row should be marked **GREEN**.

```text
INTERESTED
```

### NOT_INTERESTED

The row should be marked **RED**.

```text
NOT_INTERESTED
```

The text status is the source of truth. Color is only a visual representation.

---

# 6. Start Button Behavior

When the user presses:

```text
START AGENT
```

the application should:

1. Load the spreadsheet.
2. Find the first row whose status is `PENDING`.
3. Start the AI calling process for that customer.
4. Conduct the conversation.
5. Determine the outcome.
6. Update the spreadsheet.
7. Find the next `PENDING` customer.
8. Continue automatically.

The user should NOT need to manually start each individual call.

---

# 7. Stop Button Behavior

When the user presses:

```text
STOP AGENT
```

the agent should stop starting new customer calls.

If possible, the current conversation should be allowed to finish gracefully before the agent completely stops.

At minimum, the system must guarantee:

> After STOP is pressed, the agent must not start another customer call.

The agent status should return to:

```text
STOPPED
```

or:

```text
IDLE
```

---

# 8. AI Voice Conversation

The AI should have a natural and polite voice conversation with the customer.

The AI's primary objective is very simple:

> Determine whether the customer is interested in learning more about the loan.

The AI does NOT need to make loan approval decisions.

It only qualifies interest.

---

# 9. AI Agent Personality

The AI should behave as a:

> Polite, professional Customer Success Partner for a bank.

The AI should:

- Speak naturally.
- Keep responses reasonably short.
- Listen to the customer's response.
- Answer basic questions when approved information is available.
- Ask clarification questions when necessary.
- Respect the customer's decision.
- Never pressure the customer.
- Politely end the conversation.

---

# 10. Interested Customer

If the customer clearly expresses interest, the AI should say something equivalent to:

> "Okay sir/ma'am, a person from our loan team will connect with you shortly."

Then:

```text
Status = INTERESTED
```

and the spreadsheet row should become **GREEN**.

The agent should then move to the next `PENDING` customer.

---

# 11. Not Interested Customer

If the customer clearly says that they are not interested:

The AI should politely end the conversation.

Then:

```text
Status = NOT_INTERESTED
```

and the spreadsheet row should become **RED**.

The agent should then move to the next `PENDING` customer.

---

# 12. Unclear Customer Response

If the customer's answer is unclear, the AI should not immediately classify the customer as interested or not interested.

It should ask a clarification question.

Example:

```text
Customer:
"Maybe."

AI:
"Sure. Would you like to know more about the loan program?"
```

Only after the customer's intent becomes reasonably clear should the AI classify the lead.

For the initial version, if the conversation cannot determine a clear outcome, the lead may remain:

```text
PENDING
```

and the system should move on safely.

---

# 13. AI Decision

The AI should produce a structured result internally.

Example:

```json
{
  "status": "INTERESTED"
}
```

or:

```json
{
  "status": "NOT_INTERESTED"
}
```

or:

```json
{
  "status": "UNCLEAR"
}
```

The application, not the LLM itself, should update the spreadsheet.

The architecture should be:

```text
AI
 |
 v
Decision
 |
 v
Python Application
 |
 v
Spreadsheet Update
```

Do not allow the LLM to directly edit the spreadsheet.

---

# 14. Customer Selection Logic

When the agent starts, it should search the spreadsheet for:

```text
Status == PENDING
```

Example:

```text
Rahul    PENDING
Amit     PENDING
Priya    INTERESTED
Neha     NOT_INTERESTED
```

The agent should call:

```text
Rahul
```

then:

```text
Amit
```

It should skip:

```text
Priya
Neha
```

because they have already been processed.

---

# 15. Processing Order

The initial implementation should process customers from top to bottom.

Example:

```text
Row 2 → PENDING → Process
Row 3 → PENDING → Process
Row 4 → INTERESTED → Skip
Row 5 → PENDING → Process
```

No advanced queue or scheduling system is required.

---

# 16. Application Status

The simple interface should show the current agent state.

Possible states:

```text
IDLE
RUNNING
CALLING
PROCESSING RESULT
STOPPING
STOPPED
COMPLETED
ERROR
```

Example:

```text
Agent Status: CALLING

Current Customer:
Rahul Sharma
```

After the call:

```text
Agent Status: RUNNING

Current Customer:
Amit Kumar
```

When there are no pending customers:

```text
Agent Status: COMPLETED
```

---

# 17. Technology Requirements

The project should use Python as the primary programming language.

Recommended initial stack:

### Programming

```text
Python
```

### Spreadsheet

```text
Excel (.xlsx)
```

### Spreadsheet library

```text
openpyxl
```

or:

```text
pandas + openpyxl
```

### LLM

Use the **Gemini API Free Tier** initially, subject to Google's current free-tier limits.

The AI provider should be isolated behind a small service/module so that Ollama can be added later if desired.

### Voice

For the free learning version, use a voice pipeline that can run locally where practical.

Possible components:

```text
Speech-to-Text:
Whisper / faster-whisper

LLM:
Gemini initially

Text-to-Speech:
A free/local TTS solution
```

### Real phone calling

Real phone calling through services such as:

```text
Twilio
Vapi
Retell AI
```

is an optional future integration.

It must NOT be required for the core ₹0 version.

---

# 18. Important Architecture Principle

Keep the application simple.

The core architecture should be:

```text
                    ┌──────────────────┐
                    │ Excel Spreadsheet│
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Python Agent App │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Voice Pipeline  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │    Gemini LLM    │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Interest Result  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Update Excel     │
                    └──────────────────┘
```

There is no requirement for:

- PostgreSQL
- MongoDB
- SQLite
- Redis
- React dashboard
- Admin dashboard
- Authentication system
- Analytics system
- CRM
- Separate frontend/backend deployment

These are intentionally excluded from the current scope.

---

# 19. No Database Requirement

The Excel spreadsheet is the data store for the current version.

Do NOT introduce a database.

The application only needs to:

```text
READ Excel
   ↓
PROCESS
   ↓
WRITE Excel
```

A database can be considered in a future project version, but it is not part of this requirement.

---

# 20. No Complex UI Requirement

The UI should be extremely simple.

Required controls:

```text
START AGENT
STOP AGENT
```

Required information:

```text
Agent Status
Current Customer
```

Optional:

```text
Number of pending customers
```

Do not build a full dashboard.

---

# 21. No Authentication Requirement

Authentication/login is not required for this personal R&D project.

---

# 22. No Deployment Requirement

The initial application should run locally on the developer's computer.

No cloud deployment is required.

---

# 23. No Google Sheets Requirement Initially

The first version should use a local Excel file.

Google Sheets may be considered later, but it is NOT required for the MVP.

---

# 24. Error Handling

The system should safely handle:

- Excel file not found.
- Invalid spreadsheet format.
- Missing required columns.
- Empty phone number.
- Empty customer name.
- LLM API failure.
- Voice failure.
- Speech recognition failure.
- Text-to-speech failure.
- Network failure.
- Invalid AI response.

A technical failure must NOT automatically mark a customer as:

```text
NOT_INTERESTED
```

If the system cannot determine the result, leave the customer as:

```text
PENDING
```

or use an appropriate technical error state without falsely classifying the customer.

---

# 25. Security and Privacy

This is a personal R&D project.

Use synthetic/fake customer data only.

Do not use:

- Real bank customers.
- Real banking information.
- PAN.
- Aadhaar.
- Bank account numbers.
- Credit scores.
- OTPs.
- Passwords.
- Card information.
- Sensitive financial information.

API keys must never be hardcoded in source code.

Use environment variables:

```text
GEMINI_API_KEY=...
```

and keep `.env` out of Git.

---

# 26. AI Safety Rules

The AI must NOT:

- Guarantee loan approval.
- Invent loan interest rates.
- Invent eligibility criteria.
- Make credit decisions.
- Request OTPs.
- Request passwords.
- Request PINs.
- Request banking credentials.
- Pressure customers.
- Misrepresent information.

The agent's job is only:

```text
Customer Interest Qualification
```

---

# 27. Development Phases

The project should be built in small phases.

## Phase 1 — Spreadsheet Agent Without AI

Build:

```text
Start Button
     ↓
Read Excel
     ↓
Find PENDING
     ↓
Simulate Result
     ↓
Update GREEN/RED
     ↓
Next PENDING
```

No voice.

No Gemini.

Purpose:

- Learn spreadsheet automation.
- Build Start/Stop workflow.
- Build processing loop.

---

## Phase 2 — Add Gemini

Replace the simulated result with Gemini.

```text
Start
  ↓
Read PENDING
  ↓
Conversation / Customer Input
  ↓
Gemini
  ↓
INTERESTED / NOT_INTERESTED
  ↓
Excel
```

Purpose:

- Learn LLM API usage.
- Learn prompts.
- Learn structured outputs.
- Learn AI decision handling.

---

## Phase 3 — Add Voice

Add:

```text
Microphone
    ↓
Speech-to-Text
    ↓
Gemini
    ↓
Text-to-Speech
    ↓
Speaker
```

Now the developer can actually talk to the AI.

Purpose:

- Learn voice agents.
- Learn STT.
- Learn TTS.
- Learn conversational state.

---

## Phase 4 — Optional Real Phone Calling

Only after the local voice agent works should real phone calling be considered.

Possible providers:

```text
Vapi
Retell AI
Twilio
```

This phase is optional because real phone calls generally introduce usage costs and additional compliance/consent requirements.

---

# 28. Final MVP

The MVP should ultimately behave like this:

### Spreadsheet

```text
Name          Phone          Status

Rahul         9000000001     PENDING
Amit          9000000002     PENDING
Priya         9000000003     INTERESTED
Neha          9000000004     NOT_INTERESTED
```

### User presses

```text
[ START AGENT ]
```

### Agent

```text
Reads spreadsheet
      ↓
Finds Rahul = PENDING
      ↓
Starts conversation
      ↓
Customer says:
"Yes, I am interested."
      ↓
AI classifies:
INTERESTED
      ↓
Rahul row → GREEN
      ↓
Finds Amit = PENDING
      ↓
Calls Amit
      ↓
Customer says:
"No, I'm not interested."
      ↓
AI classifies:
NOT_INTERESTED
      ↓
Amit row → RED
      ↓
Find next PENDING
```

When all pending customers are processed:

```text
Agent Status: COMPLETED
```

If the user presses:

```text
[ STOP AGENT ]
```

the agent stops processing new customers.

---

# 29. Definition of Success

The project is successful when the user can:

1. Open the application.
2. See the Start and Stop buttons.
3. Press Start.
4. The application reads the Excel spreadsheet.
5. It finds PENDING customers.
6. It processes customers one by one.
7. The AI has a voice conversation with the customer.
8. The AI determines whether the customer is interested.
9. Interested customers are marked `INTERESTED` and visually GREEN.
10. Not interested customers are marked `NOT_INTERESTED` and visually RED.
11. The agent automatically moves to the next PENDING customer.
12. Pressing Stop prevents new calls from starting.
13. When no PENDING customers remain, the agent stops automatically.

---

# 30. Coding Agent Instructions

Before implementing anything, read this entire document.

The coding agent MUST follow these rules:

1. Keep the application simple.
2. Do not add a database.
3. Do not build a complex dashboard.
4. Do not build authentication.
5. Do not build a CRM.
6. Do not add analytics unless explicitly requested later.
7. Use the Excel spreadsheet as the data store.
8. Use Python as the primary language.
9. Build Start/Stop functionality.
10. Process PENDING leads sequentially.
11. Do not skip directly to advanced features.
12. Build Phase 1 first and verify it.
13. Then implement Phase 2.
14. Then implement Phase 3.
15. Keep real telephony as an optional final phase.
16. Do not make paid services mandatory.
17. Use Gemini Free Tier initially.
18. Keep AI provider integration modular enough to support Ollama later.
19. Keep voice provider integration modular enough to support Vapi/Retell/Twilio later.
20. Never use real customer or banking data.
21. Never hardcode API keys.
22. Never allow the LLM to directly modify the spreadsheet.
23. The Python application must validate AI results before updating the spreadsheet.
24. Never classify a technical/API failure as NOT_INTERESTED.
25. Keep the UI limited to Start, Stop, Agent Status, and Current Customer.
26. Do not implement features that are not required by this document.
27. If a future feature is useful, document it as a future enhancement rather than implementing it now.
28. After completing each phase, verify that the application still works before moving to the next phase.

---

# 31. Immediate First Task

The coding agent should start with **Phase 1 only**.

First implementation target:

```text
Excel Spreadsheet
       ↓
Python Application
       ↓
Simple UI
       ↓
START button
       ↓
Find PENDING customer
       ↓
Simulate Interested / Not Interested
       ↓
Update Excel
       ↓
GREEN / RED
       ↓
Next PENDING customer
       ↓
STOP button can stop future processing
```

Do NOT implement voice, Gemini, Vapi, Retell, Twilio, databases, React dashboards, or cloud deployment in the first task.

Once Phase 1 is working correctly, proceed to Phase 2.
