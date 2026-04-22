"""Ingestion: insert parsed transactions into the DB with dedupe and merge.

Why we need this:
  SMS and PDF statements describe the same transactions with different details.
  - PDF has: canonical timestamps, named recipients on some sends
  - SMS has: agent IDs on withdrawals, more granular fee/tax breakdown

So ingestion is an UPSERT keyed on transaction_id, merging fields.

Rules (simple, deterministic):
  - If a row with the same transaction_id already exists:
      * Fill in missing (None) fields from the new record
      * Prefer the non-None value when both have it, with a source preference:
        - timestamp:  PDF > SMS (PDF timestamps are canonical)
        - counterparty_name: whichever is non-None; on conflict, prefer the
          longer string (PDF sometimes has fuller names)
        - agent_id:   SMS wins (PDF drops this)
        - fee:        prefer non-None; on conflict, keep existing
  - If no existing row, insert.

Transactions with no transaction_id (airtime top-ups, received airtime) cannot
be deduped — they're always inserted. This is acceptable since these messages
typically don't appear in PDF statements anyway.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.db import Transaction
from app.schemas.transaction import ParsedTransaction


@dataclass
class IngestResult:
    inserted: int = 0
    merged: int = 0
    skipped_no_change: int = 0

    def as_dict(self) -> dict:
        return {
            "inserted": self.inserted,
            "merged": self.merged,
            "skipped_no_change": self.skipped_no_change,
            "total": self.inserted + self.merged + self.skipped_no_change,
        }


def _prefer_longer(a: str | None, b: str | None) -> str | None:
    """Return the non-None string; if both non-None, return the longer one."""
    if a is None:
        return b
    if b is None:
        return a
    return a if len(a) >= len(b) else b


def _merge_into(existing: Transaction, incoming: ParsedTransaction) -> bool:
    """Merge `incoming` into `existing` in-place. Returns True if anything changed."""
    changed = False

    # Timestamps: PDF tends to be canonical. PDF rows are marked by raw_message
    # starting with "[PDF row]". Prefer PDF timestamp when available.
    is_pdf = incoming.raw_message.startswith("[PDF row]")
    if is_pdf and existing.timestamp != incoming.timestamp:
        existing.timestamp = incoming.timestamp
        changed = True

    # Names: prefer longer non-None
    new_name = _prefer_longer(existing.counterparty_name, incoming.counterparty_name)
    if new_name != existing.counterparty_name:
        existing.counterparty_name = new_name
        changed = True

    # Numbers: fill in if missing
    if existing.counterparty_number is None and incoming.counterparty_number:
        existing.counterparty_number = incoming.counterparty_number
        changed = True

    # Agent ID: SMS-only, fill in if missing
    if existing.agent_id is None and incoming.agent_id:
        existing.agent_id = incoming.agent_id
        changed = True

    # Reference (external TID): fill in if missing
    if existing.reference is None and incoming.reference:
        existing.reference = incoming.reference
        changed = True

    # Fee / balance: fill in if missing (but don't overwrite)
    if existing.fee is None and incoming.fee is not None:
        existing.fee = incoming.fee
        changed = True
    if existing.balance_after is None and incoming.balance_after is not None:
        existing.balance_after = incoming.balance_after
        changed = True

    return changed


def upsert_transactions(
    db: Session, transactions: Iterable[ParsedTransaction]
) -> IngestResult:
    """Insert or merge a batch of parsed transactions."""
    result = IngestResult()

    for pt in transactions:
        existing = None
        if pt.transaction_id:
            existing = (
                db.query(Transaction)
                .filter(Transaction.transaction_id == pt.transaction_id)
                .first()
            )

        if existing is None:
            row = Transaction(
                transaction_id=pt.transaction_id,
                timestamp=pt.timestamp,
                type=pt.type.value,
                direction=pt.direction.value,
                amount=pt.amount,
                currency=pt.currency,
                counterparty_name=pt.counterparty_name,
                counterparty_number=pt.counterparty_number,
                agent_id=pt.agent_id,
                reference=pt.reference,
                fee=pt.fee,
                balance_after=pt.balance_after,
                network=pt.network.value,
                raw_message=pt.raw_message,
                parse_method=pt.parse_method.value,
                # Categorization fields set to placeholders; categorizer fills them in.
                category="other",
                category_confidence=0.0,
            )
            db.add(row)
            result.inserted += 1
        else:
            if _merge_into(existing, pt):
                result.merged += 1
            else:
                result.skipped_no_change += 1

    db.commit()
    return result
