"""Knowledge-base search: scoring, ranking, and metadata filter."""
from pathlib import Path

import pytest

from server.config import CONFIG
from server.rag.embeddings import get_embedder
from server.rag.knowledge import (
    load_knowledge_documents,
    build_knowledge_store,
    search_knowledge,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def vectordb(tmp_path_factory):
    embedder = get_embedder(CONFIG["EMBEDDING_MODEL_PATH"])
    paths = sorted(str(p) for p in (PROJECT_ROOT / "data" / "documents").glob("*.md"))
    docs = load_knowledge_documents(paths)
    persist = tmp_path_factory.mktemp("chroma")
    return build_knowledge_store(docs, embedder, str(persist))


def test_search_returns_scored_results(vectordb):
    results = search_knowledge(vectordb, "验证码有效期是多久")
    assert results
    for r in results:
        assert 0.0 <= r["score"] <= 1.0
        assert r["source"]
        assert r["chunk_id"]


def test_relevant_source_in_top3(vectordb):
    results = search_knowledge(vectordb, "密码登录时凭证和什么校验", k=3)
    sources = [r["source"] for r in results]
    assert "01_login_prd.md" in sources


def test_search_with_document_type_filter(vectordb):
    results = search_knowledge(vectordb, "验证码有效期", filter={"document_type": "prd"})
    assert results
    assert all(r["document_type"] == "prd" for r in results)


def test_score_is_cosine_from_distance(vectordb):
    results = search_knowledge(vectordb, "验证码有效期")
    assert results
    for r in results:
        assert abs((1 - r["distance"] / 2) - r["score"]) < 1e-6
