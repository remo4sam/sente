"""Tests for the Airtel PDF statement importer.

Uses a real statement (committed as a test fixture) to verify:
  - Metadata extraction
  - Row count matches the statement's contents
  - Credit and debit totals reconcile with the PDF's own summary
  - Individual transaction shapes for a few representative rows

The fixture PDF lives in tests/fixtures/. It contains the user's real data
with no redaction — either commit a sanitized version or mark this test as
requiring a local fixture only.

Run:  cd backend && pytest tests/test_pdf_importer.py -v
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.parsers.pdf_importer import parse_description, parse_statement
from app.schemas.transaction import Direction, TransactionType


FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE_PDF = FIXTURE_DIR / "airtel_statement_march_2026.pdf"


pytestmark = pytest.mark.skipif(
    not FIXTURE_PDF.exists(),
    reason=f"Fixture PDF not found at {FIXTURE_PDF}. Copy your statement there to run.",
)


# ---------- Description parser unit tests ----------

@pytest.mark.parametrize(
    "desc, credit_debit, expected_type, expected_name, expected_number, expected_ref",
    [
        # Cash deposits (bank source)
        (
            "Received from 1121408 , SC BANK SC BANK",
            "Credit",
            TransactionType.DEPOSIT,
            "SC BANK",
            "1121408",
            None,
        ),
        (
            "Received from 1243688 , Bonna Gyaviira Morgan Bonna Gyaviira Morgan",
            "Credit",
            # No "BANK" in the source name -> treated as a P2P receive, not a deposit.
            TransactionType.RECEIVED,
            "Bonna Gyaviira Morgan",
            "1243688",
            None,
        ),
        # Other-network receive
        (
            "Received Money from 100105152. Sender TID 9427148860",
            "Credit",
            TransactionType.RECEIVED,
            None,
            "100105152",
            "9427148860",
        ),
        # P2P sends
        (
            "Sent Money to 740204439 , JOEL AKUMA",
            "Debit",
            TransactionType.SENT,
            "JOEL AKUMA",
            "740204439",
            None,
        ),
        (
            "Sent Money to . Receiving TID 6561053120",
            "Debit",
            TransactionType.SENT,
            None,
            None,
            "6561053120",
        ),
        # Airtime top-up (Prepaid Mobile App)
        (
            "Sent Money to 100000508 Prepaid Mobile App Prepaid Mobile App",
            "Debit",
            TransactionType.AIRTIME,
            "Prepaid Mobile App",
            None,
            None,
        ),
        # Paid to merchant
        (
            "Paid to 4391641 LA GATOS SERVICES LTD LA GATOS SERVICES LTD",
            "Debit",
            TransactionType.BILL_PAYMENT,
            "LA GATOS SERVICES LTD",
            None,
            None,
        ),
        # Paid to bundle
        (
            "Paid to 1097868 Data bundle Mobile App Data bundle Mobile App",
            "Debit",
            TransactionType.BUNDLE,
            "Data bundle Mobile App",
            None,
            None,
        ),
    ],
    ids=[
        "bank_deposit_sc",
        "p2p_receive_doubled_name",
        "received_money_sender_tid",
        "sent_named_recipient",
        "sent_anonymous",
        "airtime_prepaid",
        "paid_merchant",
        "paid_bundle",
    ],
)
def test_parse_description(desc, credit_debit, expected_type, expected_name, expected_number, expected_ref):
    fields = parse_description(desc, credit_debit)
    assert fields.tx_type == expected_type
    if expected_name is not None:
        assert fields.counterparty_name == expected_name
    if expected_number is not None:
        assert fields.counterparty_number == expected_number
    if expected_ref is not None:
        assert fields.external_tid == expected_ref


# ---------- End-to-end statement tests ----------

def test_parse_statement_fixture_returns_metadata():
    metadata, _txns, _stats = parse_statement(FIXTURE_PDF)
    assert metadata.customer_name == "Samuel Remo"
    assert metadata.mobile_number == "703901643"
    assert metadata.opening_balance == Decimal("25111.80")
    assert metadata.closing_balance == Decimal("73201.80")
    assert metadata.total_credit == Decimal("7040000.00")
    assert metadata.total_debit == Decimal("6991910.00")


def test_parse_statement_all_rows_parsed():
    _md, transactions, stats = parse_statement(FIXTURE_PDF)
    assert stats.rows_seen == 23
    assert stats.rows_parsed == 23
    assert stats.rows_failed == 0
    assert stats.rows_skipped == 0
    assert len(transactions) == 23


def test_totals_reconcile_with_pdf_summary():
    """The PDF's own 'Total Debit' includes fees; our sum of (amount+fee) must match."""
    metadata, transactions, _stats = parse_statement(FIXTURE_PDF)

    computed_credit = sum(t.amount for t in transactions if t.direction == Direction.IN)
    computed_debit = sum(
        (t.amount + (t.fee or Decimal(0))) for t in transactions if t.direction == Direction.OUT
    )

    assert computed_credit == metadata.total_credit
    assert computed_debit == metadata.total_debit


def test_no_unmatched_descriptions():
    """Every description in the fixture should match one of our template patterns."""
    _md, _txns, stats = parse_statement(FIXTURE_PDF)
    assert stats.unmatched_descriptions == []


def test_named_sends_extract_name_and_number():
    _md, transactions, _stats = parse_statement(FIXTURE_PDF)
    joel_sends = [t for t in transactions if t.counterparty_name == "JOEL AKUMA"]
    assert len(joel_sends) == 2
    assert all(t.counterparty_number == "740204439" for t in joel_sends)
    assert all(t.type == TransactionType.SENT for t in joel_sends)


def test_anonymous_sends_preserve_external_tid():
    _md, transactions, _stats = parse_statement(FIXTURE_PDF)
    anon = [t for t in transactions if t.type == TransactionType.SENT and t.counterparty_name is None]
    # There are 3 anonymous sends in March (TIDs 6561053120, 0661314048, 1758694720)
    assert len(anon) == 3
    assert all(t.reference is not None for t in anon)
    assert {"6561053120", "0661314048", "1758694720"} == {t.reference for t in anon}
