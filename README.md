# AI Loan Customer Agent

A simple AI Voice Agent that acts as a Customer Success Partner for a bank's loan-program outreach.

The agent reads a spreadsheet, finds PENDING customers, calls them one by one, has a natural conversation, determines whether the customer is interested in the loan, and updates the spreadsheet accordingly.

## Current Status: Phase 3 (text conversation with an LLM)

- [x] Phase 1 — Project setup & Excel basics (skeleton, sample data, read PENDING, colour-coded updates)
- [x] Phase 2.1–2.3 — Processing loop, terminal Start/Stop, error handling & logging
- [ ] Phase 2.4 — Flask web UI (not built yet; the app is terminal-based for now)
- [x] Phase 3 — LLM text conversation (Groq gpt-oss-120b, Gemini or local Ollama; structured JSON decision)
- [ ] Phase 4 — Add Voice Pipeline
- [ ] Phase 5 — Optional Real Phone Calling

## Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
.\venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt

# Copy env template and add your settings
copy .env.example .env
```

## Choosing the LLM

Set `LLM_PROVIDER` in `.env`:

| Provider | `LLM_PROVIDER` | Notes |
|---|---|---|
| Groq (cloud) | `groq` | Needs `GROQ_API_KEY`. Runs `openai/gpt-oss-120b` by default (`GROQ_MODEL`). |
| Gemini (cloud) | `gemini` (default if unset) | Needs `GEMINI_API_KEY`. The free tier has a small daily request limit. Model set by `GEMINI_MODEL`. |
| Ollama (local) | `ollama` | Free, offline, no quota. Model set by `OLLAMA_MODEL`. |

### Groq (gpt-oss-120b)
1. Create a key at https://console.groq.com/keys and put it in `.env` as `GROQ_API_KEY`.
2. Set `LLM_PROVIDER=groq` in `.env`.

### Gemini
1. Get a key at https://aistudio.google.com/apikey and put it in `.env` as `GEMINI_API_KEY`.
2. Check https://aistudio.google.com/rate-limit and set `GEMINI_MODEL` to a model with a high free daily limit (default: `gemini-2.5-flash-lite`).

### Ollama
1. Install Ollama from https://ollama.com.
2. Run `ollama pull llama3.2:3b` (or set `OLLAMA_MODEL` to another model you pulled).
3. Set `LLM_PROVIDER=ollama` in `.env`. The server is expected at `http://127.0.0.1:11434` (`OLLAMA_HOST`).

## Usage

```bash
# Generate sample spreadsheet with fake data
python create_sample_data.py

# Run the agent (terminal commands: start, stop, status, reset, quit)
python main.py
```

During `start`, the AI speaks first and you type the customer's replies in the terminal.

## How it works

- Greeting is fixed text (0 LLM calls).
- Each customer reply costs **one** LLM call, which returns `{"reply": "...", "status": "INTERESTED | NOT_INTERESTED | UNCLEAR"}`.
- The Python app validates the result and is the only thing that writes to Excel. The LLM never edits the spreadsheet.
- `INTERESTED` -> green row, `NOT_INTERESTED` -> red row.
- `UNCLEAR`, invalid AI output, or any technical failure -> the customer stays `PENDING`. A failure never marks a customer `NOT_INTERESTED`.
- If the LLM cannot work at all (invalid API key, or the daily quota runs out), the agent stops with status `ERROR` and the remaining customers stay `PENDING`.

## Tech Stack

- **Language:** Python
- **Spreadsheet:** Excel (.xlsx) via openpyxl
- **LLM:** Groq (gpt-oss-120b), Gemini free tier or local Ollama (switchable via `LLM_PROVIDER`)
- **Voice:** Whisper STT + Local TTS (Phase 4, not built yet)

## Safety

- Use synthetic/fake customer data only.
- Never commit `.env` (it is in `.gitignore`).
