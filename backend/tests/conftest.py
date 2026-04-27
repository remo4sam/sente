"""Test configuration and shared fixtures.

Mocks heavy / network-dependent imports so the suite runs offline:
  - sentence_transformers: returns deterministic small vectors so .tobytes()
    produces real bytes (needed by the integration tests that exercise
    the correction / few-shot store flow)
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import numpy as np


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
