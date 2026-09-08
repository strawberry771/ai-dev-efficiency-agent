"""LangGraph workflow for the AI 研发效能 Agent.

Pipeline::

    START
      -> classify_intent
      -> route_by_intent
          knowledge_query        -> retrieve_knowledge
          issue_query            -> retrieve_issue
          test_case_generation   -> generate_test_cases
          general_chat           -> direct_answer
      -> generate_final_answer
      -> prepare_citations
      -> END

The three core tools (search_knowledge / search_issue / generate_test_cases)
are called deterministically inside the nodes, not via LLM tool-calling.
"""
import re
import time
from typing import List

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

from server.agent.state import WorkflowState
from server.agent.router import classify_intent
from server.agent.core_tools import DevelopmentTools

DEFAULT_TESTCASE_COUNT = 8
NO_EVIDENCE_MSG = "当前知识库未检索到足够依据。"
NO_ISSUE_MSG = "未找到匹配的历史 Issue。"


def _last_user_text(messages: List) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content or ""
    return ""


def _parse_count(text: str) -> int:
    m = re.search(r"(\d+)\s*条", text)
    return int(m.group(1)) if m else DEFAULT_TESTCASE_COUNT


def _format_context_items(items: List[dict], kind: str) -> str:
    out = []
    for i, r in enumerate(items, 1):
        if kind == "issue":
            out.append(
                f"[{i}] {r.get('issue_id')} — {r.get('title')}\n"
                f"现象：{r.get('symptom', '')}\n根因：{r.get('root_cause', '')}\n解决：{r.get('resolution', '')}"
            )
        else:
            loc = r.get("section") or r.get("page") or ""
            out.append(f"[{i}] ({r.get('source', '')} / {loc})\n{r.get('content', '')}")
    return "\n\n".join(out)


def _format_test_cases(tcs: List[dict]) -> str:
    lines = ["根据需求与知识库生成以下测试用例：", ""]
    for tc in tcs:
        tag = "【文档依据】" if tc.get("basis_type") == "documented" else "【AI 建议】"
        lines.append(f"**{tc.get('id')}** {tag} {tc.get('title')}（优先级 {tc.get('priority', 'P1')}）")
        if tc.get("precondition"):
            lines.append(f"- 前置条件：{tc['precondition']}")
        for s in tc.get("steps", []):
            lines.append(f"- 步骤：{s}")
        if tc.get("expected_result"):
            lines.append(f"- 预期结果：{tc['expected_result']}")
        if tc.get("source_basis"):
            lines.append(f"- 依据：{'、'.join(tc['source_basis'])}")
        lines.append("")
    return "\n".join(lines)


