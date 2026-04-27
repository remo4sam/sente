"""LLM fallback parser.

When the regex templates miss, call Claude Haiku with a tool-use-flavored
structured output request. This is the 'long tail' of messages — promotional
variants, weird line breaks, new template versions, etc.

Design notes:
- We use Haiku (fast + cheap) because parsing is a high-volume, well-bounded task.
- We give the model a tight schema and a short system prompt — no chain-of-thought.
- We always record parse_method=LLM so we can measure the fallback rate.
- Unparseable messages return None and get logged for human review.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from anthropic import Anthropic

from app.config import get_settings
from app.observability import get_logger, track_llm_call
from app.retry import with_retries
from app.schemas.transaction import (
    Direction,
    Network,
    ParseMethod,
    ParsedTransaction,
    TransactionType,
)

logger = get_logger(__name__)


_SYSTEM = """You are a mobile money transaction parser for Uganda (MTN and Airtel).
Extract structured fields from an SMS message and return ONLY a JSON object.

Schema fields (use null when absent):
- transaction_id: string | null
- timestamp: ISO 8601 datetime string
- type: one of "sent", "received", "withdraw", "deposit", "bill_payment", "airtime",
        "bundle", "loan_taken", "loan_repaid", "savings_deposit", "savings_withdraw",
        "fee", "reversal", "other"
- direction: "in" or "out"
- amount: number (UGX)
- counterparty_name: string | null
- counterparty_number: string | null
- agent_id: string | null
- reference: string | null
- fee: number | null
- balance_after: number | null
- network: "MTN" | "Airtel" | "unknown"

Return strictly valid JSON, no prose, no code fences.
If the message is not a transaction (promotional, balance inquiry with no movement,
system notice), return {"type": "other", "direction": "out", "amount": 0, "timestamp":
"<today>", "network": "unknown"}.
"""


def llm_parse(message: str, client: Optional[Anthropic] = None) -> Optional[ParsedTransaction]:
    """Parse a message via Claude. Returns None on hard failure."""
    settings = get_settings()
    client = client or Anthropic(api_key=settings.anthropic_api_key)

    try:
        with track_llm_call("parser", settings.parser_model) as t:
            resp = with_retries(
                lambda: client.messages.create(
                    model=settings.parser_model,
                    max_tokens=512,
                    system=_SYSTEM,
                    messages=[{"role": "user", "content": message}],
                ),
                op="parser",
            )
            t.input_tokens = getattr(resp.usage, "input_tokens", 0)
            t.output_tokens = getattr(resp.usage, "output_tokens", 0)
            t.success = True
    except Exception:
        logger.exception("llm_parse_failed", extra={"message_preview": message[:80]})
        return None

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    # Strip accidental code fences defensively
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON for message: %r", message[:80])
        return None

    try:
        return ParsedTransaction(
            transaction_id=data.get("transaction_id"),
            timestamp=datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
            if data.get("timestamp")
            else datetime.utcnow(),
            type=TransactionType(data.get("type", "other")),
            direction=Direction(data.get("direction", "out")),
            amount=Decimal(str(data.get("amount", 0))),
            counterparty_name=data.get("counterparty_name"),
            counterparty_number=data.get("counterparty_number"),
            agent_id=data.get("agent_id"),
            reference=data.get("reference"),
            fee=Decimal(str(data["fee"])) if data.get("fee") is not None else None,
            balance_after=Decimal(str(data["balance_after"]))
            if data.get("balance_after") is not None
            else None,
            network=Network(data.get("network", "unknown")),
            raw_message=message,
            parse_method=ParseMethod.LLM,
        )
    except (ValueError, KeyError) as e:
        logger.warning("LLM output failed schema validation: %s", e)
        return None
