"""Product evaluation for the AI 研发效能 Agent.

Runs the compiled workflow directly (no API server required) over a 30-item
dataset — 10 knowledge / 10 issue / 10 test-case queries — and reports:

  * Intent Accuracy
  * Source Hit Rate (knowledge)
  * Issue Hit Rate (issue)
  * Test Case Schema Pass Rate (test-case)
  * Task Completion Rate
  * Mean Latency

The workflow requires a local embedding model and a live DeepSeek API call.
Results are written to ``evaluation/results/latest.json`` and describe that
run only; reruns may differ.
"""
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.messages import HumanMessage  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402

from server.config import CONFIG  # noqa: E402
from server.rag.embeddings import get_embedder  # noqa: E402
from server.rag.index import index_knowledge_base  # noqa: E402
from server.agent.workflow import build_workflow, run_workflow  # noqa: E402

DATASET_PATH = Path(__file__).parent / "datasets" / "dev_agent_eval.json"
RESULTS_DIR = Path(__file__).parent / "results"

TESTCASE_REQUIRED = {"id", "title", "steps", "expected_result", "priority", "basis_type"}


def build_runtime():
    embedder = get_embedder(CONFIG["EMBEDDING_MODEL_PATH"])
    llm = ChatOpenAI(
        model=CONFIG["MODEL_NAME"],
        temperature=0,
        api_key=CONFIG["DEEPSEEK_API_KEY"],
        base_url=CONFIG["DEEPSEEK_BASE_URL"],
    )
    db = str(PROJECT_ROOT / ".rag_workspace" / "knowledge_db")
    vectordb, _, _ = index_knowledge_base(embedder, db)
    graph = build_workflow(vectordb, llm)
    return graph


def _testcase_schema_ok(tcs) -> bool:
    if not tcs:
        return False
    for tc in tcs:
        if not TESTCASE_REQUIRED.issubset(tc.keys()):
            return False
        if not isinstance(tc.get("steps"), list) or not tc.get("steps"):
            return False
        if tc.get("basis_type") not in {"documented", "ai_suggestion"}:
            return False
    return True


def main():
    graph = build_runtime()
    items = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    per_item = []
    for item in items:
        state = run_workflow(
            graph,
            [HumanMessage(content=item["query"])],
            session_id="eval",
            task_id=item["id"],
        )
        pred_intent = state.get("intent", "")
        intent_ok = pred_intent == item["intent"]
        retrieved = state.get("retrieved_context", [])
        success = bool(state.get("success", False)) and bool(state.get("final_answer", ""))
        latency = state.get("latency_ms", 0)

        hit = None
        if item["intent"] == "knowledge_query":
            sources = [r.get("source", "") for r in retrieved]
            hit = any(s in item.get("expected_sources", []) for s in sources)
        elif item["intent"] == "issue_query":
            ids = [r.get("issue_id", "") for r in retrieved]
            hit = any(i in item.get("expected_issues", []) for i in ids)

        schema_ok = None
        n_cases = 0
        if item["intent"] == "test_case_generation":
            tcs = state.get("tool_results", {}).get("test_cases", [])
            schema_ok = _testcase_schema_ok(tcs)
            n_cases = len(tcs)

        per_item.append({
            "id": item["id"],
            "intent": item["intent"],
            "predicted_intent": pred_intent,
            "intent_ok": intent_ok,
            "hit": hit,
            "schema_ok": schema_ok,
            "success": success,
            "latency_ms": latency,
            "num_test_cases": n_cases,
        })
        print(f"[{item['id']}] intent={pred_intent} ok={intent_ok} hit={hit} "
              f"schema={schema_ok} cases={n_cases} latency={latency}ms")

    def frac(pred) -> float:
        vals = [r for r in per_item if pred(r) is not None]
        return round(sum(1 for r in vals if pred(r)) / len(vals), 4) if vals else 0.0

    def frac_by_intent(intent, key) -> float:
        vals = [r[key] for r in per_item if r["intent"] == intent and r[key] is not None]
        return round(sum(1 for v in vals if v) / len(vals), 4) if vals else 0.0

    latencies = [r["latency_ms"] for r in per_item]

    summary = {
        "dataset": "dev_agent_eval.json",
        "total_items": len(per_item),
        "intent_accuracy": frac(lambda r: r["intent_ok"]),
        "source_hit_rate": frac_by_intent("knowledge_query", "hit"),
        "issue_hit_rate": frac_by_intent("issue_query", "hit"),
        "test_case_schema_pass_rate": frac_by_intent("test_case_generation", "schema_ok"),
        "task_completion_rate": frac(lambda r: r["success"]),
        "mean_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
        "per_item": per_item,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "latest.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== Evaluation Summary ===")
    for k in ("intent_accuracy", "source_hit_rate", "issue_hit_rate",
              "test_case_schema_pass_rate", "task_completion_rate", "mean_latency_ms"):
        print(f"  {k}: {summary[k]}")
    print(f"\nResults written to {out}")


if __name__ == "__main__":
    main()
