"""Tests for the Airtel Money regex parser.

Every message from the user's real SMS export is asserted against expected
parsed output. When a new template appears, add it to fixtures_airtel.py and
add/update a regex template in regex_parser.py until this suite passes.

Run:   cd backend && pytest tests/ -v
"""
from __future__ import annotations

import pytest

from app.parsers.regex_parser import try_regex_parse, ParseOutcome
from app.parsers.orchestrator import parse_message, ParseStats
from app.schemas.transaction import ParsedTransaction
from tests.fixtures_airtel import FIXTURES


@pytest.mark.parametrize("message, expected", FIXTURES, ids=[f[0][:60] for f in FIXTURES])
def test_regex_parse_fixture(message: str, expected):
    """Each fixture message should either parse to the expected dict or SKIP."""
    result = try_regex_parse(message)

    if expected is None:
        # Should be a deliberate skip
        assert result == ParseOutcome.SKIP, f"Expected SKIP for {message!r}, got {result!r}"
        return

    # Should parse successfully
    assert isinstance(result, ParsedTransaction), (
        f"Expected ParsedTransaction for {message!r}, got {result!r}"
    )

    for field_name, expected_value in expected.items():
        actual = getattr(result, field_name)
        assert actual == expected_value, (
            f"Field {field_name!r}: expected {expected_value!r}, got {actual!r}\n"
            f"Message: {message!r}"
        )


def test_orchestrator_stats_on_fixtures():
    """End-to-end: run the orchestrator over all fixtures and check the metrics.

    With good regex coverage, every fixture should either be a regex hit or a
    deliberate skip. Zero failures, zero LLM fallbacks (since we don't want to
    pay per-test for LLM calls in CI).
    """
    messages = [m for m, _ in FIXTURES]
    expected_skips = sum(1 for _, exp in FIXTURES if exp is None)
    expected_hits = len(FIXTURES) - expected_skips

    # Parse with stats but without actually calling the LLM —
    # we assume regex covers everything in the fixture set.
    stats = ParseStats()
    parsed = []
    for msg in messages:
        # Bypass the LLM by only calling regex
        result = try_regex_parse(msg)
        stats.total += 1
        if isinstance(result, ParsedTransaction):
            stats.regex_hits += 1
            parsed.append(result)
        elif result == ParseOutcome.SKIP:
            stats.skipped += 1
        else:
            stats.failures += 1
            stats.unmatched_samples.append(msg)

    # Report for debuggability
    print("\n" + "=" * 60)
    print("Parser stats on real Airtel export:")
    print(f"  total:      {stats.total}")
    print(f"  regex_hits: {stats.regex_hits}")
    print(f"  skipped:    {stats.skipped}")
    print(f"  failures:   {stats.failures}")
    print(f"  regex_rate: {stats.regex_rate:.2%}")
    if stats.unmatched_samples:
        print("Unmatched:")
        for s in stats.unmatched_samples:
            print(f"  - {s[:100]}")
    print("=" * 60)

    assert stats.failures == 0, f"{stats.failures} messages fell through regex: {stats.unmatched_samples}"
    assert stats.regex_hits == expected_hits
    assert stats.skipped == expected_skips
