"""Shared evaluation metrics and report utilities.

Keeps the statistical primitives in one place so parser_eval and categorizer_eval
report consistently. No ML-framework dependency on purpose — this is plain stdlib
plus numpy, to keep evals fast and reproducible.
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Sequence


# ---------- Accuracy ----------

@dataclass
class AccuracyResult:
    total: int
    correct: int
    accuracy: float
    per_class_accuracy: dict[str, float]
    per_class_support: dict[str, int]  # how many examples per class

    def as_dict(self) -> dict:
        return asdict(self)


def accuracy(
    y_true: Sequence[str], y_pred: Sequence[str]
) -> AccuracyResult:
    """Compute overall + per-class accuracy.

    Per-class accuracy here is 'recall' (of examples of class C, how many did
    we predict correctly). This is the more useful number when class support
    is uneven, which it always is for personal finance transactions.
    """
    assert len(y_true) == len(y_pred), "y_true and y_pred must be the same length"
    total = len(y_true)
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)

    per_class_correct: dict[str, int] = defaultdict(int)
    per_class_support: dict[str, int] = defaultdict(int)
    for t, p in zip(y_true, y_pred):
        per_class_support[t] += 1
        if t == p:
            per_class_correct[t] += 1

    per_class_accuracy = {
        c: per_class_correct[c] / per_class_support[c] if per_class_support[c] else 0.0
        for c in per_class_support
    }

    return AccuracyResult(
        total=total,
        correct=correct,
        accuracy=correct / total if total else 0.0,
        per_class_accuracy=per_class_accuracy,
        per_class_support=dict(per_class_support),
    )


# ---------- Confusion matrix ----------

def confusion_matrix(
    y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str]
) -> list[list[int]]:
    """Return a dense confusion matrix with rows=true, cols=pred, ordered by `labels`."""
    idx = {l: i for i, l in enumerate(labels)}
    m = [[0] * len(labels) for _ in labels]
    for t, p in zip(y_true, y_pred):
        if t in idx and p in idx:
            m[idx[t]][idx[p]] += 1
    return m


def top_confusions(
    y_true: Sequence[str], y_pred: Sequence[str], top_k: int = 10
) -> list[tuple[str, str, int]]:
    """Return the top-k (true, predicted, count) mistakes, excluding correct predictions."""
    c: Counter[tuple[str, str]] = Counter()
    for t, p in zip(y_true, y_pred):
        if t != p:
            c[(t, p)] += 1
    return [(t, p, n) for (t, p), n in c.most_common(top_k)]


# ---------- Accuracy curve ----------

@dataclass
class CurvePoint:
    num_corrections: int
    accuracy: float
    seed: int | None = None


@dataclass
class AccuracyCurve:
    """An accuracy curve: how hold-out accuracy changes as corrections are added."""
    strategy: str  # "random" | "stratified"
    points_per_seed: dict[int, list[CurvePoint]] = field(default_factory=dict)

    def mean_curve(self) -> list[tuple[int, float, float]]:
        """Return list of (num_corrections, mean_accuracy, stdev) across seeds."""
        # Pivot: group by num_corrections
        by_n: dict[int, list[float]] = defaultdict(list)
        for pts in self.points_per_seed.values():
            for p in pts:
                by_n[p.num_corrections].append(p.accuracy)
        out = []
        for n in sorted(by_n):
            accs = by_n[n]
            mean = statistics.mean(accs)
            sd = statistics.stdev(accs) if len(accs) > 1 else 0.0
            out.append((n, mean, sd))
        return out


# ---------- Report writers ----------

def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))


def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def format_accuracy_report(result: AccuracyResult, title: str = "Accuracy") -> str:
    """Pretty-print an accuracy result as a text block for console or docs."""
    lines = [f"=== {title} ===", f"Overall: {result.accuracy:.1%} ({result.correct}/{result.total})", ""]
    lines.append("Per-class (recall):")
    rows = sorted(
        result.per_class_accuracy.items(),
        key=lambda kv: -result.per_class_support.get(kv[0], 0),
    )
    for cls, acc in rows:
        support = result.per_class_support.get(cls, 0)
        lines.append(f"  {cls:<28} {acc:>6.1%}   (n={support})")
    return "\n".join(lines)


def format_confusions(confusions: list[tuple[str, str, int]], title: str = "Top confusions") -> str:
    lines = [f"=== {title} ==="]
    if not confusions:
        lines.append("  (none)")
        return "\n".join(lines)
    for t, p, n in confusions:
        lines.append(f"  {t:<28} -> {p:<28} ({n})")
    return "\n".join(lines)
