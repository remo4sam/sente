# syntax=docker/dockerfile:1.6
#
# Multi-stage build for the Sente backend.
# Pre-bakes the embedding model into the image so first-request latency is fast,
# and so the running container doesn't need outbound HTTPS to HuggingFace.

FROM python:3.12-slim AS builder

# System deps needed by pdfplumber + numpy/torch wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY backend/requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Pre-download the embedding model so it's cached in the image
ENV TRANSFORMERS_CACHE=/build/.cache/huggingface
ENV HF_HOME=/build/.cache/huggingface
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-small-en-v1.5')"


FROM python:3.12-slim AS runtime

# libgomp1 is needed at runtime by torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash app

# Copy installed Python packages and HF model cache from builder
COPY --from=builder /root/.local /home/app/.local
COPY --from=builder /build/.cache/huggingface /home/app/.cache/huggingface

ENV PATH=/home/app/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/home/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/home/app/.cache/huggingface \
    LOG_LEVEL=INFO

WORKDIR /app
COPY --chown=app:app backend/ /app/

USER app

# Railway and most container hosts inject $PORT
ENV PORT=8000
EXPOSE 8000

# Postgres backend — safe to scale workers based on host CPU
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2"]
