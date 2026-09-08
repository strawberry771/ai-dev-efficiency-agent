"""Historical issue store: loading + keyword retrieval."""
from server.issues.issue_store import load_issues, search_issue


def test_load_issues_has_ten():
    issues = load_issues()
    assert len(issues) == 10
    assert all(i["issue_id"].startswith("ISSUE-") for i in issues)


def test_search_issue_matches_verification_fail():
    results = search_issue("验证码正确但登录失败")
    assert results
    assert results[0]["issue_id"] == "ISSUE-001"


def test_search_issue_returns_empty_for_no_match():
    assert search_issue("zzzqqqwww") == []


def test_search_issue_scores_descending():
    results = search_issue("验证码登录失败")
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_issue_annotates_reason():
    results = search_issue("验证码正确但登录失败")
    for r in results:
        assert "match_reason" in r
