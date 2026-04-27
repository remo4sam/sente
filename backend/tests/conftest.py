"""Test configuration and shared fixtures.

Mocks heavy / network-dependent imports so the suite runs offline:
  - sentence_transformers: returns deterministic small vectors so .tobytes()
    produces real bytes (needed by the integration tests that exercise
    the correction / few-shot store flow)

Pins DATABASE_URL to in-memory SQLite before app modules are imported so the
suite doesn't require a running Postgres (the app default is Postgres for dev).
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import numpy as np

# File-backed (not :memory:) so multiple connections from the FastAPI thread
# pool see the same data. The file is recreated per test by the fresh_db
# fixture in test_integration.py.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_sente.db")


def _fake_encode(texts, **_kwargs):
    """Deterministic 'embeddings' for tests.

    Hash the text into a 32-dim float32 unit vector. Same input -> same vector,
    so retrieval similarity is testable end-to-end.
    """
    if isinstance(texts, str):
        texts = [texts]
    out = np.zeros((len(texts), 32), dtype=np.float32)
    for i, t in enumerate(texts):
        rng = np.random.default_rng(abs(hash(t)) % (2**32))
        v = rng.standard_normal(32).astype(np.float32)
        out[i] = v / (np.linalg.norm(v) + 1e-9)
    return out


if "sentence_transformers" not in sys.modules:
    fake = MagicMock()
    fake_model = MagicMock()
    fake_model.encode = _fake_encode
    fake.SentenceTransformer = MagicMock(return_value=fake_model)
    sys.modules["sentence_transformers"] = fake
