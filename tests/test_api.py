"""FastAPI integration smoke tests (endpoints that need no LLM / embedding)."""
from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_feedback_unknown_task():
    r = client.post("/feedback", json={"task_id": "nope", "feedback": "rejected", "edited": False})
    assert r.status_code == 200
    assert r.json() == {"status": "task_not_found"}


def test_metrics_summary_shape():
    s = client.get("/metrics/summary").json()
    for k in ("total_tasks", "task_completion_rate", "acceptance_rate",
              "direct_accept_rate", "human_edit_rate", "latency_ms"):
        assert k in s
