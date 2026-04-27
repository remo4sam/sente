"""Parser evaluation.

Runs the parser over a corpus of SMS messages and reports:
  - regex-vs-LLM-vs-failure split
  - per-template hit counts
  - throughput (messages/sec) and avg latency for LLM fallbacks
  - samples of unmatched messages (for regex template development)

The corpus is: real fixtures from tests/fixtures_airtel.py + the synthetic
labeled set (raw_sms field). This gives both curated edge cases and scale.

Output:
  evals/results/parser_eval.json
  evals/results/parser_eval.txt  (human-readable)
"""
from __future__ import annotations

import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.parsers.regex_parser import TEMPLATES, ParseOutcome, try_regex_parse
from app.parsers.orchestrator import parse_message, ParseStats
from app.schemas.transaction import ParsedTransaction

logger = logging.getLogger(__name__)


@dataclass
class ParserEvalReport:
    corpus_name: str
    total: int
    regex_hits: int
    llm_hits: int
    skipped: int
    failures: int
    regex_rate: float
    llm_rate: float
    failure_rate: float
    template_hits: dict[str, int]
    avg_regex_latency_ms: float
    avg_llm_latency_ms: float
    unmatched_samples: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "corpus_name": self.corpus_name,
            "total": self.total,
            "regex_hits": self.regex_hits,
            "llm_hits": self.llm_hits,
            "skipped": self.skipped,
            "failures": self.failures,
            "regex_rate": round(self.regex_rate, 4),
            "llm_rate": round(self.llm_rate, 4),
            "failure_rate": round(self.failure_rate, 4),
            "template_hits": self.template_hits,
            "avg_regex_latency_ms": round(self.avg_regex_latency_ms, 2),
            "avg_llm_latency_ms": round(self.avg_llm_latency_ms, 2),
            "unmatched_samples": self.unmatched_samples,
        }

    def as_text(self) -> str:
        lines = [
            f"=== Parser eval: {self.corpus_name} ===",
            f"Total messages:  {self.total}",
            f"Regex hits:      {self.regex_hits}  ({self.regex_rate:.1%})",
            f"LLM fallbacks:   {self.llm_hits}  ({self.llm_rate:.1%})",
            f"Skipped (OTP/FAILED): {self.skipped}",
            f"Failures:        {self.failures}  ({self.failure_rate:.1%})",
            "",
            f"Latency: regex {self.avg_regex_latency_ms:.2f}ms avg, "
            f"LLM {self.avg_llm_latency_ms:.2f}ms avg",
            "",
            "Per-template hits:",
        ]
        for name, n in sorted(self.template_hits.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {name:<30} {n}")
        if self.unmatched_samples:
            lines.append("\nUnmatched samples:")
            for s in self.unmatched_samples[:10]:
                lines.append(f"  - {s[:120]}")
        return "\n".join(lines)


def evaluate_parser(
    messages: list[str],
    corpus_name: str = "default",
    use_llm_fallback: bool = False,
) -> ParserEvalReport:
    """Evaluate the parser on a message corpus.

    use_llm_fallback=False (default) keeps the eval deterministic and free.
    Set True for a true end-to-end measurement that includes the LLM path.
    """
    stats = ParseStats()
    template_hits: Counter[str] = Counter()
    regex_latencies: list[float] = []
    llm_latencies: list[float] = []

    for msg in messages:
        stats.total += 1
        t0 = time.perf_counter()
        result = try_regex_parse(msg)
        regex_latencies.append((time.perf_counter() - t0) * 1000)

        if isinstance(result, ParsedTransaction):
            stats.regex_hits += 1
            # Identify which template matched for per-template stats
            for tpl in TEMPLATES:
                if tpl.pattern.search(msg):
                    template_hits[tpl.name] += 1
                    break
        elif result == ParseOutcome.SKIP:
            stats.skipped += 1
            for tpl in TEMPLATES:
                if tpl.pattern.search(msg):
                    template_hits[tpl.name] += 1
                    break
        else:
            if use_llm_fallback:
                t0 = time.perf_counter()
                llm_result = parse_message(msg)  # this will call LLM
                llm_latencies.append((time.perf_counter() - t0) * 1000)
                if llm_result is not None:
                    stats.llm_hits += 1
                else:
                    stats.failures += 1
                    stats.unmatched_samples.append(msg)
            else:
                stats.failures += 1
                stats.unmatched_samples.append(msg)

    denom = stats.total - stats.skipped or 1
    return ParserEvalReport(
        corpus_name=corpus_name,
        total=stats.total,
        regex_hits=stats.regex_hits,
        llm_hits=stats.llm_hits,
        skipped=stats.skipped,
        failures=stats.failures,
        regex_rate=stats.regex_hits / denom,
        llm_rate=stats.llm_hits / denom,
        failure_rate=stats.failures / denom,
        template_hits=dict(template_hits),
        avg_regex_latency_ms=(sum(regex_latencies) / len(regex_latencies)) if regex_latencies else 0.0,
        avg_llm_latency_ms=(sum(llm_latencies) / len(llm_latencies)) if llm_latencies else 0.0,
        unmatched_samples=stats.unmatched_samples[:20],
    )


def write_reports(report: ParserEvalReport, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"parser_eval_{report.corpus_name}.json").write_text(
        json.dumps(report.as_dict(), indent=2)
    )
    (out_dir / f"parser_eval_{report.corpus_name}.txt").write_text(report.as_text())
