"""Human-feedback recording (SQLite)."""
from server.metrics.tracker import MetricsTracker


def test_record_feedback_unknown_task(tmp_path):
    t = MetricsTracker(str(tmp_path / "m.db"))
    assert t.record_feedback("nonexistent", "accepted", False) is False


def test_record_feedback_known_task(tmp_path):
    t = MetricsTracker(str(tmp_path / "m.db"))
    t.record_task(
        task_id="t1", session_id="s1", intent="knowledge_query",
        started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z",
        latency_ms=1000, success=True,
    )
    assert t.record_feedback("t1", "accepted", False) is True


def test_record_feedback_edited_answer(tmp_path):
    t = MetricsTracker(str(tmp_path / "m.db"))
    t.record_task("t2", "s1", "issue_query", "a", "b", 1000, True)
    assert t.record_feedback("t2", "edited_and_accepted", True, "修改后的答案") is True
