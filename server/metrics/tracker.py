"""SQLite-backed product metrics + human feedback tracker.

Stores one row per task. Feedback (accepted / edited_and_accepted / rejected)
is recorded against an existing task via ``record_feedback``.

No API keys, queries or answers are stored — only task metadata and feedback,
which is local demo logging (see README).
"""
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

DEFAULT_DB_PATH = ".rag_workspace/product_metrics.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    session_id TEXT,
    intent TEXT,
    started_at TEXT,
    finished_at TEXT,
    latency_ms INTEGER,
    success INTEGER,
    feedback TEXT,
    edited INTEGER,
    edited_answer TEXT,
    created_at TEXT
)
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MetricsTracker:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._execute(_SCHEMA)

    def _execute(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(sql, params)
                conn.commit()
            finally:
                conn.close()

    def _query(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def record_task(
        self,
        task_id: str,
        session_id: str,
        intent: str,
        started_at: str,
        finished_at: str,
        latency_ms: int,
        success: bool,
    ) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO tasks
                (task_id, session_id, intent, started_at, finished_at, latency_ms, success, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, session_id, intent, started_at, finished_at, latency_ms, int(success), _now_iso()),
        )

    def record_feedback(self, task_id: str, feedback: str, edited: bool, edited_answer: Optional[str] = None) -> bool:
        """Update feedback for an existing task. Returns False if task unknown."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.execute("UPDATE tasks SET feedback = ?, edited = ?, edited_answer = ? WHERE task_id = ?",
                                   (feedback, int(edited), edited_answer, task_id))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def summary(self) -> dict:
        rows = self._query("SELECT * FROM tasks")
        total = len(rows)
        successful = sum(1 for r in rows if r["success"])
        feedback_rows = [r for r in rows if r["feedback"] is not None]
        accepted = sum(1 for r in feedback_rows if r["feedback"] == "accepted")
        edited_accepted = sum(1 for r in feedback_rows if r["feedback"] == "edited_and_accepted")
        rejected = sum(1 for r in feedback_rows if r["feedback"] == "rejected")
        latencies = sorted(r["latency_ms"] for r in rows if r["latency_ms"] is not None)

        def pct(n: int, d: int) -> float:
            return round(n / d, 4) if d else 0.0

        def percentile(data: List[int], p: float) -> float:
            if not data:
                return 0.0
            k = (len(data) - 1) * p
            f = int(k)
            c = f + 1
            if c >= len(data):
                return float(data[-1])
            return data[f] + (data[c] - data[f]) * (k - f)

        accepted_tasks = accepted + edited_accepted
        return {
            "total_tasks": total,
            "successful_tasks": successful,
            "task_completion_rate": pct(successful, total),
            "feedback_tasks": len(feedback_rows),
            "accepted": accepted,
            "edited_and_accepted": edited_accepted,
            "rejected": rejected,
            "acceptance_rate": pct(accepted_tasks, len(feedback_rows)),
            "direct_accept_rate": pct(accepted, len(feedback_rows)),
            "human_edit_rate": pct(edited_accepted, accepted_tasks),
            "latency_ms": {
                "mean": round(sum(latencies) / len(latencies), 1) if latencies else 0,
                "p50": round(percentile(latencies, 0.5), 1),
                "p95": round(percentile(latencies, 0.95), 1),
            },
        }
