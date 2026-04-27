# Deployment

This guide deploys Sente to **Vercel (frontend) + Railway (backend) +
Supabase (Postgres)** for ~$0–5/month. The whole flow takes about 30 minutes
the first time.

For an AWS Lambda + S3 + CloudFront migration, see `docs/aws-migration.md`
(planned, not yet written).

## Prerequisites

- A GitHub account with the project pushed to a repo
- A [Railway](https://railway.app) account
- A [Vercel](https://vercel.com) account
- A [Supabase](https://supabase.com) account
- An Anthropic API key

## 1. Provision Postgres on Supabase

1. supabase.com → New Project. Pick a region close to your Railway region
   (lower latency). Save the database password — Supabase only shows it once.
2. Wait for provisioning (~2 min).
3. Project Settings → Database → **Connection Pooling**. Copy the
   **Transaction mode** URI (port 6543). It looks like:
   ```
   postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
   ```
4. Convert it for SQLAlchemy + psycopg2 and add SSL:
   ```
   postgresql+psycopg2://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
   ```
   That string is what you'll paste into Railway's `DATABASE_URL` in step 2c.

   Use the pooled connection (port 6543), not the direct one (5432) — Railway
   workers reconnect on every cold start and the direct connection limit on
   the free Supabase tier is small.

## 2. Deploy the backend to Railway

### 2a. Create the project

1. Click "New Project" → "Deploy from GitHub repo" → select your Sente repo.
2. Railway detects the `Dockerfile` at the project root and starts building.
3. Wait for the first build (~5 min — it's installing PyTorch and downloading
   the embedding model).

### 2b. Set the env vars

In your backend service → Variables tab, add:

```
DATABASE_URL         postgresql+psycopg2://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
ANTHROPIC_API_KEY    sk-ant-...
PARSER_MODEL         claude-haiku-4-5-20251001
CATEGORIZER_MODEL    claude-haiku-4-5-20251001
CHAT_MODEL           claude-sonnet-4-6
EMBEDDING_MODEL      sentence-transformers/bge-small-en-v1.5
LOG_LEVEL            INFO
CORS_ORIGINS         https://your-frontend.vercel.app
```

`DATABASE_URL` is the Supabase string from step 1.
`CORS_ORIGINS` won't be known until step 3 — leave a placeholder, you'll
update it after the frontend is deployed.

### 2c. Generate a public domain

Settings → Networking → "Generate Domain". Railway gives you something like
`sente-backend-production.up.railway.app`. Copy this — you need it for the
frontend.

### 2d. Verify

```bash
curl https://your-backend.up.railway.app/health
# {"ok":true}

curl https://your-backend.up.railway.app/categories | jq length
# 17
```

If `/health` doesn't respond, check Railway's deploy logs. The most common
issue is hitting the memory limit during model loading — bump to a 1GB
instance if needed.

## 3. Deploy the frontend to Vercel

### 3a. Import the project

1. New Project → Import Git Repository → select your Sente repo.
2. Set "Root Directory" to `frontend`.
3. Framework preset auto-detects as Next.js.

### 3b. Configure env vars

Add to "Environment Variables":

```
NEXT_PUBLIC_API_BASE   https://your-backend.up.railway.app
```

Or, if you want same-origin requests (recommended for production), set
`NEXT_PUBLIC_API_BASE=/api` and update `frontend/vercel.json` rewrites
to point at your Railway URL.

### 3c. Deploy

Click Deploy. First build takes ~2 min. Vercel gives you a URL like
`https://sente.vercel.app`.

### 3d. Update CORS on the backend

Go back to Railway → backend service → Variables → set:

```
CORS_ORIGINS    https://sente.vercel.app
```

Railway will redeploy the backend automatically.

## 4. Smoke test

1. Open the frontend URL. You should see the dashboard with "No transactions yet".
2. Go to Upload → paste an Airtel SMS → click Ingest. The transaction should
   appear under Transactions and the dashboard should update.
3. Go to Chat → ask "How much did I spend?". The agent should respond with a
   useful answer.
4. Hit `/metrics` on the backend to see LLM call stats:
   ```bash
   curl https://your-backend.up.railway.app/metrics | jq
   ```

## 5. Cost monitoring

Railway free tier gives you $5/month of usage credit. The backend service
running 24/7 with low traffic uses ~$3–4/month. Supabase free tier covers
Postgres (500MB storage, 2GB egress) — plenty for a demo.

Vercel's free tier covers the frontend forever for personal projects.

Anthropic API costs are pay-per-call:
- Haiku (parser, categorizer): ~$0.25 per 1M input tokens, ~$1.25 per 1M output
- Sonnet (chat): ~$3 per 1M input, ~$15 per 1M output
- Demo-scale traffic: under $1/month

## 6. Rolling out updates

```bash
git push origin main
# Railway and Vercel both rebuild on push automatically.
```

Vercel keeps a preview URL for every PR if you want to share work-in-progress.

## 7. Common issues

**Backend cold start is slow.** First request after idle takes ~10s on Railway
because the Python process loads the embedding model. This is fine for a
demo. For real users, set `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` higher and
configure a healthcheck ping every 5 minutes (e.g., from a cron service).

**`/ingest/pdf` returns 413.** Railway and Vercel both have request size
limits (default ~5MB on Railway, ~4.5MB on Vercel rewrites). For larger
PDFs, either bypass Vercel rewrites and hit Railway directly, or bump the
limit in Railway settings.

**SQLAlchemy errors mentioning `strftime`.** You're hitting the SQLite-specific
date function on Postgres. The `_month_expr()` helper in `services/tools.py`
handles this — make sure you've deployed a version that includes that fix.

**CORS errors in the browser.** Triple-check that `CORS_ORIGINS` on the
backend exactly matches your frontend URL, including the protocol
(`https://`) and no trailing slash.

## 8. Rollback

Both Railway and Vercel keep the last N deploys.
- Railway: Deployments tab → pick a past deploy → "Redeploy"
- Vercel: Deployments tab → pick → "Promote to Production"
- Supabase: Database → Backups (paid tiers) or rerun `init_db()` against a
  scratch project for schema-only rollback.
