"""FastAPI entry point.

Endpoints:
  GET  /health                Liveness probe
  GET  /metrics               LLM call metrics snapshot
  GET  /categories            Taxonomy for the frontend
  POST /ingest/text           Ingest one or more SMS message strings (JSON)
  POST /ingest/pdf            Ingest an Airtel statement PDF (multipart)
  GET  /transactions          List transactions with simple filters
  POST /transactions/correct  User correction that feeds the learning loop
  POST /chat                  Natural-language Q&A over transactions
"""
from __future__ import annotations

import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.taxonomy import Category, CATEGORY_DESCRIPTIONS
from app.database import get_db, init_db
from app.models.db import Transaction
from app.observability import (
    configure_logging,
    get_logger,
    get_metrics_recorder,
    new_request_id,
)
from app.parsers.orchestrator import parse_batch
from app.parsers.pdf_importer import parse_statement
from app.schemas.transaction import ParsedTransaction
from app.services.categorizer import classify, record_correction
from app.services.chat_agent import run_chat
from app.services.ingest import upsert_transactions

logger = get_logger("api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    init_db()
    logger.info("startup_complete")
    yield


app = FastAPI(title="Sente", version="0.3.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Tag every request with an ID and log latency + status."""
    rid = new_request_id()
    t0 = time.perf_counter()
    request.state.request_id = rid
    try:
        response = await call_next(request)
    except Exception:
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.exception(
            "request_error",
            extra={
                "request_id": rid,
                "method": request.method,
                "path": request.url.path,
                "latency_ms": round(latency_ms, 1),
            },
        )
        raise
    latency_ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Request-ID"] = rid
    logger.info(
        "request",
        extra={
            "request_id": rid,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": round(latency_ms, 1),
        },
    )
    return response


# ---------- Request / response models ----------

class IngestTextRequest(BaseModel):
    messages: list[str]


class IngestResponse(BaseModel):
    parsed: int
    inserted: int
    merged: int
    skipped_no_change: int
    parser_stats: dict[str, Any]
    # PDF-only fields (None for text ingestion)
    customer_name: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    statement_total_credit: float | None = None
    statement_total_debit: float | None = None


class TransactionOut(BaseModel):
    id: int
    transaction_id: str | None
    timestamp: str
    type: str
    direction: str
    amount: float
    counterparty_name: str | None
    counterparty_number: str | None
    category: str
    category_confidence: float
    user_corrected: bool
    network: str

    @classmethod
    def from_orm_row(cls, t: Transaction) -> "TransactionOut":
        return cls(
            id=t.id,
            transaction_id=t.transaction_id,
            timestamp=t.timestamp.isoformat(),
            type=t.type,
            direction=t.direction,
            amount=float(t.amount),
            counterparty_name=t.counterparty_name,
            counterparty_number=t.counterparty_number,
            category=t.category,
            category_confidence=t.category_confidence,
            user_corrected=t.user_corrected,
            network=t.network,
        )


class CorrectionRequest(BaseModel):
    transaction_id: int    # internal DB id, not the telco TID
    category: Category


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]]


# ---------- Shared helpers ----------

def _categorize_and_persist(
    db: Session, parsed_items: list[ParsedTransaction]
) -> dict[str, Any]:
    """Upsert a batch, then categorize any newly-inserted or still-uncategorized rows."""
    ingest_result = upsert_transactions(db, parsed_items)

    # Only categorize rows that aren't user-corrected and have no category or "other"
    tids = [p.transaction_id for p in parsed_items if p.transaction_id]
    q = db.query(Transaction)
    if tids:
        q = q.filter(
            (Transaction.transaction_id.in_(tids))
            | (Transaction.user_corrected == False)  # noqa: E712
        )
    rows = q.filter(Transaction.user_corrected == False).all()  # noqa: E712

    for row in rows:
        if row.category and row.category != "other" and row.category_confidence > 0:
            continue
        # Reconstruct a ParsedTransaction for the categorizer
        from decimal import Decimal
        from datetime import datetime as _dt
        from app.schemas.transaction import (
            Direction as _D, Network as _N, ParseMethod as _P, TransactionType as _T,
        )
        pt = ParsedTransaction(
            transaction_id=row.transaction_id,
            timestamp=row.timestamp if isinstance(row.timestamp, _dt) else _dt.fromisoformat(str(row.timestamp)),
            type=_T(row.type),
            direction=_D(row.direction),
            amount=Decimal(str(row.amount)),
            counterparty_name=row.counterparty_name,
            counterparty_number=row.counterparty_number,
            agent_id=row.agent_id,
            reference=row.reference,
            fee=Decimal(str(row.fee)) if row.fee is not None else None,
            balance_after=Decimal(str(row.balance_after)) if row.balance_after is not None else None,
            network=_N(row.network),
            raw_message=row.raw_message,
            parse_method=_P(row.parse_method),
        )
        category, confidence = classify(db, pt)
        row.category = category.value
        row.category_confidence = confidence

    db.commit()
    return ingest_result.as_dict()


