"""Parser orchestration: regex-first, LLM-fallback, with metrics.

Flow:
  1. Try regex. If it matches a real transaction, done.
  2. If regex matches a "skip" template (OTP notice, failed transaction), drop it.
  3. Otherwise, call the LLM fallback.
  4. If that fails too, record the unmatched sample.

The ParseStats object is the source of truth for the fallback-rate metric
surfaced in the capstone writeup.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.parsers.regex_parser import try_regex_parse, ParseOutcome
from app.parsers.llm_parser import llm_parse
from app.schemas.transaction import ParsedTransaction


@dataclass
class ParseStats:
    total: int = 0
    regex_hits: int = 0
    llm_hits: int = 0
    skipped: int = 0     # OTP notices, FAILED — intentional drops
    failures: int = 0    # no template matched and LLM couldn't parse either
    unmatched_samples: list[str] = field(default_factory=list)

    @property
    def regex_rate(self) -> float:
        denom = self.total - self.skipped
        return self.regex_hits / denom if denom else 0.0

    @property
    def llm_rate(self) -> float:
        denom = self.total - self.skipped
        return self.llm_hits / denom if denom else 0.0

    @property
    def failure_rate(self) -> float:
        denom = self.total - self.skipped
        return self.failures / denom if denom else 0.0

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "regex_hits": self.regex_hits,
            "llm_hits": self.llm_hits,
            "skipped": self.skipped,
            "failures": self.failures,
            "regex_rate": round(self.regex_rate, 4),
            "llm_rate": round(self.llm_rate, 4),
            "failure_rate": round(self.failure_rate, 4),
            "unmatched_samples": self.unmatched_samples[:20],
        }


def parse_message(message: str, stats: Optional[ParseStats] = None) -> Optional[ParsedTransaction]:
    """Parse a single message. Returns None for skipped or unparseable."""
    if stats is not None:
        stats.total += 1

    result = try_regex_parse(message)

    if isinstance(result, ParsedTransaction):
        if stats is not None:
            stats.regex_hits += 1
        return result

    if result == ParseOutcome.SKIP:
        if stats is not None:
            stats.skipped += 1
        return None

    # No regex match — try LLM
    llm_result = llm_parse(message)
    if llm_result is not None:
        if stats is not None:
            stats.llm_hits += 1
        return llm_result

    if stats is not None:
        stats.failures += 1
        if len(stats.unmatched_samples) < 20:
            stats.unmatched_samples.append(message)
    return None


def parse_batch(messages: list[str]) -> tuple[list[ParsedTransaction], ParseStats]:
    stats = ParseStats()
    parsed: list[ParsedTransaction] = []
    for m in messages:
        t = parse_message(m, stats=stats)
        if t is not None:
            parsed.append(t)
    return parsed, stats
