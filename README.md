# AI Loan Customer Agent

A simple AI Voice Agent that acts as a Customer Success Partner for a bank's loan-program outreach.

The agent reads a spreadsheet, finds PENDING customers, calls them one by one, has a natural conversation, determines whether the customer is interested in the loan, and updates the spreadsheet accordingly.

## Current Status: Phase 1 Complete

- [x] Phase 1.1 — Project Skeleton
- [x] Phase 1.2 — Create Sample Spreadsheet
- [x] Phase 1.3 — Read & Find PENDING Customers
- [x] Phase 1.4 — Update Spreadsheet with Color Coding
- [ ] Phase 2 — Processing Loop & Simulated Agent
- [ ] Phase 3 — Add Gemini LLM
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

# Copy env template and add your keys
copy .env.example .env
```

## Usage

```bash
# Generate sample spreadsheet with fake data
python create_sample_data.py

# Run the agent
python main.py
```

## Tech Stack

- **Language:** Python
- **Spreadsheet:** Excel (.xlsx) via openpyxl
- **LLM:** Gemini Free Tier (Phase 3)
- **Voice:** Whisper STT + Local TTS (Phase 4)
