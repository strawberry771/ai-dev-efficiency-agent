"""Product metrics summary (acceptance / completion / latency)."""
from server.metrics.tracker import MetricsTracker


def _seed(t):
    t.record_task("t1", "s", "knowledge_query", "a", "b", 1000, True)
    t.record_task("t2", "s", "issue_query", "a", "b", 2000, True)
    t.record_task("t3", "s", "test_case_generation", "a", "b", 3000, True)
    t.record_task("t4", "s", "knowledge_query", "a", "b", 4000, True)
    t.record_feedback("t1", "accepted", False)
    t.record_feedback("t2", "edited_and_accepted", True, "edit")
    t.record_feedback("t3", "rejected", False)
    # t4 has no feedback


def test_summary_counts_and_rates(tmp_path):
    t = MetricsTracker(str(tmp_path / "m.db"))
    _seed(t)
    s = t.summary()
    assert s["total_tasks"] == 4
    assert s["successful_tasks"] == 4
    assert s["task_completion_rate"] == 1.0
    assert s["feedback_tasks"] == 3
    assert s["accepted"] == 1
    assert s["edited_and_accepted"] == 1
    assert s["rejected"] == 1
    assert s["acceptance_rate"] == round(2 / 3, 4)
    assert s["direct_accept_rate"] == round(1 / 3, 4)
    assert s["human_edit_rate"] == 0.5


def test_summary_latency_percentiles(tmp_path):
    t = MetricsTracker(str(tmp_path / "m.db"))
    _seed(t)
    s = t.summary()
    lat = s["latency_ms"]
    assert lat["mean"] == 2500.0
    assert lat["p50"] == 2500.0
    assert lat["p95"] == 3850.0
