# Sente

AI-powered analyzer for Ugandan mobile money transactions. Ingests MTN and
Airtel data (SMS, PDF statements, CSV, paste), normalizes it, auto-categorizes
with a learning loop, and exposes insights via a dashboard and natural-language
chat.

Capstone project for an AI engineering course. Demonstrates:

- Hybrid regex + LLM structured-output parsing with a measurable fallback rate
- Zero-shot → few-shot categorization with an embedding-based learning loop
- Server-side agent with tool use for natural-language Q&A over transactions
- Multi-source ingestion with upsert / merge by transaction ID

## Monorepo layout

```
sente/
├── CLAUDE.md         Context for AI assistants working on this codebase
├── backend/          FastAPI + SQLAlchemy + Anthropic
│   ├── app/
│   │   ├── parsers/       Regex + LLM fallback for SMS; pdfplumber for PDF
│   │   ├── services/      Categorization, agent, embeddings, ingest
│   │   ├── models/        SQLAlchemy ORM
│   │   ├── schemas/       Pydantic wire models
│   │   └── data/          Category taxonomy
│   └── tests/             39 passing tests, real Airtel fixtures
└── frontend/         Next.js 15 + shadcn/ui + Tailwind
    ├── app/               Dashboard / upload / transactions / chat
    ├── components/        UI primitives + feature components
    └── lib/               Typed API client, types, formatters
```

## Quick start

### Backend

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # add your ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
pytest tests/ -v          # expect 39 passed
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev               # http://localhost:3000
```

## Status

Working:
- Airtel SMS parsing — 9 templates, 100% hit rate on real export
- Airtel PDF statement parsing — 23/23 rows reconcile with statement totals
- Categorization with learning loop
- Chat agent with 4 tools (`query_transactions`, `aggregate`, `top_counterparties`, `category_trend`)
- Dashboard, transactions table with inline category correction, upload, chat UI

Not yet built:
- MTN SMS templates (need real samples)
- SMS XML importer (SMS Backup & Restore format)
- Synthetic data generator
- Eval harness with frozen labeled set
- Budgets + forecasting

See `CLAUDE.md` for more.
