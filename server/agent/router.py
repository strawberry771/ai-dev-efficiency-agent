"""Intent router for the AI 研发效能 Agent.

Classifies a user message into one of four intents. The primary mechanism is
DeepSeek structured output (function calling); a deterministic keyword rule
set is kept only as a fallback in case the LLM call fails.
"""
from typing import List

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

ALLOWED_INTENTS = {"knowledge_query", "issue_query", "test_case_generation", "general_chat"}

_INTENT_SYSTEM = """你是「AI 研发效能 Agent」的意图识别器。判断用户输入属于以下哪一类：

- knowledge_query：询问研发知识 / 文档内容（PRD、技术设计、测试资料等），例如「验证码有效期多久」「验证码存在哪里」。
- issue_query：询问历史问题 / Bug / 故障案例，例如「以前有没有类似问题」「有没有遇到过这个 bug」。
- test_case_generation：要求生成测试用例，例如「根据登录 PRD 生成 8 条测试用例」。
- general_chat：闲聊，或与研发知识 / 历史问题 / 测试用例无关的一般性问题。

只输出分类结果，不要输出额外解释。"""


class IntentResult(BaseModel):
    intent: str = Field(description="one of: knowledge_query, issue_query, test_case_generation, general_chat")
    confidence: float = Field(description="confidence in [0.0, 1.0]")
    reason: str = Field(description="short reason for the classification")


def _keyword_fallback(message: str) -> dict:
    """Deterministic keyword rules, used only if the LLM router fails."""
    m = (message or "").lower()
    if any(k in m for k in ("测试用例", "用例", "test case", "testcase")):
        return {"intent": "test_case_generation", "confidence": 0.6, "reason": "keyword fallback: test case"}
    if any(k in m for k in ("历史", "以前", "类似问题", "故障", "bug", "issue", "有没有遇到过")):
        return {"intent": "issue_query", "confidence": 0.6, "reason": "keyword fallback: issue"}
    if any(k in m for k in ("生成", "测试")):
        return {"intent": "test_case_generation", "confidence": 0.5, "reason": "keyword fallback: generate"}
    return {"intent": "knowledge_query", "confidence": 0.5, "reason": "keyword fallback: knowledge"}


def classify_intent(llm, message: str) -> dict:
    """Return ``{"intent", "confidence", "reason"}``.

    ``llm`` is a base ``ChatOpenAI`` (DeepSeek). Falls back to keyword rules on
    any failure and always returns a valid intent.
    """
    try:
        structured = llm.with_structured_output(IntentResult, method="function_calling")
        out = structured.invoke([
            SystemMessage(content=_INTENT_SYSTEM),
            HumanMessage(content=message),
        ])
        intent = out.intent if out.intent in ALLOWED_INTENTS else "general_chat"
        confidence = max(0.0, min(1.0, float(out.confidence)))
        return {"intent": intent, "confidence": confidence, "reason": out.reason}
    except Exception:
        return _keyword_fallback(message)
