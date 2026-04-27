"""Generate the synthetic labeled eval set.

Usage:
    python -m scripts.regenerate_labeled_set            # uses default seed 42
    python -m scripts.regenerate_labeled_set --seed 7
    python -m scripts.regenerate_labeled_set --force    # overwrite existing

The generated file is deterministic for a given seed.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from evals.labeled_set import generate_labeled_set, save_labeled_set

LABELED_SET_PATH = Path(__file__).parent.parent / "evals" / "labeled_set.json"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true", help="overwrite existing file")
    parser.add_argument("--out", type=Path, default=LABELED_SET_PATH)
    args = parser.parse_args()

    if args.out.exists() and not args.force:
        print(f"{args.out} already exists. Use --force to overwrite.")
        return

    examples = generate_labeled_set(seed=args.seed)
    save_labeled_set(examples, args.out)
    print(f"Wrote {len(examples)} examples to {args.out}")


if __name__ == "__main__":
    main()
