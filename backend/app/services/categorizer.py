"""Categorization with a learning loop.

Pipeline:
1. Build a short text representation of the transaction (counterparty, type, amount).
2. Retrieve the top-K most similar user-corrected examples from the database.
3. Call Claude with the taxonomy + retrieved examples as few-shots + the transaction.
4. Parse structured output (category + confidence).

When users correct a category, the correction is embedded and stored. Over time,
the few-shot pool grows and accuracy improves. That delta — measured on a frozen
eval set — is the core evaluation chart in the capstone report.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.taxonomy import Category, CATEGORY_DESCRIPTIONS
from app.models.db import CategoryExample
from app.observability import get_logger, track_llm_call
from app.retry import with_retries
from app.schemas.transaction import ParsedTransaction
from app.services.embeddings import embed_one, embed, cosine_similarity

logger = get_logger(__name__)


def transaction_to_text(t: ParsedTransaction) -> str:
    """Compact text representation used for embedding and classification."""
    parts = [
        f"type={t.type.value}",
        f"direction={t.direction.value}",
        f"amount={t.amount} {t.currency}",
    ]
    if t.counterparty_name:
        parts.append(f"counterparty={t.counterparty_name}")
    if t.reference:
        parts.append(f"reference={t.reference}")
    if t.network:
        parts.append(f"network={t.network.value}")
    return " | ".join(parts)


@dataclass
class FewShot:
    text: str
    category: str


def retrieve_few_shots(
    db: Session, query_text: str, k: int = 5, min_similarity: float = 0.55
) -> list[FewShot]:
    """Retrieve top-K user-corrected examples most similar to the query."""
    examples = db.query(CategoryExample).all()
    if not examples:
        return []

    q = embed_one(query_text)
    scored = []
    for ex in examples:
        v = np.frombuffer(ex.embedding, dtype=np.float32)
        sim = cosine_similarity(q, v)
        if sim >= min_similarity:
            scored.append((sim, ex))
    scored.sort(key=lambda p: p[0], reverse=True)
    return [FewShot(text=ex.transaction_text, category=ex.category) for _, ex in scored[:k]]


_CLASSIFIER_SYSTEM = """You categorize personal mobile money transactions from Uganda.
Pick exactly ONE category from the provided taxonomy.
Return strict JSON: {"category": "<key>", "confidence": <0..1>, "reason": "<short>"}.
No prose, no code fences.
"""


def _build_user_prompt(transaction_text: str, few_shots: list[FewShot]) -> str:
    taxonomy = "\n".join(
        f"- {c.value}: {CATEGORY_DESCRIPTIONS[c]}" for c in Category
    )
    parts = [f"Taxonomy:\n{taxonomy}\n"]
    if few_shots:
        ex_block = "\n".join(
            f"- Transaction: {fs.text}\n  Category: {fs.category}" for fs in few_shots
        )
        parts.append(f"Examples from this user's past corrections:\n{ex_block}\n")
    parts.append(f"Classify this transaction:\n{transaction_text}")
    return "\n".join(parts)


def classify(
    db: Session, transaction: ParsedTransaction, client: Anthropic | None = None
) -> tuple[Category, float]:
    """Zero-shot → few-shot categorization. Returns (category, confidence)."""
    settings = get_settings()
    client = client or Anthropic(api_key=settings.anthropic_api_key)

    text = transaction_to_text(transaction)
    few_shots = retrieve_few_shots(db, text)

    with track_llm_call("categorizer", settings.categorizer_model) as t:
        resp = with_retries(
            lambda: client.messages.create(
                model=settings.categorizer_model,
                max_tokens=256,
                system=_CLASSIFIER_SYSTEM,
                messages=[{"role": "user", "content": _build_user_prompt(text, few_shots)}],
            ),
            op="categorizer",
        )
        t.input_tokens = getattr(resp.usage, "input_tokens", 0)
        t.output_tokens = getattr(resp.usage, "output_tokens", 0)
        t.success = True
    raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    try:
        data = json.loads(raw)
        category = Category(data["category"])
        confidence = float(data.get("confidence", 0.5))
    except Exception:
        logger.warning("classifier_parse_fallback", extra={"raw_preview": raw[:120]})
        category, confidence = Category.OTHER, 0.0

    return category, confidence


def record_correction(
    db: Session, transaction: ParsedTransaction, corrected_category: Category
) -> None:
    """Persist a user correction as a few-shot example."""
    text = transaction_to_text(transaction)
    vec = embed_one(text)
    ex = CategoryExample(
        transaction_text=text,
        category=corrected_category.value,
        embedding=vec.tobytes(),
    )
    db.add(ex)
    db.commit()


def bulk_seed_examples(db: Session, pairs: Iterable[tuple[str, Category]]) -> int:
    """Seed the few-shot pool in bulk (e.g., from a hand-labeled eval set)."""
    pairs = list(pairs)
    if not pairs:
        return 0
    texts = [t for t, _ in pairs]
    vecs = embed(texts)
    for (text, cat), vec in zip(pairs, vecs):
        db.add(
            CategoryExample(
                transaction_text=text,
                category=cat.value,
                embedding=vec.tobytes(),
            )
        )
    db.commit()
    return len(pairs)
