"""Intent router: deterministic keyword fallback + LLM path (mocked)."""
from server.agent.router import classify_intent, _keyword_fallback, ALLOWED_INTENTS, IntentResult


def test_keyword_fallback_test_case():
    assert _keyword_fallback("生成测试用例")["intent"] == "test_case_generation"


def test_keyword_fallback_issue():
    assert _keyword_fallback("以前有没有类似问题")["intent"] == "issue_query"


def test_keyword_fallback_knowledge():
    assert _keyword_fallback("验证码有效期多久")["intent"] == "knowledge_query"


class _RaisingLLM:
    def with_structured_output(self, schema, method=None):
        raise RuntimeError("boom")


def test_classify_intent_falls_back_on_error():
    result = classify_intent(_RaisingLLM(), "生成测试用例")
    assert result["intent"] in ALLOWED_INTENTS


class _FakeLLM:
    def with_structured_output(self, schema, method=None):
        return self

    def invoke(self, messages):
        return IntentResult(intent="issue_query", confidence=0.9, reason="test")


def test_classify_intent_returns_llm_result():
    result = classify_intent(_FakeLLM(), "以前有没有类似问题")
    assert result["intent"] == "issue_query"
    assert result["confidence"] == 0.9
