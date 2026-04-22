"""Normalized transaction schema.

This is the canonical shape every transaction takes once it's past the parser,
regardless of input format (SMS XML, PDF statement, CSV, pasted text).
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.data.taxonomy import Category


class TransactionType(str, Enum):
    SENT = "sent"
    RECEIVED = "received"
    WITHDRAW = "withdraw"
    DEPOSIT = "deposit"
    BILL_PAYMENT = "bill_payment"
    AIRTIME = "airtime"
    BUNDLE = "bundle"
    LOAN_TAKEN = "loan_taken"
    LOAN_REPAID = "loan_repaid"
    SAVINGS_DEPOSIT = "savings_deposit"
    SAVINGS_WITHDRAW = "savings_withdraw"
    FEE = "fee"
    REVERSAL = "reversal"
    OTHER = "other"


class Direction(str, Enum):
    IN = "in"
    OUT = "out"


class Network(str, Enum):
    MTN = "MTN"
    AIRTEL = "Airtel"
    UNKNOWN = "unknown"


class ParseMethod(str, Enum):
    REGEX = "regex"
    LLM = "llm"
    MANUAL = "manual"


class ParsedTransaction(BaseModel):
    """What the parser emits. Categorization happens downstream."""

    transaction_id: Optional[str] = Field(None, description="Telco reference ID")
    timestamp: datetime
    type: TransactionType
    direction: Direction
    amount: Decimal
    currency: str = "UGX"
    counterparty_name: Optional[str] = None
    counterparty_number: Optional[str] = None
    agent_id: Optional[str] = None
    reference: Optional[str] = None
    fee: Optional[Decimal] = None
    balance_after: Optional[Decimal] = None
    network: Network = Network.UNKNOWN
    raw_message: str
    parse_method: ParseMethod


class EnrichedTransaction(ParsedTransaction):
    """Parsed transaction with a predicted category and confidence."""

    category: Category
    category_confidence: float = Field(ge=0.0, le=1.0)
    user_corrected: bool = False
