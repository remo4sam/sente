"""Categorizer evaluation.

This is the capstone's headline metric artifact. Produces:

  1. Zero-shot accuracy (classifier with no few-shots, just taxonomy)
  2. Oracle upper bound (classifier with ALL other examples as few-shots)
  3. Accuracy curve: accuracy on hold-out vs # corrections added (random order)
  4. Accuracy curve: same, but stratified correction order
  5. Confusion matrix at zero-shot and at fully-corrected states

Methodology:
  - 70/30 train/hold-out split, stratified by category so every category
    appears in both splits.
  - For each seed (default 3), we shuffle the train set and add corrections
    in batches of 10, re-measuring hold-out accuracy after each batch.
  - Final results are mean +/- stdev across seeds.

Cost control:
  - Each classifier call uses Haiku, which is ~$0.25/M input tokens.
  - A full run: ~45 hold-out examples x ~10 checkpoints x 3 seeds = ~1350
    classifier calls, plus ~45 zero-shot + ~45 oracle. Budget: ~2000 calls.
  - Estimated cost with Haiku: under $0.50 per full run.
  - Use --quick flag for a 1-seed smoke-test.
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.taxonomy import Category, CATEGORY_DESCRIPTIONS
from app.models.db import Base, CategoryExample
from app.services.categorizer import (
    FewShot,
    _CLASSIFIER_SYSTEM,
    _build_user_prompt,
)
from app.services.embeddings import embed
from evals.labeled_set import LabeledExample
from evals.metrics import (
    AccuracyCurve,
    AccuracyResult,
    CurvePoint,
    accuracy,
    confusion_matrix,
    top_confusions,
)

logger = logging.getLogger(__name__)


# ---------- In-memory few-shot store ----------
# We bypass the DB for evaluation. Much faster; lets us run many configurations
# deterministically without side effects on the app database.


@dataclass
class MemoryFewShotStore:
    items: list[tuple[str, str, np.ndarray]] = field(default_factory=list)

    def add(self, text: str, category: str, embedding: np.ndarray) -> None:
        self.items.append((text, category, embedding))

    def retrieve(
        self, query_embedding: np.ndarray, k: int = 5, min_similarity: float = 0.55
    ) -> list[FewShot]:
        scored = []
        for text, cat, vec in self.items:
            sim = float(np.dot(query_embedding, vec))
            if sim >= min_similarity:
                scored.append((sim, text, cat))
        scored.sort(reverse=True)
        return [FewShot(text=t, category=c) for _, t, c in scored[:k]]

    def __len__(self) -> int:
        return len(self.items)


# ---------- Classifier call (mirrors services/categorizer.classify, DB-free) ----------


def _classify(
    client: Anthropic,
    model: str,
    transaction_text: str,
    few_shots: list[FewShot],
) -> str:
    import json

    resp = client.messages.create(
        model=model,
        max_tokens=128,
        system=_CLASSIFIER_SYSTEM,
        messages=[{"role": "user", "content": _build_user_prompt(transaction_text, few_shots)}],
    )
    raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        return json.loads(raw)["category"]
    except Exception:
        logger.warning("Classifier fallback; raw=%r", raw[:120])
        return Category.OTHER.value


# ---------- Stratified split ----------


def stratified_split(
    examples: list[LabeledExample], test_size: float, seed: int
) -> tuple[list[LabeledExample], list[LabeledExample]]:
    rng = random.Random(seed)
    by_cat: dict[str, list[LabeledExample]] = {}
    for ex in examples:
        by_cat.setdefault(ex.category, []).append(ex)

    train, test = [], []
    for cat, items in by_cat.items():
        rng.shuffle(items)
        k = max(1, int(round(len(items) * test_size)))
        test.extend(items[:k])
        train.extend(items[k:])
    rng.shuffle(train)
    rng.shuffle(test)
    return train, test


# ---------- Evaluations ----------


def eval_zero_shot(
    client: Anthropic, model: str, hold_out: list[LabeledExample]
) -> AccuracyResult:
    """Classifier accuracy with no few-shots at all."""
    y_true, y_pred = [], []
    for ex in hold_out:
        pred = _classify(client, model, ex.transaction_text, few_shots=[])
        y_true.append(ex.category)
        y_pred.append(pred)
    return accuracy(y_true, y_pred)


def eval_with_store(
    client: Anthropic,
    model: str,
    hold_out: list[LabeledExample],
    store: MemoryFewShotStore,
) -> AccuracyResult:
    """Classifier accuracy using few-shots retrieved from the current store."""
    texts = [ex.transaction_text for ex in hold_out]
    query_embs = embed(texts)
    y_true, y_pred = [], []
    for ex, q in zip(hold_out, query_embs):
        shots = store.retrieve(q, k=5)
        pred = _classify(client, model, ex.transaction_text, few_shots=shots)
        y_true.append(ex.category)
        y_pred.append(pred)
    return accuracy(y_true, y_pred)


def build_accuracy_curve(
    client: Anthropic,
    model: str,
    train: list[LabeledExample],
    hold_out: list[LabeledExample],
    strategy: str,  # "random" | "stratified"
    seeds: list[int],
    batch_size: int = 10,
) -> AccuracyCurve:
    """Incrementally add corrections and re-measure hold-out accuracy."""
    curve = AccuracyCurve(strategy=strategy)

    # Pre-embed all train texts once (same text => same embedding across seeds)
    text_to_vec = dict(zip(
        [ex.transaction_text for ex in train],
        embed([ex.transaction_text for ex in train]),
    ))

    for seed in seeds:
        rng = random.Random(seed)
        if strategy == "random":
            ordered = list(train)
            rng.shuffle(ordered)
        elif strategy == "stratified":
            # Cycle through categories, taking one from each at a time
            buckets: dict[str, list[LabeledExample]] = {}
            for ex in train:
                buckets.setdefault(ex.category, []).append(ex)
            for b in buckets.values():
                rng.shuffle(b)
            ordered = []
            while any(buckets.values()):
                for cat in list(buckets):
                    if buckets[cat]:
                        ordered.append(buckets[cat].pop())
            # Tail-shuffle to avoid lockstep artifacts
            rng.shuffle(ordered[len(buckets):])
        else:
            raise ValueError(f"unknown strategy: {strategy}")

        store = MemoryFewShotStore()
        points: list[CurvePoint] = []

        # Baseline: 0 corrections
        logger.info("[%s seed=%d] baseline with 0 corrections", strategy, seed)
        acc = eval_with_store(client, model, hold_out, store)
        points.append(CurvePoint(num_corrections=0, accuracy=acc.accuracy, seed=seed))

        # Add in batches
        for start in range(0, len(ordered), batch_size):
            batch = ordered[start : start + batch_size]
            for ex in batch:
                store.add(ex.transaction_text, ex.category, text_to_vec[ex.transaction_text])
            n = len(store)
            logger.info("[%s seed=%d] measuring at %d corrections", strategy, seed, n)
            acc = eval_with_store(client, model, hold_out, store)
            points.append(CurvePoint(num_corrections=n, accuracy=acc.accuracy, seed=seed))

        curve.points_per_seed[seed] = points

    return curve


# ---------- Top-level runner ----------


@dataclass
class CategorizerEvalReport:
    zero_shot: AccuracyResult
    oracle: AccuracyResult
    random_curve: AccuracyCurve
    stratified_curve: AccuracyCurve
    zero_shot_confusion: list[tuple[str, str, int]]
    oracle_confusion: list[tuple[str, str, int]]
    labels: list[str]
    num_train: int
    num_holdout: int

    def as_dict(self) -> dict:
        return {
            "num_train": self.num_train,
            "num_holdout": self.num_holdout,
            "zero_shot": self.zero_shot.as_dict(),
            "oracle": self.oracle.as_dict(),
            "zero_shot_top_confusions": [
                {"true": t, "pred": p, "count": n} for t, p, n in self.zero_shot_confusion
            ],
            "oracle_top_confusions": [
                {"true": t, "pred": p, "count": n} for t, p, n in self.oracle_confusion
            ],
            "random_curve": [
                {"n_corrections": n, "mean_acc": m, "stdev": s}
                for n, m, s in self.random_curve.mean_curve()
            ],
            "stratified_curve": [
                {"n_corrections": n, "mean_acc": m, "stdev": s}
                for n, m, s in self.stratified_curve.mean_curve()
            ],
        }


def run_full_eval(
    examples: list[LabeledExample],
    seeds: list[int],
    split_seed: int = 0,
    batch_size: int = 10,
    model: Optional[str] = None,
) -> CategorizerEvalReport:
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)
    model = model or settings.categorizer_model

    train, hold_out = stratified_split(examples, test_size=0.3, seed=split_seed)
    logger.info("Split: %d train / %d hold-out", len(train), len(hold_out))

    labels = sorted({ex.category for ex in examples})

    # Zero-shot
    logger.info("Evaluating zero-shot...")
    zero = eval_zero_shot(client, model, hold_out)

    # Oracle: use ENTIRE train set as few-shot pool
    logger.info("Evaluating oracle (full few-shot pool)...")
    oracle_store = MemoryFewShotStore()
    train_embs = embed([ex.transaction_text for ex in train])
    for ex, v in zip(train, train_embs):
        oracle_store.add(ex.transaction_text, ex.category, v)
    oracle = eval_with_store(client, model, hold_out, oracle_store)

    # Confusion matrices at both ends
    y_true_z, y_pred_z = [], []
    for ex in hold_out:
        y_true_z.append(ex.category)
        y_pred_z.append(_classify(client, model, ex.transaction_text, few_shots=[]))
    zero_confusions = top_confusions(y_true_z, y_pred_z, top_k=10)

    y_true_o, y_pred_o = [], []
    query_embs = embed([ex.transaction_text for ex in hold_out])
    for ex, q in zip(hold_out, query_embs):
        shots = oracle_store.retrieve(q, k=5)
        y_true_o.append(ex.category)
        y_pred_o.append(_classify(client, model, ex.transaction_text, few_shots=shots))
    oracle_confusions = top_confusions(y_true_o, y_pred_o, top_k=10)

    # Curves
    logger.info("Building random-order curve (%d seeds)...", len(seeds))
    random_curve = build_accuracy_curve(
        client, model, train, hold_out, strategy="random", seeds=seeds, batch_size=batch_size
    )
    logger.info("Building stratified-order curve (%d seeds)...", len(seeds))
    stratified_curve = build_accuracy_curve(
        client, model, train, hold_out, strategy="stratified", seeds=seeds, batch_size=batch_size
    )

    return CategorizerEvalReport(
        zero_shot=zero,
        oracle=oracle,
        random_curve=random_curve,
        stratified_curve=stratified_curve,
        zero_shot_confusion=zero_confusions,
        oracle_confusion=oracle_confusions,
        labels=labels,
        num_train=len(train),
        num_holdout=len(hold_out),
    )
