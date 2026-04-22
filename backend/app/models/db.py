"""SQLAlchemy ORM models backing the SQLite store."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, Numeric, Boolean, Float, Text, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(8), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    currency: Mapped[str] = mapped_column(String(8), default="UGX")
    counterparty_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    counterparty_number: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fee: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    network: Mapped[str] = mapped_column(String(16), default="unknown")
    raw_message: Mapped[str] = mapped_column(Text)
    parse_method: Mapped[str] = mapped_column(String(16))

    # Categorization
    category: Mapped[str] = mapped_column(String(32), index=True, default="other")
    category_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    user_corrected: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CategoryExample(Base):
    """User-corrected transactions become few-shot examples for future classification.

    The embedding is stored so we can retrieve similar examples at classification
    time without recomputing.
    """
    __tablename__ = "category_examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), index=True)
    embedding: Mapped[bytes] = mapped_column()  # numpy bytes
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