def build_workflow(vectordb, llm):
    tools = DevelopmentTools(vectordb, llm)

    def classify(state: WorkflowState) -> dict:
        text = _last_user_text(state.get("messages", []))
        result = classify_intent(llm, text)
        return {
            "intent": result["intent"],
            "intent_confidence": result["confidence"],
            "intent_reason": result["reason"],
        }

    def route(state: WorkflowState) -> str:
        intent = state.get("intent", "general_chat")
        return intent if intent in {"knowledge_query", "issue_query", "test_case_generation", "general_chat"} else "general_chat"

    def retrieve_knowledge(state: WorkflowState) -> dict:
        text = _last_user_text(state.get("messages", []))
        res = tools.search_knowledge(text)
        return {
            "retrieved_context": res["results"],
            "tool_results": {
                "tools_used": ["search_knowledge"],
                "insufficient_evidence": res["insufficient_evidence"],
            },
            "requires_confirmation": False,
        }

    def retrieve_issue(state: WorkflowState) -> dict:
        text = _last_user_text(state.get("messages", []))
        res = tools.search_issue(text)
        return {
            "retrieved_context": res["results"],
            "tool_results": {
                "tools_used": ["search_issue"],
                "insufficient_evidence": res["insufficient_evidence"],
            },
            "requires_confirmation": False,
        }

    def generate_test_cases(state: WorkflowState) -> dict:
        text = _last_user_text(state.get("messages", []))
        res = tools.search_knowledge(text)
        if res["insufficient_evidence"]:
            return {
                "retrieved_context": [],
                "tool_results": {"tools_used": ["search_knowledge"], "insufficient_evidence": True},
                "requires_confirmation": False,
            }
        count = _parse_count(text)
        tcs = tools.generate_test_cases(text, res["results"], count)
        return {
            "retrieved_context": res["results"],
            "tool_results": {
                "tools_used": ["search_knowledge", "generate_test_cases"],
                "insufficient_evidence": False,
                "test_cases": tcs,
            },
            "requires_confirmation": any(tc.get("basis_type") == "ai_suggestion" for tc in tcs),
        }

    def direct_answer(state: WorkflowState) -> dict:
        return {
            "retrieved_context": [],
            "tool_results": {"tools_used": [], "insufficient_evidence": False},
            "requires_confirmation": False,
        }

    def generate_final_answer(state: WorkflowState) -> dict:
        text = _last_user_text(state.get("messages", []))
        intent = state.get("intent", "general_chat")
        tr = state.get("tool_results", {})

        # High uncertainty (low intent confidence or AI-suggested test cases)
        # should prompt a human to confirm.
        confirm = bool(state.get("requires_confirmation")) or state.get("intent_confidence", 1.0) < 0.6

        if intent == "general_chat":
            answer = llm.invoke([SystemMessage(content="你是研发助手，简洁直接地回答用户问题。"), HumanMessage(content=text)]).content
        elif tr.get("insufficient_evidence"):
            answer = NO_ISSUE_MSG if intent == "issue_query" else NO_EVIDENCE_MSG
        elif intent == "issue_query":
            ctx = state.get("retrieved_context", [])
            prompt = f"你是研发助手。请根据下面的历史 Issue 回答用户问题，引用 Issue 编号（如 ISSUE-001）。不要编造不存在的 Issue 编号。\n\n用户问题：\n{text}\n\n历史 Issue：\n{_format_context_items(ctx, 'issue')}"
            answer = llm.invoke([SystemMessage(content=prompt), HumanMessage(content=text)]).content
        elif intent == "test_case_generation":
            answer = _format_test_cases(tr.get("test_cases", []))
        else:
            ctx = state.get("retrieved_context", [])
            prompt = f"你是研发助手。请仅根据下面检索到的知识片段回答用户问题，并在回答中用 [1][2] 标注引用来源。不要编造来源或超出片段内容。\n\n用户问题：\n{text}\n\n知识片段：\n{_format_context_items(ctx, 'knowledge')}"
            answer = llm.invoke([SystemMessage(content=prompt), HumanMessage(content=text)]).content

        if confirm and answer:
            answer += "\n\n（建议人工确认）"

        return {"final_answer": answer, "requires_confirmation": confirm}

    def prepare_citations(state: WorkflowState) -> dict:
        intent = state.get("intent", "general_chat")
        ctx = state.get("retrieved_context", [])
        if intent == "issue_query":
            citations = [{"source": r.get("issue_id", ""), "title": r.get("title", "")} for r in ctx]
        else:
            citations = [
                {
                    "source": r.get("source", ""),
                    "section": r.get("section"),
                    "page": r.get("page"),
                    "chunk_id": r.get("chunk_id"),
                }
                for r in ctx
            ]
        return {"citations": citations}

    graph = StateGraph(WorkflowState)
    graph.add_node("classify_intent", classify)
    graph.add_node("retrieve_knowledge", retrieve_knowledge)
    graph.add_node("retrieve_issue", retrieve_issue)
    graph.add_node("generate_test_cases", generate_test_cases)
    graph.add_node("direct_answer", direct_answer)
    graph.add_node("generate_final_answer", generate_final_answer)
    graph.add_node("prepare_citations", prepare_citations)

    graph.set_entry_point("classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        route,
        {
            "knowledge_query": "retrieve_knowledge",
            "issue_query": "retrieve_issue",
            "test_case_generation": "generate_test_cases",
            "general_chat": "direct_answer",
        },
    )
    for node in ("retrieve_knowledge", "retrieve_issue", "generate_test_cases", "direct_answer"):
        graph.add_edge(node, "generate_final_answer")
    graph.add_edge("generate_final_answer", "prepare_citations")
    graph.add_edge("prepare_citations", END)

    return graph.compile()


def run_workflow(graph, messages, session_id: str, task_id: str) -> dict:
    """Invoke the workflow and normalize success / latency / error handling."""
    started = time.perf_counter()
    try:
        state = graph.invoke({
            "messages": messages,
            "session_id": session_id,
            "task_id": task_id,
        })
        state["success"] = True
    except Exception as e:
        state = {
            "intent": "general_chat",
            "intent_confidence": 0.0,
            "final_answer": "系统处理时发生错误，请稍后重试。",
            "citations": [],
            "retrieved_context": [],
            "tool_results": {"tools_used": [], "insufficient_evidence": False},
            "requires_confirmation": False,
            "success": False,
            "session_id": session_id,
            "task_id": task_id,
            "error": str(e),
        }
    state["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return state
