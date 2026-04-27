"""Run the parser evaluation on real fixtures + synthetic labeled set.

Usage:
    python -m scripts.run_parser_eval
    python -m scripts.run_parser_eval --with-llm-fallback

Outputs:
    evals/results/parser_eval_*.json
    evals/results/parser_eval_*.txt
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from evals.labeled_set import load_labeled_set
from evals.parser_eval import evaluate_parser, write_reports
from tests.fixtures_airtel import FIXTURES

REPO_ROOT = Path(__file__).parent.parent
LABELED_SET_PATH = REPO_ROOT / "evals" / "labeled_set.json"
RESULTS_DIR = REPO_ROOT / "evals" / "results"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-llm-fallback", action="store_true",
                        help="Also call the LLM on messages that miss regex (costs tokens)")
    args = parser.parse_args()

    # Corpus 1: curated real fixtures
    real_messages = [m for m, _ in FIXTURES]
    report1 = evaluate_parser(real_messages, corpus_name="real_fixtures",
                              use_llm_fallback=args.with_llm_fallback)
    write_reports(report1, RESULTS_DIR)
    print(report1.as_text())
    print()

    # Corpus 2: synthetic labeled set
    if LABELED_SET_PATH.exists():
        synth = load_labeled_set(LABELED_SET_PATH)
        synth_messages = [ex.raw_sms for ex in synth]
        report2 = evaluate_parser(synth_messages, corpus_name="synthetic",
                                  use_llm_fallback=args.with_llm_fallback)
        write_reports(report2, RESULTS_DIR)
        print(report2.as_text())
    else:
        print(f"(skipping synthetic corpus: {LABELED_SET_PATH} not found; "
              f"run `python -m scripts.regenerate_labeled_set` first)")


if __name__ == "__main__":
    main()
