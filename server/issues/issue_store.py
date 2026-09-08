"""Historical issue store with keyword/fuzzy scoring.

Issues are synthetic demo data in ``data/issues/issues.json``. Retrieval is a
simple, explainable keyword-overlap scorer over title / symptom / root_cause /
tags / module — no embedding index, so it is stable and easy to reason about.

A title hit is weighted twice as strongly as a body hit. The score is the
weighted coverage of the query's terms (0.0–1.0). When nothing matches,
``search_issue`` returns an empty list — callers must never fabricate an issue
id from an empty result.
"""
import json
import re
from pathlib import Path
from typing import List, Optional

DEFAULT_ISSUES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "issues" / "issues.json"

_CJK = re.compile(r"[一-鿿]+")
_ASCII = re.compile(r"[a-z0-9]+")


def _terms(text: str) -> set:
    """Tokenize text into ASCII words and Chinese character bigrams."""
    text = (text or "").lower()
    terms = set(_ASCII.findall(text))
    for run in _CJK.findall(text):
        if len(run) == 1:
            terms.add(run)
        else:
            terms.update(run[i:i + 2] for i in range(len(run) - 1))
    return terms


def load_issues(path: Optional[str] = None) -> List[dict]:
    p = Path(path) if path else DEFAULT_ISSUES_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("issues", [])


def search_issue(query: str, top_k: int = 5, min_score: float = 0.05) -> List[dict]:
    """Keyword-overlap search over the issue store.

    Returns matches sorted by score (descending), each annotated with
    ``score`` and ``match_reason``. Returns ``[]`` when nothing matches.
    """
    qterms = _terms(query)
    if not qterms:
        return []

    results = []
    for issue in load_issues():
        title = issue.get("title", "").lower()
        body = " ".join([
            issue.get("symptom", ""),
            issue.get("root_cause", ""),
            issue.get("resolution", ""),
            issue.get("module", ""),
            " ".join(issue.get("tags", [])),
        ]).lower()

        title_terms = _terms(issue.get("title", ""))
        hit_fields = []
        weighted = 0
        for t in qterms:
            if t in title_terms:
                weighted += 2
                hit_fields.append("title")
            elif t in body:
                weighted += 1
                hit_fields.append("body")

        if weighted == 0:
            continue

        results.append({
            **issue,
            "score": round(weighted / (2 * len(qterms)), 4),
            "match_reason": "matched: " + ", ".join(sorted(set(hit_fields))),
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return [r for r in results[:top_k] if r["score"] >= min_score]
