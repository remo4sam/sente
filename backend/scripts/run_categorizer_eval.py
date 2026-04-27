"""Run the categorizer evaluation.

Usage:
    python -m scripts.run_categorizer_eval             # full run: 3 seeds
    python -m scripts.run_categorizer_eval --quick     # 1 seed, batch size 20

Outputs:
    evals/results/categorizer_eval.json
    evals/results/categorizer_eval.txt
    evals/results/accuracy_curve.png  (if matplotlib available)
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from evals.categorizer_eval import run_full_eval
from evals.labeled_set import load_labeled_set
from evals.metrics import format_accuracy_report, format_confusions

REPO_ROOT = Path(__file__).parent.parent
LABELED_SET_PATH = REPO_ROOT / "evals" / "labeled_set.json"
RESULTS_DIR = REPO_ROOT / "evals" / "results"


def render_text_report(report, out_path: Path) -> None:
    lines = [
        "=== Categorizer Eval ===",
        f"Train size:    {report.num_train}",
        f"Hold-out size: {report.num_holdout}",
        "",
        format_accuracy_report(report.zero_shot, "Zero-shot (no few-shots)"),
        "",
        format_accuracy_report(report.oracle, "Oracle (all train as few-shot pool)"),
        "",
        format_confusions(report.zero_shot_confusion, "Top confusions (zero-shot)"),
        "",
        format_confusions(report.oracle_confusion, "Top confusions (oracle)"),
        "",
        "=== Accuracy curve (random order, mean across seeds) ===",
    ]
    for n, m, s in report.random_curve.mean_curve():
        lines.append(f"  n={n:>3}   acc={m:.1%}  stdev={s:.3f}")
    lines.append("")
    lines.append("=== Accuracy curve (stratified order, mean across seeds) ===")
    for n, m, s in report.stratified_curve.mean_curve():
        lines.append(f"  n={n:>3}   acc={m:.1%}  stdev={s:.3f}")
    out_path.write_text("\n".join(lines))


def plot_curves(report, out_path: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib not installed; skipping chart)")
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    for curve, label, color in [
        (report.random_curve, "Random correction order", "#6366f1"),
        (report.stratified_curve, "Stratified (one per category first)", "#22c55e"),
    ]:
        xs = [n for n, _, _ in curve.mean_curve()]
        ms = [m for _, m, _ in curve.mean_curve()]
        ss = [s for _, _, s in curve.mean_curve()]
        ax.plot(xs, ms, marker="o", label=label, color=color, linewidth=2)
        ax.fill_between(xs,
                        [m - s for m, s in zip(ms, ss)],
                        [m + s for m, s in zip(ms, ss)],
                        alpha=0.15, color=color)

    # Horizontal lines for zero-shot and oracle
    ax.axhline(report.zero_shot.accuracy, linestyle="--", color="#94a3b8",
               label=f"Zero-shot baseline ({report.zero_shot.accuracy:.0%})")
    ax.axhline(report.oracle.accuracy, linestyle="--", color="#f59e0b",
               label=f"Oracle ceiling ({report.oracle.accuracy:.0%})")

    ax.set_xlabel("Corrections added to few-shot pool")
    ax.set_ylabel("Hold-out accuracy")
    ax.set_title("Categorization accuracy vs user corrections")
    ax.set_ylim(0, 1.02)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Wrote chart: {out_path}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="1 seed, batch size 20 (faster, noisier)")
    args = parser.parse_args()

    if not LABELED_SET_PATH.exists():
        raise SystemExit(
            f"Labeled set not found at {LABELED_SET_PATH}. "
            f"Run: python -m scripts.regenerate_labeled_set"
        )

    examples = load_labeled_set(LABELED_SET_PATH)
    print(f"Loaded {len(examples)} examples")

    seeds = [42] if args.quick else [42, 7, 99]
    batch_size = 20 if args.quick else 10

    report = run_full_eval(examples, seeds=seeds, batch_size=batch_size)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "categorizer_eval.json").write_text(json.dumps(report.as_dict(), indent=2))
    render_text_report(report, RESULTS_DIR / "categorizer_eval.txt")
    plot_curves(report, RESULTS_DIR / "accuracy_curve.png")

    # Console summary
    delta_random = report.random_curve.mean_curve()[-1][1] - report.zero_shot.accuracy
    delta_strat = report.stratified_curve.mean_curve()[-1][1] - report.zero_shot.accuracy
    print()
    print("=" * 60)
    print(f"Zero-shot baseline:       {report.zero_shot.accuracy:.1%}")
    print(f"After all corrections (random):     "
          f"{report.random_curve.mean_curve()[-1][1]:.1%}  (+{delta_random*100:.1f} pts)")
    print(f"After all corrections (stratified): "
          f"{report.stratified_curve.mean_curve()[-1][1]:.1%}  (+{delta_strat*100:.1f} pts)")
    print(f"Oracle ceiling:           {report.oracle.accuracy:.1%}")
    print("=" * 60)


if __name__ == "__main__":
    main()
