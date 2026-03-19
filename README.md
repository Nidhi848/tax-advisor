# Personal Tax Advisor

A 2025 US federal tax advisor with a Claude-powered chat, tax calculator, and document entry (W-2 / 1099).

## Setup

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Add your Anthropic API key to `.env`:

```
ANTHROPIC_API_KEY=your_key_here
```

## Running the App

**Backend:**
```bash
source .venv/bin/activate && uvicorn api:app --reload
```

**Frontend:**
```bash
cd frontend && npm install && npm run dev
```

Access the app at **http://localhost:5173**

## API Endpoints

- `POST /calculate` — Tax breakdown (income, filing_status, deductions)
- `POST /document/manual` — Manual W-2 or 1099 entry
- `POST /document/pdf` — PDF upload for W-2 or 1099
- `POST /chat` — Streamed chat with Claude (SSE)
- `GET /profile` — User profile
- `POST /profile` — Update profile

## CLI (Legacy)

```bash
python main.py
```
