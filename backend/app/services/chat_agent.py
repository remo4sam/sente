"""Chat agent with tool use.

Server-side agent loop (Pattern A): the frontend sends a user message, the
backend drives the Anthropic tool-use loop, executes tools against the DB,
and streams the final answer back.

For the capstone this is kept simple and non-streaming. Add streaming once
the shape is stable — see docs/plan.md.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "query_transactions",
        "description": (
            "Fetch a list of individual transactions with optional filters. "
            "Use when the user wants specific transactions, not aggregates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "direction": {"type": "string", "enum": ["in", "out"]},
                "period": {
                    "type": "string",
                    "enum": [
                        "this_month", "last_month", "last_7_days",
                        "last_30_days", "last_90_days", "this_year", "last_year",
                    ],
                },
                "min_amount": {"type": "number"},
                "counterparty": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "aggregate",
        "description": (
            "Aggregate transactions. Use for 'how much total', 'top categories', "
            "'monthly breakdown' style questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "group_by": {"type": "string", "enum": ["category", "counterparty", "month"]},
                "metric": {"type": "string", "enum": ["sum", "count", "avg"], "default": "sum"},
                "direction": {"type": "string", "enum": ["in", "out"]},
                "period": {"type": "string"},
                "top_n": {"type": "integer", "default": 10},
            },
            "required": ["group_by"],
        },
    },
    {
        "name": "top_counterparties",
        "description": "Top recipients (direction=out) or senders (direction=in) by total amount.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["in", "out"], "default": "out"},
                "period": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "category_trend",
        "description": "Monthly spending trend for a single category over the last N months.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "months": {"type": "integer", "default": 6},
            },
            "required": ["category"],
        },
    },
]


_SYSTEM = """You are Sente, a personal finance assistant for Ugandan mobile money users.
Answer questions about the user's MTN/Airtel transactions using the provided tools.

Rules:
- Always call a tool to get real numbers. Never invent figures.
- Prefer `aggregate` for totals and breakdowns; use `query_transactions` for
  specific lists.
- Currency is UGX. Format amounts with thousand separators (e.g., "UGX 45,000").
- Be concise. Lead with the number, then one sentence of context.
- If the user's question is ambiguous (e.g., "last month" on the 2nd of a month),
  pick a sensible default and note it in one line.
"""


def run_chat(db: Session, messages: list[dict[str, Any]], max_steps: int = 6) -> dict[str, Any]:
    """Run the agent loop. Returns {"answer": str, "trace": list}."""
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)

    trace: list[dict[str, Any]] = []
    convo = list(messages)

    for step in range(max_steps):
        resp = client.messages.create(
            model=settings.chat_model,
            max_tokens=1024,
            system=_SYSTEM,
            tools=TOOL_SCHEMAS,
            messages=convo,
        )

        if resp.stop_reason == "tool_use":
            tool_results = []
            for block in resp.content:
                if getattr(block, "type", None) == "tool_use":
                    name = block.name
                    args = block.input or {}
                    fn = TOOL_REGISTRY.get(name)
                    if fn is None:
                        result = {"error": f"unknown tool {name}"}
                    else:
                        try:
                            result = fn(db, **args)
                        except TypeError as e:
                            result = {"error": f"bad arguments: {e}"}
                    trace.append({"tool": name, "args": args, "result": result})
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        }
                    )
            convo.append({"role": "assistant", "content": resp.content})
            convo.append({"role": "user", "content": tool_results})
            continue

        # Final answer
        answer = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        return {"answer": answer, "trace": trace, "steps": step + 1}

    return {
        "answer": "I wasn't able to finish that query within the step budget. Try rephrasing?",
        "trace": trace,
        "steps": max_steps,
    }
