# CLAUDE.md

Context file for Claude (or any AI coding assistant) working on this codebase.
Read this before making non-trivial changes.

## What this is

**Sente** is an AI-powered analyzer for Ugandan mobile money transactions (MTN
and Airtel). It's a capstone project for an AI engineering course, built to
demonstrate a handful of specific AI engineering techniques on top of a real
personal-finance use case.


## The four AI engineering showcases

Every architectural decision in this project ties back to one of these. If a
change weakens any of them, push back.

1. **Hybrid regex + LLM parsing with a measurable fallback rate.** The SMS
   parser tries regex templates first; anything that misses falls through to a
   Claude Haiku structured-output call. The `ParseStats` object tracks the
   regex/LLM/failure split — this is the first metric surfaced in the capstone
   writeup.

2. **Zero-shot → few-shot categorization with an embedding-based learning loop.**
   When a user corrects a category, the correction is embedded
   (`bge-small-en-v1.5` locally) and stored. Future classifications retrieve the
   top-K similar corrections and include them as few-shots. The accuracy delta
   on a frozen eval set is the second capstone metric.

3. **Server-side agent with tool use for natural-language Q&A.** The chat
   endpoint runs the Anthropic tool-use loop server-side (Pattern A — backend
   owns the loop). Tools are narrow and typed:
   `query_transactions`, `aggregate`, `top_counterparties`, `category_trend`.
   The LLM never sees raw rows it doesn't ask for.

4. **Multi-source ingestion with dedupe.** SMS and PDF statements describe the
   same transactions with different details. Ingestion upserts by
   `transaction_id` and merges fields (PDF wins on timestamps, SMS wins on agent
   IDs). See `services/ingest.py`.

## Architecture

```
Frontend (Next.js 15 + shadcn/ui)
    │  HTTP (JSON + multipart for PDFs)
    ▼
Backend (FastAPI)
    ├─ parsers/
    │   ├─ regex_parser.py    Airtel SMS templates, 100% hit rate on real export
    │   ├─ llm_parser.py      Haiku fallback with Pydantic-shaped output
    │   ├─ orchestrator.py    Metrics + fallback coordination
    │   └─ pdf_importer.py    pdfplumber for Airtel PDF statements
    ├─ services/
    │   ├─ ingest.py          Upsert + merge by transaction_id
    │   ├─ categorizer.py     Zero-shot + few-shot retrieval
    │   ├─ embeddings.py      sentence-transformers singleton
    │   ├─ tools.py           DB tools exposed to the chat agent
    │   └─ chat_agent.py      Server-side tool-use loop
    ├─ models/db.py           SQLAlchemy: Transaction, CategoryExample
    ├─ schemas/transaction.py Pydantic: ParsedTransaction, EnrichedTransaction
    ├─ data/taxonomy.py       17 personal-finance categories
    └─ main.py                FastAPI endpoints
```

## Critical domain knowledge

These took real investigation to learn. Don't relearn them.

### SMS vs PDF have different framings for the same transaction

Example: TID `143251777870` appears as:
- SMS: `WITHDRAWN ... UGX400,000 with Agent ID: 678447 ...`
- PDF: `Sent Money to 747198564 EDNA AGABA`

Edna Agaba is clearly a registered agent — the SMS uses the agent view, the
PDF uses the customer view. The ingestion layer merges both records into one
row. **Don't "fix" this by picking one source as canonical — both views are
useful.**

### Airtel doubles many name fields

`"SC BANK SC BANK"`, `"Bonna Gyaviira Morgan Bonna Gyaviira Morgan"`. The
`_dedupe_doubled` helper handles this. Always run counterparty names through
it before display or storage.

### `SELF_TRANSFER` must be excluded from spending analytics

Users routinely move money between their own accounts via mobile money
(bank → Airtel → URA, bank → Airtel → bank). These pass-throughs are NOT real
spending or income. The `EXCLUDE_FROM_TOTALS` constant in the frontend
dashboard handles this; any new analytics code must respect it.

### Airtel's "Total Debit" is fee-inclusive

Sum of `(amount + fee)` across debit rows equals the statement's Total Debit
field. Verified exactly on the March 2026 statement (UGX 6,991,910). Our
reconciliation tests assert this — don't remove them.

### Three timestamp formats in one Airtel export

`15-March-2026 02:01`, `Date 15-March-2026 02:01.`, and bare dates with
trailing periods. We use `dateutil.parse(..., dayfirst=True)` instead of
`strptime` because of this. Don't swap in stricter parsing.

### Some SMS templates drop timestamps

`"Top up of UGX X for NUMBER"` and `"You have been debited UGX X"` have no
embedded timestamp. The parser uses `datetime.utcnow()` as a placeholder — the
SMS XML importer (TODO) will override this with the SMS receive time from the
Android backup.

### Some SMS templates drop recipients

`"You have been debited UGX 75,000 ... TID 143416174774 ... Send using MyAirtel App"`
has no recipient name. These get `counterparty_name=None` and typically require
user correction or later reconciliation with the PDF statement
(which shows `"Sent Money to . Receiving TID 6561053120"` — still no name, but
an external TID you can match on).

## Code conventions

- **Backend:** Python 3.11+, type hints everywhere, Pydantic for wire models,
  SQLAlchemy for ORM. No `async def` for DB code — we use sync SQLAlchemy with
  FastAPI's thread pool.
- **Frontend:** TypeScript strict, React 19, Server Components by default,
  `"use client"` only where needed (forms, charts, interactive state).
- **No clever code.** The parsers, classifiers, and agent loops should read
  linearly. Prefer explicit `if` branches over metaprogramming.
- **Everything is tested against real data.** 25 SMS fixtures + 23 PDF rows,
  all derived from Samuel's actual March 2026 export. Add to fixtures before
  adding to parsers.

## Running things

```bash
# Backend
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # fill in ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000

# Tests
pytest tests/ -v        # expect 39 passed

# Frontend (separate terminal)
cd frontend
npm install
cp .env.local.example .env.local
npm run dev             # http://localhost:3000
```

## Current state (as of April 2026)

Working end-to-end:
- Airtel SMS parsing (9 templates, 100% hit rate on real export)
- Airtel PDF statement ingestion (23/23 rows reconcile with statement totals)
- Categorization with learning loop
- Chat agent with 4 tools
- Dashboard, transactions table, upload, chat UI
