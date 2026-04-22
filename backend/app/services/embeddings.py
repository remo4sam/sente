"""Local embeddings via sentence-transformers.

Lazy-loaded singleton so Streamlit-style reloads don't pay the model load cost
twice. bge-small-en-v1.5 is ~130MB, fast on CPU, and good enough for this task.
"""
from __future__ import annotations

import threading
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import get_settings


_model_lock = threading.Lock()
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer(get_settings().embedding_model)
    return _model


def embed(texts: list[str]) -> np.ndarray:
    """Return a (len(texts), dim) float32 array, L2-normalized."""
    model = _get_model()
    vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return vecs.astype(np.float32)


def embed_one(text: str) -> np.ndarray:
    return embed([text])[0]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Both already normalized => dot product."""
    return float(np.dot(a, b))
