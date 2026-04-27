"""Retry wrapper for Anthropic API calls.

Why: API can fail with rate limits, transient 5xx, or network blips. A single
failure shouldn't break a parsing batch or chat turn. We retry only on classes
of errors that are actually transient — never on auth failures or 400-class
client errors that retrying won't fix.

This is intentionally lightweight (~30 lines). Production systems use tenacity
or the SDK's built-in retries; for a capstone, explicit code is more readable
and easier to discuss in the writeup.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# These are transient: the SDK or upstream telling us "try again later".
RETRIABLE_EXCEPTIONS = (
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,  # 500/502/503/504
)


def with_retries(
    fn: Callable[[], T],
    *,
    op: str,
    max_attempts: int = 3,
    base_delay_s: float = 0.5,
    max_delay_s: float = 8.0,
) -> T:
    """Call `fn` with exponential backoff + jitter on transient failures.

    Re-raises non-retriable errors immediately. Logs each retry with structured
    context so the observability layer can pick it up.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except RETRIABLE_EXCEPTIONS as e:
            last_exc = e
            if attempt >= max_attempts:
                logger.error(
                    "llm_retry_exhausted",
                    extra={"op": op, "attempt": attempt, "error": f"{type(e).__name__}: {e}"},
                )
                raise
            # Exponential backoff with full jitter
            delay = min(base_delay_s * (2 ** (attempt - 1)), max_delay_s)
            delay = random.uniform(0, delay)
            logger.warning(
                "llm_retry",
                extra={
                    "op": op,
                    "attempt": attempt,
                    "next_delay_s": round(delay, 2),
                    "error": f"{type(e).__name__}: {e}",
                },
            )
            time.sleep(delay)
        except APIStatusError:
            # 4xx (except 429) — auth, bad request, etc. Not retriable.
            raise

    # Unreachable, but keeps mypy happy
    assert last_exc is not None
    raise last_exc
