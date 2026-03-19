# Personal Tax Advisor

A **2025 US federal tax advisor** powered by Claude. Chat with an AI assistant, run tax calculations, enter W-2/1099 documents, and model “what if” scenarios (STR, cost segregation, capital gains, 401k/IRA). All data is stored locally; only tax-related figures are sent to the Anthropic API.

---

## Features

- **Chat** — Ask tax questions in plain language. Claude uses your profile and can run calculations, update your profile, and invoke scenario modelers from the conversation.
- **Tax calculator** — Estimate federal tax from income, filing status, and optional deductions (2025 brackets and standard deduction).
- **Document entry** — Enter W-2 or 1099 data manually or upload a PDF (PDFs are sent to Anthropic for extraction). Data is saved to your profile.
- **Profile** — Filing status, state, dependents, income, age, self-employment income. Used as defaults across the app and in chat.
- **Scenario modeling** — Four modelers:
  - **STR (short-term rental)** — Depreciation, STR “loophole” eligibility (avg stay &lt; 7 days, 750+ hours), passive loss rules, MAGI phaseout.
  - **Cost segregation** — Reclassified depreciation, 60% bonus (2024), Year 1 vs straight-line, estimated tax savings.
  - **Capital gains harvesting** — LTCG rates (0/15/20%), net gain/loss, $3k ordinary offset, carryforward.
  - **401k/IRA** — Tax savings at contribution levels, Roth eligibility (2024 MAGI limits), backdoor Roth note, SEP-IRA if self-employed.
- **Compare scenarios** — Run 2–4 scenarios vs baseline; side-by-side table with Δ vs baseline, recommendation, CSV export, and print/PDF.
- **Chat history** — Conversations saved locally; list, load, delete, and resume. Today / Yesterday / Earlier grouping.
- **Getting started** — Welcome screen for first-time users and a “?” help that explains profile → documents → chat.

---

## Tech stack

- **Backend:** FastAPI, Anthropic Python SDK, local JSON storage (profile, conversations).
- **Frontend:** React, Vite, React Router, Tailwind CSS.

---

## Setup

### 1. Clone and backend

```bash
git clone https://github.com/Nidhi848/tax-advisor.git
cd tax-advisor
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. API key

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your_key_here
```

(Used for chat and for PDF document parsing.)

### 3. Frontend

```bash
cd frontend
npm install
```

---

## Running the app

**Terminal 1 — backend:**

```bash
cd tax-advisor
source .venv/bin/activate
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — frontend:**

```bash
cd tax-advisor/frontend
npm run dev
```

Open **http://localhost:5173**. The frontend expects the API at **http://localhost:8000** (see `frontend/src/lib/api.js` if you use a different port).

---

## Data and privacy

- **Stored locally (never sent to API):** Profile (`user_profile.json`), chat conversations (`conversations/`), manual document data you enter.
- **Sent to Anthropic:** Chat messages and any document content you upload as PDF (for parsing). The app does not send your name or employer; tax figures and conversation context are used to answer questions and run tools.
- Add `.env`, `user_profile.json`, and `conversations/` to your own ignore list if you fork; they are in `.gitignore` here.

---

## API overview

| Endpoint | Description |
|----------|-------------|
| `POST /calculate` | Tax breakdown (income, filing status, optional deductions). |
| `POST /document/manual` | Submit W-2 or 1099 fields as JSON. |
| `POST /document/pdf` | Upload W-2 or 1099 PDF for extraction. |
| `POST /chat` | Streamed chat (SSE). Optional `conversation_id` to continue a thread; returns new id when starting a new one. |
| `GET /conversations` | List conversations (id, timestamp, preview). |
| `GET /conversations/{id}` | Full message history for a conversation. |
| `DELETE /conversations/{id}` | Delete a conversation. |
| `POST /scenario/str` | Run STR scenario modeler. |
| `POST /scenario/cost-seg` | Run cost segregation modeler. |
| `POST /scenario/capital-gains` | Run capital gains harvesting modeler. |
| `POST /scenario/401k` | Run 401k/IRA optimizer. |
| `POST /scenario/compare` | Compare multiple scenarios; returns table vs baseline. |
| `GET /profile` | Get user profile. |
| `POST /profile` | Update user profile. |

---

## Disclaimer

This app is for **educational and estimation purposes** only. It is not a substitute for professional tax, legal, or financial advice. Verify all numbers and strategies with a qualified tax professional or CPA.
