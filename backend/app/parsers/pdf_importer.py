"""PDF statement parser for Airtel Money Uganda.

Complements the SMS parser. Unlike SMS, statements provide:
  - The canonical transaction timestamp for EVERY row
  - Named recipients for some transactions that SMS leaves as "Sent Money to ."
  - A reconciled view (fee, balance-after, status) that matches telco records

Extraction strategy:
  1. pdfplumber for tabular extraction (fast, deterministic, free)
  2. Regex over the `Description` column to identify transaction type
  3. Fall through to LLM parser only for descriptions no pattern recognizes

Dedup: when SMS and PDF cover the same period, we dedupe by transaction_id
at the ingestion layer (see services/ingest.py).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterator, Optional

import pdfplumber
from dateutil import parser as dtparser

from app.schemas.transaction import (
    Direction,
    Network,
    ParseMethod,
    ParsedTransaction,
    TransactionType,
)

logger = logging.getLogger(__name__)


# ---------- Metadata extraction ----------

@dataclass
class StatementMetadata:
    customer_name: Optional[str] = None
    mobile_number: Optional[str] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    total_credit: Optional[Decimal] = None
    total_debit: Optional[Decimal] = None


_META_PATTERNS = {
    "customer_name": re.compile(r"Customer\s+Name:\s*(?P<v>[^\n]+)", re.IGNORECASE),
    "mobile_number": re.compile(r"Mobile\s+Number:\s*(?P<v>\d+)", re.IGNORECASE),
    "period": re.compile(r"Statement\s+Period:\s*(?P<start>[^\s]+)\s+to\s+(?P<end>[^\s\n]+)", re.IGNORECASE),
    "opening": re.compile(r"Opening\s+Balance:\s*Ugx\s*(?P<v>[\d,.]+)", re.IGNORECASE),
    "closing": re.compile(r"Closing\s+Balance:\s*Ugx\s*(?P<v>[\d,.]+)", re.IGNORECASE),
    "credit": re.compile(r"Total\s+Credit:\s*Ugx\s*(?P<v>[\d,.]+)", re.IGNORECASE),
    "debit": re.compile(r"Total\s+Debit:\s*Ugx\s*(?P<v>[\d,.]+)", re.IGNORECASE),
}


def _parse_decimal(s: str) -> Decimal:
    return Decimal(s.replace(",", "").strip())


def extract_metadata(text: str) -> StatementMetadata:
    md = StatementMetadata()
    if m := _META_PATTERNS["customer_name"].search(text):
        md.customer_name = m.group("v").strip()
    if m := _META_PATTERNS["mobile_number"].search(text):
        md.mobile_number = m.group("v").strip()
    if m := _META_PATTERNS["period"].search(text):
        try:
            md.period_start = dtparser.parse(m.group("start"), dayfirst=True)
            md.period_end = dtparser.parse(m.group("end"), dayfirst=True)
        except (ValueError, dtparser.ParserError):
            pass
    if m := _META_PATTERNS["opening"].search(text):
        md.opening_balance = _parse_decimal(m.group("v"))
    if m := _META_PATTERNS["closing"].search(text):
        md.closing_balance = _parse_decimal(m.group("v"))
    if m := _META_PATTERNS["credit"].search(text):
        md.total_credit = _parse_decimal(m.group("v"))
    if m := _META_PATTERNS["debit"].search(text):
        md.total_debit = _parse_decimal(m.group("v"))
    return md


# ---------- Description parser ----------
# The Description column compactly encodes transaction type. Patterns seen:
#
#   Received from {account_num} , {NAME doubled or SC BANK SC BANK}
#   Received Money from {account_num}. Sender TID {tid}
#   Sent Money to {msisdn} , {NAME}
#   Sent Money to . Receiving TID {tid}          (no named recipient)
#   Sent Money to {account_num} {merchant doubled}   (app-level send)
#   Paid to {merchant_code} {MERCHANT NAME doubled}


_DESC_RECEIVED_FROM = re.compile(
    r"""^Received\s+from\s+(?P<account>\S+)\s*,\s*(?P<source>.+)$""",
    re.IGNORECASE | re.DOTALL,
)
_DESC_RECEIVED_MONEY_FROM = re.compile(
    r"""^Received\s+Money\s+from\s+(?P<account>\S+?)\.\s*Sender\s+TID\s+(?P<tid>\w+)""",
    re.IGNORECASE | re.DOTALL,
)
_DESC_SENT_NAMED = re.compile(
    r"""^Sent\s+Money\s+to\s+(?P<msisdn>\d{6,})\s*,\s*(?P<n>.+)$""",
    re.IGNORECASE | re.DOTALL,
)
_DESC_SENT_UNNAMED = re.compile(
    r"""^Sent\s+Money\s+to\s*\.\s*Receiving\s+TID\s+(?P<tid>\w+)""",
    re.IGNORECASE | re.DOTALL,
)
_DESC_SENT_MERCHANT = re.compile(
    r"""^Sent\s+Money\s+to\s+(?P<account>\d{6,})\s+(?P<merchant>.+)$""",
    re.IGNORECASE | re.DOTALL,
)
_DESC_PAID = re.compile(
    r"""^Paid\s+to\s+(?P<code>\S+)\s+(?P<merchant>.+)$""",
    re.IGNORECASE | re.DOTALL,
)


def _collapse_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _dedupe_doubled(name: Optional[str]) -> Optional[str]:
    """Airtel doubles many name fields: 'SC BANK SC BANK' -> 'SC BANK'."""
    if not name:
        return name
    stripped = name.strip()
    tokens = stripped.split()
    n = len(tokens)
    if n >= 2 and n % 2 == 0 and tokens[: n // 2] == tokens[n // 2 :]:
        return " ".join(tokens[: n // 2])
    return stripped


@dataclass
class DescriptionFields:
    tx_type: TransactionType
    counterparty_name: Optional[str] = None
    counterparty_number: Optional[str] = None
    external_tid: Optional[str] = None  # counterparty-side TID when present


def parse_description(desc: str, credit_debit: str) -> DescriptionFields:
    """Parse the Description cell. Uses the Credit/Debit column to disambiguate."""
    desc_flat = _collapse_whitespace(desc)
    is_credit = credit_debit.strip().lower() == "credit"

    if is_credit:
        if m := _DESC_RECEIVED_MONEY_FROM.match(desc_flat):
            return DescriptionFields(
                tx_type=TransactionType.RECEIVED,
                counterparty_number=m.group("account"),
                external_tid=m.group("tid"),
            )
        if m := _DESC_RECEIVED_FROM.match(desc_flat):
            source = _dedupe_doubled(m.group("source"))
            # Heuristic: an all-caps "BANK" in the source => it's a deposit
            tx_type = (
                TransactionType.DEPOSIT
                if source and "BANK" in source.upper()
                else TransactionType.RECEIVED
            )
            return DescriptionFields(
                tx_type=tx_type,
                counterparty_name=source,
                counterparty_number=m.group("account"),
            )
        return DescriptionFields(tx_type=TransactionType.RECEIVED)

    # Debit branch
    if m := _DESC_PAID.match(desc_flat):
        merchant = _dedupe_doubled(m.group("merchant"))
        tx_type = (
            TransactionType.BUNDLE
            if merchant and "bundle" in merchant.lower()
            else TransactionType.BILL_PAYMENT
        )
        return DescriptionFields(tx_type=tx_type, counterparty_name=merchant)
    if m := _DESC_SENT_UNNAMED.match(desc_flat):
        return DescriptionFields(
            tx_type=TransactionType.SENT,
            external_tid=m.group("tid"),
        )
    if m := _DESC_SENT_NAMED.match(desc_flat):
        return DescriptionFields(
            tx_type=TransactionType.SENT,
            counterparty_name=_dedupe_doubled(m.group("n")),
            counterparty_number=m.group("msisdn"),
        )
    if m := _DESC_SENT_MERCHANT.match(desc_flat):
        merchant = _dedupe_doubled(m.group("merchant"))
        tx_type = (
            TransactionType.AIRTIME
            if merchant and ("prepaid" in merchant.lower() or "airtime" in merchant.lower())
            else TransactionType.BILL_PAYMENT
        )
        return DescriptionFields(tx_type=tx_type, counterparty_name=merchant)

    return DescriptionFields(tx_type=TransactionType.OTHER)


# ---------- Row -> ParsedTransaction ----------

@dataclass
class ImportStats:
    pages: int = 0
    rows_seen: int = 0
    rows_parsed: int = 0
    rows_skipped: int = 0  # non-successful status
    rows_failed: int = 0
    unmatched_descriptions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "pages": self.pages,
            "rows_seen": self.rows_seen,
            "rows_parsed": self.rows_parsed,
            "rows_skipped": self.rows_skipped,
            "rows_failed": self.rows_failed,
            "unmatched_descriptions": self.unmatched_descriptions[:10],
        }


def _row_to_transaction(row: list[str]) -> Optional[ParsedTransaction]:
    """Convert a raw table row to a ParsedTransaction, or None to skip."""
    if len(row) < 8:
        return None
    tid, date_str, desc, status, amount_str, credit_debit, fee_str, balance_str = row[:8]

    if not status or "success" not in status.lower():
        return None

    try:
        ts = dtparser.parse(date_str.strip(), dayfirst=True)
    except (ValueError, dtparser.ParserError):
        logger.warning("Failed to parse date %r in row %r", date_str, tid)
        return None

    fields = parse_description(desc, credit_debit)

    direction = Direction.IN if credit_debit.strip().lower() == "credit" else Direction.OUT

    return ParsedTransaction(
        transaction_id=(tid or "").strip() or None,
        timestamp=ts,
        type=fields.tx_type,
        direction=direction,
        amount=_parse_decimal(amount_str),
        counterparty_name=fields.counterparty_name,
        counterparty_number=fields.counterparty_number,
        reference=fields.external_tid,
        fee=_parse_decimal(fee_str) if fee_str and fee_str.strip() else None,
        balance_after=_parse_decimal(balance_str) if balance_str and balance_str.strip() else None,
        network=Network.AIRTEL,
        raw_message=_collapse_whitespace(f"[PDF row] tid={tid} | {desc} | {amount_str} {credit_debit}"),
        parse_method=ParseMethod.REGEX,
    )


# ---------- Public entry point ----------

def parse_statement(
    pdf_path: str | Path,
) -> tuple[StatementMetadata, list[ParsedTransaction], ImportStats]:
    """Extract metadata and transactions from an Airtel PDF statement."""
    stats = ImportStats()
    transactions: list[ParsedTransaction] = []

    with pdfplumber.open(pdf_path) as pdf:
        stats.pages = len(pdf.pages)

        # Metadata from page 1 text
        page1_text = pdf.pages[0].extract_text() or ""
        metadata = extract_metadata(page1_text)

        # Transactions from every page's tables
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table or len(table) < 2:
                    continue
                header = [(c or "").strip() for c in table[0]]
                if "Transaction ID" not in header:
                    continue  # skip the summary table on page 1
                for raw_row in table[1:]:
                    row = [(c or "").strip() for c in raw_row]
                    stats.rows_seen += 1
                    try:
                        tx = _row_to_transaction(row)
                    except Exception:
                        logger.exception("Row parse error: %r", row)
                        stats.rows_failed += 1
                        continue
                    if tx is None:
                        stats.rows_skipped += 1
                        continue
                    transactions.append(tx)
                    stats.rows_parsed += 1
                    if tx.type == TransactionType.OTHER and len(row) > 2:
                        stats.unmatched_descriptions.append(row[2])

    return metadata, transactions, stats


def iter_pages_as_markdown(pdf_path: str | Path) -> Iterator[str]:
    """Utility for debugging: yield a markdown-ish dump of each page's tables."""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            out = [f"## Page {i + 1}"]
            for t_idx, table in enumerate(page.extract_tables()):
                out.append(f"### Table {t_idx}")
                for row in table:
                    out.append(" | ".join((c or "").strip() for c in row))
            yield "\n".join(out)
