"""Tools the chat agent can invoke against the transaction store.

Design principle: each tool is narrow, its parameters are typed, and its output
is already shaped for the LLM to reason over (pre-aggregated when appropriate).
The LLM should never see raw rows it doesn't need — that wastes tokens and
tempts hallucination.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, desc
from sqlalchemy.orm import Session

from app.models.db import Transaction


def _date_range(period: str | None) -> tuple[datetime | None, datetime | None]:
    """Resolve human-friendly period strings to (start, end). None = open-ended."""
    if not period:
        return None, None
    now = datetime.utcnow()
    p = period.lower().strip()
    if p in ("this_month", "current_month"):
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if p == "last_month":
        first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = first_this - timedelta(seconds=1)
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, end
    if p == "last_7_days":
        return now - timedelta(days=7), now
    if p == "last_30_days":
        return now - timedelta(days=30), now
    if p == "last_90_days":
        return now - timedelta(days=90), now
    if p == "this_year":
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0), now
    if p == "last_year":
        start = now.replace(year=now.year - 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
        return start, end
    return None, None


def tool_query_transactions(
    db: Session,
    category: str | None = None,
    direction: str | None = None,
    period: str | None = None,
    min_amount: float | None = None,
    counterparty: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    q = db.query(Transaction)
    if category:
        q = q.filter(Transaction.category == category)
    if direction:
        q = q.filter(Transaction.direction == direction)
    if min_amount is not None:
        q = q.filter(Transaction.amount >= Decimal(str(min_amount)))
    if counterparty:
        q = q.filter(Transaction.counterparty_name.ilike(f"%{counterparty}%"))
    start, end = _date_range(period)
    if start:
        q = q.filter(Transaction.timestamp >= start)
    if end:
        q = q.filter(Transaction.timestamp <= end)
    q = q.order_by(desc(Transaction.timestamp)).limit(limit)
    rows = q.all()
    return {
        "count": len(rows),
        "transactions": [
            {
                "timestamp": r.timestamp.isoformat(),
                "type": r.type,
                "direction": r.direction,
                "amount": float(r.amount),
                "counterparty": r.counterparty_name,
                "category": r.category,
            }
            for r in rows
        ],
    }


def tool_aggregate(
    db: Session,
    group_by: str,  # "category" | "counterparty" | "month"
    metric: str = "sum",  # "sum" | "count" | "avg"
    direction: str | None = None,
    period: str | None = None,
    top_n: int = 10,
) -> dict[str, Any]:
    if group_by == "category":
        col = Transaction.category
    elif group_by == "counterparty":
        col = Transaction.counterparty_name
    elif group_by == "month":
        col = func.strftime("%Y-%m", Transaction.timestamp)
    else:
        return {"error": f"unknown group_by: {group_by}"}

    if metric == "sum":
        agg = func.sum(Transaction.amount)
    elif metric == "count":
        agg = func.count(Transaction.id)
    elif metric == "avg":
        agg = func.avg(Transaction.amount)
    else:
        return {"error": f"unknown metric: {metric}"}

    q = db.query(col.label("bucket"), agg.label("value"))
    if direction:
        q = q.filter(Transaction.direction == direction)
    start, end = _date_range(period)
    if start:
        q = q.filter(Transaction.timestamp >= start)
    if end:
        q = q.filter(Transaction.timestamp <= end)
    q = q.group_by("bucket").order_by(desc("value")).limit(top_n)
    rows = q.all()
    return {
        "group_by": group_by,
        "metric": metric,
        "period": period,
        "results": [{"bucket": r.bucket, "value": float(r.value or 0)} for r in rows],
    }


def tool_top_counterparties(
    db: Session, direction: str = "out", period: str | None = None, limit: int = 10
) -> dict[str, Any]:
    return tool_aggregate(
        db,
        group_by="counterparty",
        metric="sum",
        direction=direction,
        period=period,
        top_n=limit,
    )


def tool_category_trend(
    db: Session, category: str, months: int = 6
) -> dict[str, Any]:
    cutoff = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=months * 31)
    rows = (
        db.query(
            func.strftime("%Y-%m", Transaction.timestamp).label("month"),
            func.sum(Transaction.amount).label("total"),
        )
        .filter(Transaction.category == category)
        .filter(Transaction.timestamp >= cutoff)
        .group_by("month")
        .order_by("month")
        .all()
    )
    return {
        "category": category,
        "series": [{"month": r.month, "total": float(r.total or 0)} for r in rows],
    }


TOOL_REGISTRY = {
    "query_transactions": tool_query_transactions,
    "aggregate": tool_aggregate,
    "top_counterparties": tool_top_counterparties,
    "category_trend": tool_category_trend,
}
