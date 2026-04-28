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

ENV HF_HOME=/build/.cache/huggingface
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-small-en-v1.5')"


FROM python:3.12-slim AS runtime

# libgomp1 is needed at runtime by torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash app

# Python packages installed in the builder stage (`pip install --user` puts
# them in /root/.local). Without this, uvicorn and friends won't exist.
COPY --from=builder --chown=app:app /root/.local /home/app/.local

# Only the bge model — nothing else from the HF cache.
COPY --from=builder --chown=app:app \
    /build/.cache/huggingface/hub/models--BAAI--bge-small-en-v1.5 \
    /home/app/.cache/huggingface/hub/models--BAAI--bge-small-en-v1.5

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

# Required runtime env (must be supplied at `docker run -e ...` or by the host):
#   ANTHROPIC_API_KEY=sk-ant-...
#   DATABASE_URL=postgresql+psycopg2://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
#   CORS_ORIGINS=https://your-frontend.example
#
# We refuse to start with the default localhost URL, which would silently fail
# inside the container. .dockerignore keeps backend/.env out of the image so
# the host's env vars are the only source of truth.
CMD ["sh", "-c", "\
    : \"${DATABASE_URL:?DATABASE_URL must be set (e.g. Supabase pooler URL with ?sslmode=require)}\"; \
    : \"${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY must be set}\"; \
    case \"$DATABASE_URL\" in *localhost*|*127.0.0.1*) \
        echo 'ERROR: DATABASE_URL points at localhost from inside the container.' >&2; exit 1;; \
    esac; \
    exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2 \
"]
