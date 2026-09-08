"""Three core development-agent tools.

``search_knowledge``, ``search_issue`` and ``generate_test_cases`` are the
capabilities the AI 研发效能 Agent is built around. They are deterministic
capabilities invoked directly by the agent workflow (not LLM tool-calling), so
they return structured dicts rather than strings.

The legacy optional tools (web / arXiv) stay in ``server/agent/tools.py`` and
are not part of the default workflow.
"""
from typing import List, Optional

from pydantic import BaseModel, Field

from server.rag.knowledge import search_knowledge as _search_kb
from server.issues.issue_store import search_issue as _search_issue

# Cosine-similarity threshold (see server/rag/knowledge.py) below which a
# knowledge query is considered to lack evidence.
MIN_SIMILARITY = 0.45


class TestCase(BaseModel):
    id: str
    title: str
    precondition: str = ""
    steps: List[str] = Field(default_factory=list)
    expected_result: str = ""
    priority: str = "P1"
    source_basis: List[str] = Field(default_factory=list)
    basis_type: str = "ai_suggestion"  # "documented" | "ai_suggestion"


class TestCaseList(BaseModel):
    test_cases: List[TestCase]


def _format_context(retrieved: List[dict]) -> str:
    if not retrieved:
        return "(无检索到的知识依据)"
    lines = []
    for i, r in enumerate(retrieved, 1):
        loc = r.get("section") or r.get("page")
        loc = f" | {loc}" if loc else ""
        lines.append(f"[依据 {i}] {r.get('source', '')}{loc}\n{r.get('content', '')}")
    return "\n\n".join(lines)


def _testcase_prompt(requirement: str, retrieved: List[dict], count: int) -> str:
    return f"""你是测试工程师，请根据下面的需求与检索到的知识依据，生成 {count} 条测试用例。

需求：
{requirement}

检索到的知识依据（带来源标注）：
{_format_context(retrieved)}

要求：
1. 每条测试用例包含：id、title、precondition、steps（数组）、expected_result、priority、source_basis（数组）、basis_type。
2. basis_type 只能取两个值：
   - "documented"：该用例由上述知识依据明确支持，source_basis 列出对应的「文件名#章节」来源；
   - "ai_suggestion"：该用例是你的补充建议，知识依据中没有明确要求，source_basis 填空数组。
3. 不要凭空编造与需求无关的断言；补充建议要合理且可执行。
4. 只输出测试用例结构，不要额外解释。"""


class DevelopmentTools:
    """Bundles the three core tools with their runtime dependencies."""

    def __init__(self, vectordb, llm, min_similarity: float = MIN_SIMILARITY):
        self.vectordb = vectordb
        self.llm = llm
        self.min_similarity = min_similarity

    def search_knowledge(self, query: str, document_type: Optional[str] = None, top_k: int = 5) -> dict:
        """Search the development knowledge base.

        Returns ``{"results": [...], "insufficient_evidence": bool}``.
        """
        f = {"document_type": document_type} if document_type else None
        results = _search_kb(self.vectordb, query, k=top_k, filter=f)
        best = max((r["score"] for r in results), default=0.0)
        return {
            "results": results,
            "insufficient_evidence": best < self.min_similarity,
        }

    def search_issue(self, query: str, top_k: int = 5) -> dict:
        """Search the historical issue store.

        Returns ``{"results": [...], "insufficient_evidence": bool}``; results
        are always real issue records (empty when nothing matches).
        """
        results = _search_issue(query, top_k=top_k)
        return {
            "results": results,
            "insufficient_evidence": not results,
        }

    def generate_test_cases(self, requirement: str, retrieved_context: List[dict], count: int) -> List[dict]:
        """Generate structured test cases from a requirement + retrieved context.

        ``retrieved_context`` is the list of dicts returned by ``search_knowledge``.
        Each returned dict has ``basis_type`` in {"documented", "ai_suggestion"}.
        """
        structured = self.llm.with_structured_output(TestCaseList, method="function_calling")
        out = structured.invoke(_testcase_prompt(requirement, retrieved_context, count))
        return [tc.model_dump() for tc in out.test_cases]