# ---------- Endpoints ----------

@app.get("/health")
def health():
    return {"ok": True}


@app.get("/metrics")
def metrics():
    """Snapshot of LLM call metrics. Useful for the demo and ongoing monitoring."""
    return {"llm": get_metrics_recorder().snapshot()}


@app.get("/categories")
def list_categories():
    return [{"key": c.value, "description": CATEGORY_DESCRIPTIONS[c]} for c in Category]


@app.post("/ingest/text", response_model=IngestResponse)
def ingest_text(req: IngestTextRequest, db: Session = Depends(get_db)) -> IngestResponse:
    parsed, parser_stats = parse_batch(req.messages)
    ingest = _categorize_and_persist(db, parsed)
    return IngestResponse(
        parsed=len(parsed),
        inserted=ingest["inserted"],
        merged=ingest["merged"],
        skipped_no_change=ingest["skipped_no_change"],
        parser_stats=parser_stats.as_dict(),
    )


@app.post("/ingest/pdf", response_model=IngestResponse)
async def ingest_pdf(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> IngestResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Expected a .pdf file")

    # Stream to a temp file; pdfplumber wants a path
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        metadata, transactions, stats = parse_statement(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    ingest = _categorize_and_persist(db, transactions)

    return IngestResponse(
        parsed=len(transactions),
        inserted=ingest["inserted"],
        merged=ingest["merged"],
        skipped_no_change=ingest["skipped_no_change"],
        parser_stats=stats.as_dict(),
        customer_name=metadata.customer_name,
        period_start=metadata.period_start.isoformat() if metadata.period_start else None,
        period_end=metadata.period_end.isoformat() if metadata.period_end else None,
        statement_total_credit=float(metadata.total_credit) if metadata.total_credit else None,
        statement_total_debit=float(metadata.total_debit) if metadata.total_debit else None,
    )


@app.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    limit: int = 100,
    offset: int = 0,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Transaction).order_by(Transaction.timestamp.desc())
    if category:
        q = q.filter(Transaction.category == category)
    rows = q.offset(offset).limit(limit).all()
    return [TransactionOut.from_orm_row(r) for r in rows]


@app.post("/transactions/correct")
def correct_category(req: CorrectionRequest, db: Session = Depends(get_db)):
    row = db.query(Transaction).filter(Transaction.id == req.transaction_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="transaction not found")

    previous_category = row.category
    row.category = req.category.value
    row.user_corrected = True
    row.category_confidence = 1.0
    db.commit()

    # Persist a learning-loop example
    from decimal import Decimal
    from datetime import datetime as _dt
    from app.schemas.transaction import (
        Direction as _D, Network as _N, ParseMethod as _P, TransactionType as _T,
    )
    pt = ParsedTransaction(
        transaction_id=row.transaction_id,
        timestamp=row.timestamp if isinstance(row.timestamp, _dt) else _dt.fromisoformat(str(row.timestamp)),
        type=_T(row.type),
        direction=_D(row.direction),
        amount=Decimal(str(row.amount)),
        counterparty_name=row.counterparty_name,
        counterparty_number=row.counterparty_number,
        agent_id=row.agent_id,
        reference=row.reference,
        fee=Decimal(str(row.fee)) if row.fee is not None else None,
        balance_after=Decimal(str(row.balance_after)) if row.balance_after is not None else None,
        network=_N(row.network),
        raw_message=row.raw_message,
        parse_method=_P(row.parse_method),
    )
    record_correction(db, pt, req.category)
    return {"ok": True, "previous": previous_category, "current": req.category.value}


@app.post("/chat")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    return run_chat(db, req.messages)
