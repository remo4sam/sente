"""Regression test for the airtel_received_money template.

Added after the parser eval revealed this was missing on the synthetic corpus.
See evals/README.md.
"""
from decimal import Decimal

from app.parsers.regex_parser import try_regex_parse
from app.schemas.transaction import Direction, Network, ParsedTransaction, TransactionType


def test_received_money_variant():
    msg = "Received money UGX 189,500 from XENO INVESTMENT 0783290229. New Bal UGX 1,938,297. TID 307805919610. 27-March-2026 21:30"
    result = try_regex_parse(msg)
    assert isinstance(result, ParsedTransaction)
    assert result.type == TransactionType.RECEIVED
    assert result.direction == Direction.IN
    assert result.amount == Decimal("189500")
    assert result.counterparty_name == "XENO INVESTMENT"
    assert result.counterparty_number == "0783290229"
    assert result.balance_after == Decimal("1938297")
    assert result.transaction_id == "307805919610"
    assert result.network == Network.AIRTEL


def test_received_money_with_bal_instead_of_new_bal():
    """Some variants use 'Bal' rather than 'New Bal'."""
    msg = "Received money UGX 50,000 from DAD OPIO 0704841005. Bal UGX 123,500. TID 105240793782. 02-March-2026 13:37"
    result = try_regex_parse(msg)
    assert isinstance(result, ParsedTransaction)
    assert result.type == TransactionType.RECEIVED
    assert result.amount == Decimal("50000")
