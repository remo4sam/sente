"""Lightweight observability: structured JSON logging + LLM call metrics.

Why custom rather than structlog: keeping deps minimal for a capstone.
Output is single-line JSON per event, parseable by any log aggregator.
The LlmMetricsRecorder is a process-local accumulator; a /metrics endpoint
exposes it for live monitoring during the demo.

Production hardening would add: trace IDs propagated through async context,
a real metrics backend (Prometheus/OTLP), and log shipping. Out of scope.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


# ---------- Structured JSON logging ----------

class JsonFormatter(logging.Formatter):
    """Emit each log record as a single line of JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Pick up structured fields from logger.bind(**kwargs)-style usage,
        # which we expose via logger.info("...", extra={"foo": "bar"}).
        for k, v in record.__dict__.items():
            if k in (
                "args", "msg", "name", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
                "created", "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process", "taskName", "message",
            ):
                continue
            try:
                json.dumps(v)
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = str(v)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str | int | None = None) -> None:
    """Call once at app startup. Idempotent."""
    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO")
    root = logging.getLogger()
    # Remove pre-existing handlers (uvicorn installs its own)
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    # Quiet down noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------- LLM call metrics ----------

# USD per 1M tokens. Source: Anthropic public pricing for the Claude 4.x line.
# Keyed by model ID with bare-family fallbacks so dated snapshots
# (e.g. "claude-haiku-4-5-20251001") and aliases ("claude-haiku-4-5") both resolve.
MODEL_PRICING_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-haiku-4-5":  {"input": 1.0,  "output": 5.0},
    "claude-sonnet-4-6": {"input": 3.0,  "output": 15.0},
    "claude-opus-4-7":   {"input": 15.0, "output": 75.0},
}


def _price_for(model: str) -> dict[str, float] | None:
    if model in MODEL_PRICING_USD_PER_MTOK:
        return MODEL_PRICING_USD_PER_MTOK[model]
    # Strip a trailing "-YYYYMMDD" date snapshot if present
    for family, price in MODEL_PRICING_USD_PER_MTOK.items():
        if model.startswith(family):
            return price
    return None


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the USD cost for a single call. 0.0 if model is unknown."""
    price = _price_for(model)
    if price is None:
        return 0.0
    return (input_tokens / 1_000_000) * price["input"] + (
        output_tokens / 1_000_000
    ) * price["output"]


@dataclass
class LlmCallSample:
    op: str                 # "parser" | "categorizer" | "chat" | other
    model: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    success: bool
    error: str | None = None


@dataclass
class ModelStats:
    """Per-model rollup within an op."""
    model: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
        }


@dataclass
class LlmMetrics:
    """Per-operation rollup."""
    op: str
    calls: int = 0
    successes: int = 0
    failures: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    latencies_ms: list[float] = field(default_factory=list)
    by_model: dict[str, ModelStats] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        return self.successes / self.calls if self.calls else 0.0

    @property
    def p50_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        s = sorted(self.latencies_ms)
        return s[len(s) // 2]

    @property
    def p95_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        s = sorted(self.latencies_ms)
        i = max(0, int(len(s) * 0.95) - 1)
        return s[i]

    def as_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "calls": self.calls,
            "successes": self.successes,
            "failures": self.failures,
            "success_rate": round(self.success_rate, 4),
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cost_usd": round(self.total_cost_usd, 6),
            "p50_latency_ms": round(self.p50_latency_ms, 1),
            "p95_latency_ms": round(self.p95_latency_ms, 1),
            "models": [self.by_model[m].as_dict() for m in sorted(self.by_model)],
        }


class LlmMetricsRecorder:
    """Thread-safe in-memory accumulator. Singleton."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_op: dict[str, LlmMetrics] = {}

    def record(self, sample: LlmCallSample) -> None:
        with self._lock:
            m = self._by_op.setdefault(sample.op, LlmMetrics(op=sample.op))
            m.calls += 1
            if sample.success:
                m.successes += 1
            else:
                m.failures += 1
            m.total_input_tokens += sample.input_tokens
            m.total_output_tokens += sample.output_tokens
            cost = estimate_cost_usd(sample.model, sample.input_tokens, sample.output_tokens)
            m.total_cost_usd += cost
            m.latencies_ms.append(sample.latency_ms)
            # Cap latency history to last 1000 to keep memory bounded
            if len(m.latencies_ms) > 1000:
                m.latencies_ms = m.latencies_ms[-1000:]
            ms = m.by_model.setdefault(sample.model, ModelStats(model=sample.model))
            ms.calls += 1
            ms.input_tokens += sample.input_tokens
            ms.output_tokens += sample.output_tokens
            ms.cost_usd += cost

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            ops = {op: m.as_dict() for op, m in self._by_op.items()}
            total_cost = sum(m.total_cost_usd for m in self._by_op.values())
            return {"ops": ops, "total_cost_usd": round(total_cost, 6)}

    def reset(self) -> None:
        with self._lock:
            self._by_op.clear()


_recorder = LlmMetricsRecorder()


def get_metrics_recorder() -> LlmMetricsRecorder:
    return _recorder


@contextmanager
def track_llm_call(op: str, model: str):
    """Context manager that records a single LLM call.

    Usage:
        with track_llm_call("parser", model) as t:
            resp = client.messages.create(...)
            t.input_tokens = resp.usage.input_tokens
            t.output_tokens = resp.usage.output_tokens
            t.success = True
    """
    @dataclass
    class _Tracker:
        input_tokens: int = 0
        output_tokens: int = 0
        success: bool = False
        error: str | None = None

    tracker = _Tracker()
    t0 = time.perf_counter()
    try:
        yield tracker
    except Exception as e:
        tracker.error = f"{type(e).__name__}: {e}"
        raise
    finally:
        latency_ms = (time.perf_counter() - t0) * 1000
        _recorder.record(
            LlmCallSample(
                op=op,
                model=model,
                latency_ms=latency_ms,
                input_tokens=tracker.input_tokens,
                output_tokens=tracker.output_tokens,
                success=tracker.success,
                error=tracker.error,
            )
        )
        get_logger("llm").info(
            "llm_call",
            extra={
                "op": op,
                "model": model,
                "latency_ms": round(latency_ms, 1),
                "input_tokens": tracker.input_tokens,
                "output_tokens": tracker.output_tokens,
                "success": tracker.success,
                "error": tracker.error,
            },
        )
