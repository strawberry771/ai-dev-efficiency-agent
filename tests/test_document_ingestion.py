"""Document ingestion: type inference + metadata enrichment."""
from pathlib import Path

import pytest

from server.rag.knowledge import (
    _infer_document_type,
    load_knowledge_documents,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS = PROJECT_ROOT / "data" / "documents"


def test_infer_document_type_prd():
    assert _infer_document_type(Path("01_login_prd.md"), ".md") == "prd"


def test_infer_document_type_technical_design():
    assert _infer_document_type(Path("02_login_technical_design.md"), ".md") == "technical_design"


def test_infer_document_type_test_spec():
    assert _infer_document_type(Path("03_login_test_spec.md"), ".md") == "test_spec"


def test_infer_document_type_fallback_pdf():
    assert _infer_document_type(Path("report.pdf"), ".pdf") == "pdf"


def test_load_knowledge_documents_metadata():
    paths = sorted(str(p) for p in DOCS.glob("*.md"))
    docs = load_knowledge_documents(paths)
    assert len(docs) > 0
    for d in docs:
        assert d.metadata["doc_id"]
        assert d.metadata["document_type"] in {"prd", "technical_design", "test_spec"}
        assert d.metadata["filename"]
        assert d.metadata["source_path"]


def test_load_knowledge_documents_rejects_unsupported():
    with pytest.raises(ValueError):
        load_knowledge_documents(["x.docx"])
