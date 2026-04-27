"""Regex-based fast-path parser for Airtel Money Uganda.

Templates are derived from real SMS exports. Anything that doesn't match here
falls through to the LLM parser in llm_parser.py.

Template coverage:
  - airtel_cash_deposit     CASH DEPOSIT of UGX X from Y. Bal UGX Z. TID T. date time
  - airtel_paid             PAID.TID T. UGX X to MERCHANT Charge UGX F. Bal UGX Z. date time
  - airtel_sent             SENT.TID T. UGX X to NAME NUMBER. Fee UGX F. Bal UGX Z. Date date time.
  - airtel_withdrawn        WITHDRAWN. TID T. UGXX with Agent ID: A.Fee UGX F.Tax UGX T2.Bal UGX Z. date time
  - airtel_debited_app      You have been debited UGX X. Fee UGX F. Bal UGX Z. TID T. Send using MyAirtel App
  - airtel_topup_outgoing   Top up of UGX X for NUMBER. Bal : UGX Z.
  - airtel_airtime_received You have received Airtime Topup of UGX X from NAME.
  - airtel_withdrawal_otp   Withdrawal of UGX X initiated. Secret Code: C. (pending, parse as OTHER and skip)
  - airtel_failed           FAILED. TID T reason (parse as OTHER and skip)

MTN templates to be added once we have real MTN samples.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Callable, Optional

from dateutil import parser as dtparser

from app.schemas.transaction import (
    Direction,
    Network,
    ParseMethod,
    ParsedTransaction,
    TransactionType,
)


# ---------- Helpers ----------

# Amounts: "UGX 1,234" OR "UGX1234" OR "UGX 1234". We strip commas and spaces.
_AMOUNT_RE = r"UGX\s*(?P<{name}>[\d,]+)"

# Timestamps seen in Airtel exports:
#   "15-March-2026 02:01"
#   "22-March-2026 12:37."
#   "Date 22-March-2026 12:37."
#   "04-March-2026 18:18"
# dateutil.parse handles all of these once we strip a trailing period.
_DATE_RE = r"(?P<{name}>\d{{1,2}}-[A-Za-z]+-\d{{4}}\s+\d{{1,2}}:\d{{2}}(?::\d{{2}})?)"


def _amt(s: Optional[str]) -> Optional[Decimal]:
    if s is None:
        return None
    cleaned = s.replace(",", "").strip()
    if not cleaned:
        return None
    return Decimal(cleaned)


def _ts(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    return dtparser.parse(s.strip().rstrip("."), dayfirst=True)


def _dedupe_doubled(name: Optional[str]) -> Optional[str]:
    """Airtel sometimes duplicates source names: 'SC BANK SC BANK' -> 'SC BANK'."""
    if not name:
        return name
    stripped = name.strip()
    tokens = stripped.split()
    n = len(tokens)
    # Check even-length names where first half == second half
    if n >= 2 and n % 2 == 0 and tokens[: n // 2] == tokens[n // 2 :]:
        return " ".join(tokens[: n // 2])
    return stripped


def _clean_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return _dedupe_doubled(name.strip()) or None


@dataclass
class Template:
    name: str
    network: Network
    pattern: re.Pattern
    builder: Callable[[re.Match, str], Optional[ParsedTransaction]]


# ---------- Airtel: CASH DEPOSIT ----------
# CASH DEPOSIT of UGX 200,000 from  SC BANK SC BANK. Bal UGX 228,702. TID 142853569804. 15-March-2026 02:01

_AIRTEL_CASH_DEPOSIT = re.compile(
    r"""CASH\s+DEPOSIT\s+of\s+UGX\s+(?P<amount>[\d,]+)\s+from\s+
        (?P<source>.+?)\.\s*
        Bal\s+UGX\s+(?P<balance>[\d,]+)\.\s*
        TID\s+(?P<tid>\w+)\.\s*
        (?P<ts>\d{1,2}-[A-Za-z]+-\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _build_airtel_cash_deposit(m: re.Match, raw: str) -> ParsedTransaction:
    source = _clean_name(m.group("source"))
    return ParsedTransaction(
        transaction_id=m.group("tid"),
        timestamp=_ts(m.group("ts")) or datetime.utcnow(),
        type=TransactionType.DEPOSIT,
        direction=Direction.IN,
        amount=_amt(m.group("amount")),
        counterparty_name=source,
        balance_after=_amt(m.group("balance")),
        network=Network.AIRTEL,
        raw_message=raw,
        parse_method=ParseMethod.REGEX,
    )


# ---------- Airtel: PAID (merchant) ----------
# PAID.TID 142853590171. UGX 179,000 to LA GATOS SERVICES LTD Charge UGX 0. Bal UGX 49,702. 15-March-2026 02:04

_AIRTEL_PAID = re.compile(
    r"""PAID\.\s*TID\s+(?P<tid>\w+)\.\s*
        UGX\s+(?P<amount>[\d,]+)\s+to\s+
        (?P<merchant>.+?)\s+Charge\s+UGX\s+(?P<fee>[\d,]+)\.\s*
        Bal\s+UGX\s+(?P<balance>[\d,]+)\.\s*
        (?P<ts>\d{1,2}-[A-Za-z]+-\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _build_airtel_paid(m: re.Match, raw: str) -> ParsedTransaction:
    merchant = _clean_name(m.group("merchant"))
    # Disambiguate bundle/data payments from generic merchant payments.
    tx_type = TransactionType.BUNDLE if merchant and "bundle" in merchant.lower() else TransactionType.BILL_PAYMENT
    return ParsedTransaction(
        transaction_id=m.group("tid"),
        timestamp=_ts(m.group("ts")) or datetime.utcnow(),
        type=tx_type,
        direction=Direction.OUT,
        amount=_amt(m.group("amount")),
        counterparty_name=merchant,
        fee=_amt(m.group("fee")),
        balance_after=_amt(m.group("balance")),
        network=Network.AIRTEL,
        raw_message=raw,
        parse_method=ParseMethod.REGEX,
    )


# ---------- Airtel: SENT (P2P) ----------
# SENT.TID 142103669037. UGX 45,000 to JOEL AKUMA  0740204439. Fee UGX 500. Bal UGX 5,979,612. Date 04-March-2026 19:18.

_AIRTEL_SENT = re.compile(
    r"""SENT\.\s*TID\s+(?P<tid>\w+)\.\s*
        UGX\s+(?P<amount>[\d,]+)\s+to\s+
        (?P<name>.+?)\s+(?P<number>\d{9,12})\.\s*
        Fee\s+UGX\s+(?P<fee>[\d,]+)\.\s*
        Bal\s+UGX\s+(?P<balance>[\d,]+)\.\s*
        Date\s+(?P<ts>\d{1,2}-[A-Za-z]+-\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _build_airtel_sent(m: re.Match, raw: str) -> ParsedTransaction:
    return ParsedTransaction(
        transaction_id=m.group("tid"),
        timestamp=_ts(m.group("ts")) or datetime.utcnow(),
        type=TransactionType.SENT,
        direction=Direction.OUT,
        amount=_amt(m.group("amount")),
        counterparty_name=_clean_name(m.group("name")),
        counterparty_number=m.group("number"),
        fee=_amt(m.group("fee")),
        balance_after=_amt(m.group("balance")),
        network=Network.AIRTEL,
        raw_message=raw,
        parse_method=ParseMethod.REGEX,
    )


# ---------- Airtel: WITHDRAWN (agent cashout) ----------
# WITHDRAWN. TID 143251777870. UGX400,000 with Agent ID: 678447.Fee UGX 7,000.Tax UGX 2,000.Bal UGX 40,702. 20-March-2026 13:33.

_AIRTEL_WITHDRAWN = re.compile(
    r"""WITHDRAWN\.\s*TID\s+(?P<tid>\w+)\.\s*
        UGX\s*(?P<amount>[\d,]+)\s+with\s+Agent\s+ID:\s*(?P<agent>\d+)\.\s*
        Fee\s+UGX\s+(?P<fee>[\d,]+)\.\s*
        (?:Tax\s+UGX\s+(?P<tax>[\d,]+)\.\s*)?
        Bal\s+UGX\s+(?P<balance>[\d,]+)\.\s*
        (?P<ts>\d{1,2}-[A-Za-z]+-\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _build_airtel_withdrawn(m: re.Match, raw: str) -> ParsedTransaction:
    # Combine Fee + Tax into fee field; we could split it later if we care.
    fee = _amt(m.group("fee")) or Decimal(0)
    tax = _amt(m.group("tax")) if m.group("tax") else None
    if tax:
        fee = fee + tax
    return ParsedTransaction(
        transaction_id=m.group("tid"),
        timestamp=_ts(m.group("ts")) or datetime.utcnow(),
        type=TransactionType.WITHDRAW,
        direction=Direction.OUT,
        amount=_amt(m.group("amount")),
        agent_id=m.group("agent"),
        fee=fee,
        balance_after=_amt(m.group("balance")),
        network=Network.AIRTEL,
        raw_message=raw,
        parse_method=ParseMethod.REGEX,
    )


# ---------- Airtel: DEBITED (app send, no recipient) ----------
# You have been debited UGX 75,000. Fee UGX 1,000. Bal UGX 53,702. TID 143416174774.Send using MyAirtel App https://...

_AIRTEL_DEBITED = re.compile(
    r"""You\s+have\s+been\s+debited\s+UGX\s+(?P<amount>[\d,]+)\.\s*
        Fee\s+UGX\s+(?P<fee>[\d,]+)\.\s*
        Bal\s+UGX\s+(?P<balance>[\d,]+)\.\s*
        TID\s+(?P<tid>\w+)\.\s*
        Send\s+using\s+MyAirtel\s+App
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _build_airtel_debited(m: re.Match, raw: str) -> ParsedTransaction:
    return ParsedTransaction(
        transaction_id=m.group("tid"),
        timestamp=datetime.utcnow(),  # no timestamp in message; will be overridden by SMS receive time in XML import
        type=TransactionType.SENT,
        direction=Direction.OUT,
        amount=_amt(m.group("amount")),
        counterparty_name=None,  # message drops the recipient
        fee=_amt(m.group("fee")),
        balance_after=_amt(m.group("balance")),
        network=Network.AIRTEL,
        raw_message=raw,
        parse_method=ParseMethod.REGEX,
    )


# ---------- Airtel: Airtime top-up outgoing ----------
# Top up of UGX 10,000 for 0758152159. Bal : UGX 30,702.

_AIRTEL_TOPUP_OUT = re.compile(
    r"""Top\s+up\s+of\s+UGX\s+(?P<amount>[\d,]+)\s+for\s+(?P<number>\d{9,12})\.\s*
        Bal\s*:\s*UGX\s+(?P<balance>[\d,]+)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _build_airtel_topup_out(m: re.Match, raw: str) -> ParsedTransaction:
    return ParsedTransaction(
        transaction_id=None,
        timestamp=datetime.utcnow(),  # no timestamp; will be overridden from SMS receive time
        type=TransactionType.AIRTIME,
        direction=Direction.OUT,
        amount=_amt(m.group("amount")),
        counterparty_number=m.group("number"),
        balance_after=_amt(m.group("balance")),
        network=Network.AIRTEL,
        raw_message=raw,
        parse_method=ParseMethod.REGEX,
    )


# ---------- Airtel: Airtime received ----------
# You have received Airtime Topup of UGX 3,000 from ELVIN ISAAC. Dial *185# ...

_AIRTEL_AIRTIME_IN = re.compile(
    r"""You\s+have\s+received\s+Airtime\s+Topup\s+of\s+UGX\s+(?P<amount>[\d,]+)\s+from\s+
        (?P<name>[^.]+?)\.\s*(?:Dial|$)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _build_airtel_airtime_in(m: re.Match, raw: str) -> ParsedTransaction:
    return ParsedTransaction(
        transaction_id=None,
        timestamp=datetime.utcnow(),
        type=TransactionType.AIRTIME,
        direction=Direction.IN,
        amount=_amt(m.group("amount")),
        counterparty_name=_clean_name(m.group("name")),
        network=Network.AIRTEL,
        raw_message=raw,
        parse_method=ParseMethod.REGEX,
    )


# ---------- Airtel: Withdrawal initiated (OTP — NOT a real transaction) ----------
# Withdrawal of UGX 400000 initiated. Secret Code: 189037. Expires on 20-March-2026 13:35.

_AIRTEL_WITHDRAW_OTP = re.compile(
    r"""Withdrawal\s+of\s+UGX\s*(?P<amount>[\d,]+)\s+initiated\.\s*
        Secret\s+Code:
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _build_airtel_withdraw_otp(m: re.Match, raw: str) -> Optional[ParsedTransaction]:
    """OTP notices are not real transactions. Return None so they are skipped."""
    return None


# ---------- Airtel: FAILED ----------
# FAILED. TID 142209904941 Amount entered is not within the allowed range.

_AIRTEL_FAILED = re.compile(r"^FAILED\.\s*TID\s+\w+", re.IGNORECASE)


def _build_airtel_failed(m: re.Match, raw: str) -> Optional[ParsedTransaction]:
    """Failed-transaction notices are skipped."""
    return None


# ---------- Airtel: "Received money UGX ... from NAME NUMBER" ----------
# Variant of RECEIVED that shows up in some message formats (and in the
# synthetic corpus). Keep this below RECEIVED variants with more structure.

_AIRTEL_RECEIVED_MONEY = re.compile(
    r"""Received\s+money\s+UGX\s+(?P<amount>[\d,]+)\s+from\s+
        (?P<n>.+?)\s+(?P<number>\d{9,12})\.\s*
        (?:New\s+Bal|Bal)\s+UGX\s+(?P<balance>[\d,]+)\.\s*
        TID\s+(?P<tid>\w+)\.\s*
        (?P<ts>\d{1,2}-[A-Za-z]+-\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _build_airtel_received_money(m: re.Match, raw: str) -> ParsedTransaction:
    return ParsedTransaction(
        transaction_id=m.group("tid"),
        timestamp=_ts(m.group("ts")) or datetime.utcnow(),
        type=TransactionType.RECEIVED,
        direction=Direction.IN,
        amount=_amt(m.group("amount")),
        counterparty_name=_clean_name(m.group("n")),
        counterparty_number=m.group("number"),
        balance_after=_amt(m.group("balance")),
        network=Network.AIRTEL,
        raw_message=raw,
        parse_method=ParseMethod.REGEX,
    )


# ---------- Template registry ----------
# Order matters: more specific patterns first. DEBITED must come before anything
# that could weakly match 'You have been'.

TEMPLATES: list[Template] = [
    Template("airtel_failed", Network.AIRTEL, _AIRTEL_FAILED, _build_airtel_failed),
    Template("airtel_withdraw_otp", Network.AIRTEL, _AIRTEL_WITHDRAW_OTP, _build_airtel_withdraw_otp),
    Template("airtel_cash_deposit", Network.AIRTEL, _AIRTEL_CASH_DEPOSIT, _build_airtel_cash_deposit),
    Template("airtel_paid", Network.AIRTEL, _AIRTEL_PAID, _build_airtel_paid),
    Template("airtel_sent", Network.AIRTEL, _AIRTEL_SENT, _build_airtel_sent),
    Template("airtel_withdrawn", Network.AIRTEL, _AIRTEL_WITHDRAWN, _build_airtel_withdrawn),
    Template("airtel_debited", Network.AIRTEL, _AIRTEL_DEBITED, _build_airtel_debited),
    Template("airtel_topup_out", Network.AIRTEL, _AIRTEL_TOPUP_OUT, _build_airtel_topup_out),
    Template("airtel_airtime_in", Network.AIRTEL, _AIRTEL_AIRTIME_IN, _build_airtel_airtime_in),
    Template("airtel_received_money", Network.AIRTEL, _AIRTEL_RECEIVED_MONEY, _build_airtel_received_money),
    # TODO: add MTN equivalents once we have MTN samples
]


# ---------- Orchestrator entry point ----------

class ParseOutcome:
    """Marker values returned from try_regex_parse."""
    # A successful parse returns a ParsedTransaction
    # A deliberate skip (OTP, FAILED) returns SKIP
    # No match returns None
    SKIP = "skip"


def try_regex_parse(message: str) -> Optional[ParsedTransaction] | str:
    """Return:
      - ParsedTransaction on successful match
      - ParseOutcome.SKIP if matched a 'skip this' template (OTP, FAILED)
      - None if no template matched
    """
    for tpl in TEMPLATES:
        m = tpl.pattern.search(message)
        if m:
            try:
                result = tpl.builder(m, message)
            except (ValueError, KeyError, TypeError):
                continue
            if result is None:
                return ParseOutcome.SKIP
            return result
    return None


def list_templates() -> list[str]:
    """Useful for debugging and eval reports."""
    return [t.name for t in TEMPLATES]
