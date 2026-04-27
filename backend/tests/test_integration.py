"""Integration tests for the FastAPI app.

We mock the Anthropic client so these run offline and deterministically.
Mocking is at the SDK boundary (`Anthropic.messages.create`), which means we
exercise everything below that — routing, request validation, the parser,
ingestion, dedupe, the metrics middleware — for real.

Coverage:
  - /health, /metrics, /categories: shape correctness
  - /ingest/text: regex-only path (no LLM needed because real fixtures hit regex 100%)
  - /ingest/pdf: end-to-end PDF -> rows visible via /transactions
  - /transactions/correct: stores correction, marks user_corrected
  - /chat: mocked tool-use loop returning a final answer
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.observability import get_metrics_recorder


FIXTURE_PDF = Path(__file__).parent / "fixtures" / "airtel_statement_march_2026.pdf"


@pytest.fixture(autouse=True)
def fresh_db():
    """Drop and recreate tables, and reset LLM metrics, before each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    get_metrics_recorder().reset()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_classifier_response():
    """Deterministic fake classifier output."""

    def make_resp(category: str = "other", confidence: float = 0.7):
        msg = MagicMock()
        block = MagicMock()
        block.type = "text"
        block.text = json.dumps({"category": category, "confidence": confidence, "reason": "test"})
        msg.content = [block]
        msg.stop_reason = "end_turn"
        # usage object with token counts
        msg.usage = MagicMock(input_tokens=10, output_tokens=5)
        return msg

    return make_resp


# ---------- Basic shape ----------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert "X-Request-ID" in r.headers  # middleware tagged it


def test_metrics_initial_state(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "llm" in r.json()
    # No LLM calls yet
    assert r.json()["llm"]["ops"] == {}
    assert r.json()["llm"]["total_cost_usd"] == 0


def test_categories(client):
    r = client.get("/categories")
    assert r.status_code == 200
    cats = r.json()
    assert len(cats) == 17  # 17 categories in taxonomy
    keys = {c["key"] for c in cats}
    assert "self_transfer" in keys
    assert "family_sent" in keys


# ---------- Ingest text (regex-only path) ----------

def test_ingest_text_regex_only_path(client, mock_classifier_response):
    """Real Airtel SMS hits regex 100%, but categorization still calls the LLM."""
    sms = [
        "SENT.TID 142103669037. UGX 45,000 to JOEL AKUMA  0740204439. Fee UGX 500. Bal UGX 5,979,612. Date 04-March-2026 19:18.",
        "CASH DEPOSIT of UGX 200,000 from  SC BANK SC BANK. Bal UGX 228,702. TID 142853569804. 15-March-2026 02:01",
    ]
    with patch("app.services.categorizer.Anthropic") as mock_anthropic:
        instance = mock_anthropic.return_value
        instance.messages.create.return_value = mock_classifier_response(
            category="family_sent", confidence=0.8
        )
        r = client.post("/ingest/text", json={"messages": sms})
    assert r.status_code == 200
    body = r.json()
    assert body["parsed"] == 2
    assert body["inserted"] == 2
    assert body["parser_stats"]["regex_hits"] == 2
    assert body["parser_stats"]["failures"] == 0


def test_ingest_text_then_list_transactions(client, mock_classifier_response):
    sms = ["SENT.TID 999111. UGX 30,000 to SARAH NAMU  0701234567. Fee UGX 500. Bal UGX 50,000. Date 05-March-2026 10:00."]
    with patch("app.services.categorizer.Anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = mock_classifier_response()
        client.post("/ingest/text", json={"messages": sms})

    r = client.get("/transactions")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["counterparty_name"] == "SARAH NAMU"
    assert rows[0]["amount"] == 30000.0


# ---------- PDF ingestion ----------

@pytest.mark.skipif(not FIXTURE_PDF.exists(), reason="fixture PDF not present")
def test_ingest_pdf_full_flow(client, mock_classifier_response):
    with patch("app.services.categorizer.Anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = mock_classifier_response()
        with FIXTURE_PDF.open("rb") as f:
            r = client.post(
                "/ingest/pdf",
                files={"file": ("statement.pdf", f, "application/pdf")},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["parsed"] == 23
    assert body["inserted"] == 23
    assert body["customer_name"] == "Samuel Remo"
    assert body["statement_total_credit"] == 7040000.0

    # Verify rows are queryable
    r2 = client.get("/transactions?limit=100")
    assert len(r2.json()) == 23


def test_ingest_pdf_rejects_non_pdf(client):
    r = client.post(
        "/ingest/pdf",
        files={"file": ("bad.txt", b"not a pdf", "text/plain")},
    )
    assert r.status_code == 400


# ---------- Correction ----------

def test_correction_marks_user_corrected(client, mock_classifier_response):
    sms = ["SENT.TID 555111. UGX 10,000 to MARY JANE  0712223334. Fee UGX 500. Bal UGX 5,000. Date 05-March-2026 10:00."]
    with patch("app.services.categorizer.Anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = mock_classifier_response(
            category="other"
        )
        client.post("/ingest/text", json={"messages": sms})

    rows = client.get("/transactions").json()
    tx_id = rows[0]["id"]

    # Correct it (record_correction does NOT call the LLM, only embeddings)
    r = client.post(
        "/transactions/correct",
        json={"transaction_id": tx_id, "category": "family_sent"},
    )
    assert r.status_code == 200
    assert r.json()["current"] == "family_sent"

    # Verify
    rows = client.get("/transactions").json()
    assert rows[0]["category"] == "family_sent"
    assert rows[0]["user_corrected"] is True


# ---------- Chat ----------

def test_chat_simple_answer(client):
    """Mock a single-turn 'no tool use' answer."""
    final_msg = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = "You haven't made any transactions yet."
    final_msg.content = [block]
    final_msg.stop_reason = "end_turn"
    final_msg.usage = MagicMock(input_tokens=20, output_tokens=10)

    with patch("app.services.chat_agent.Anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = final_msg
        r = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "How much did I spend?"}]},
        )
    assert r.status_code == 200
    body = r.json()
    assert "transactions" in body["answer"].lower()
    assert body["trace"] == []
    assert body["steps"] == 1


def test_metrics_populated_after_calls(client, mock_classifier_response):
    """Run a few operations and check /metrics reflects them."""
    sms = ["SENT.TID 777111. UGX 5,000 to BOB  0701112223. Fee UGX 500. Bal UGX 10,000. Date 05-March-2026 10:00."]
    with patch("app.services.categorizer.Anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = mock_classifier_response()
        client.post("/ingest/text", json={"messages": sms})

    r = client.get("/metrics").json()
    assert "categorizer" in r["llm"]["ops"]
    cat_metrics = r["llm"]["ops"]["categorizer"]
    assert cat_metrics["calls"] == 1
    assert cat_metrics["successes"] == 1
    assert cat_metrics["input_tokens"] > 0
    assert cat_metrics["p50_latency_ms"] >= 0
    assert cat_metrics["cost_usd"] > 0
    assert len(cat_metrics["models"]) == 1
    assert cat_metrics["models"][0]["calls"] == 1
    assert r["llm"]["total_cost_usd"] >= cat_metrics["cost_usd"]
