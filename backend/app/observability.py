"""LangSmith observability helpers.

What you get:
  - Every Anthropic API call is traced as a run in your LangSmith project
    (model, prompt, completion, latency, token counts, errors).
  - Top-level functions decorated with @traceable show up as a run hierarchy:
    run_chat → chat.llm_call → tool.query_transactions, etc.

How it toggles:
  - LANGSMITH_TRACING=false (default) — `anthropic_client()` returns a plain
    Anthropic SDK client and `traceable` is a near-zero-overhead pass-through.
  - LANGSMITH_TRACING=true — the client is wrapped via
    `langsmith.wrappers.wrap_anthropic` and runs are sent to the project named
    in `LANGSMITH_PROJECT` using `LANGSMITH_API_KEY`.

Everything the langsmith SDK needs is read from environment variables; we
re-export the relevant pydantic-settings values into os.environ on first use
so a single `.env` file drives both app code and the SDK.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from anthropic import Anthropic

from app.config import get_settings

if TYPE_CHECKING:
    from anthropic import Anthropic as AnthropicT


_env_installed = False


def _install_langsmith_env() -> None:
    """Copy Settings.langsmith_* into os.environ so the SDK finds them.

    Uses setdefault so a real environment variable always wins over the
    .env-derived value.
    """
    global _env_installed
    if _env_installed:
        return
    s = get_settings()
    if s.langsmith_tracing:
        os.environ.setdefault("LANGSMITH_TRACING", "true")
    if s.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", s.langsmith_api_key)
    if s.langsmith_project:
        os.environ.setdefault("LANGSMITH_PROJECT", s.langsmith_project)
    _env_installed = True


def _tracing_enabled() -> bool:
    _install_langsmith_env()
    return os.environ.get("LANGSMITH_TRACING", "").lower() in ("1", "true", "yes")


def anthropic_client(api_key: str | None = None) -> "AnthropicT":
    """Return an Anthropic client, wrapped with LangSmith tracing when enabled.

    The wrapped object has the same public surface as `anthropic.Anthropic`,
    so call sites don't need to branch.
    """
    key = api_key or get_settings().anthropic_api_key
    client = Anthropic(api_key=key)
    if _tracing_enabled():
        try:
            from langsmith.wrappers import wrap_anthropic

            return wrap_anthropic(client)
        except ImportError:
            # langsmith not installed — fall back to untraced client
            pass
    return client


# Re-export `traceable` so call sites don't need to import langsmith directly.
# When langsmith isn't installed or tracing is off, we provide a pass-through
# decorator with the same signature so the code keeps working.
try:
    from langsmith import traceable  # type: ignore
except ImportError:  # pragma: no cover
    def traceable(*dargs, **dkwargs):  # type: ignore[no-redef]
        """No-op stand-in when langsmith isn't installed."""
        # Support both @traceable and @traceable(name=..., tags=...) usages.
        if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
            return dargs[0]

        def _decorator(fn):
            return fn

        return _decorator


__all__ = ["anthropic_client", "traceable"]
