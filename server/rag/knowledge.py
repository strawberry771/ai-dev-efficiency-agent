"""Multi-document development knowledge base.

Upgrades the single-PDF session flow to a repository of development docs
(PRD / technical design / test specs) that can be indexed and searched
together. Supports at least PDF, Markdown and plain-text sources.

Every chunk is annotated with:
  doc_id, filename, document_type, page (PDF) or section (Markdown),
  chunk_id, source_path.
"""
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter

from shared.utils import file_sha256

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SUPPORTED_EXTS = {".pdf", ".md", ".markdown", ".txt"}

# Markdown header levels that become the ``section`` metadata field.
_HEADERS = [
    ("#", "section"),
    ("##", "section"),
]


def _doc_id(path: Path) -> str:
    return file_sha256(path.read_bytes())


def _infer_document_type(path: Path, ext: str) -> str:
    """Derive a semantic document category from the filename, falling back
    to the file format when no category is recognizable."""
    name = path.stem.lower()
    if "prd" in name or "requirement" in name:
        return "prd"
    if "test" in name or "spec" in name or "case" in name:
        return "test_spec"
    if "design" in name or "technical" in name or "arch" in name:
        return "technical_design"
    if ext == ".pdf":
        return "pdf"
    if ext in (".md", ".markdown"):
        return "markdown"
    return "text"


def _load_pdf(path: Path) -> List[Document]:
    loader = PyPDFLoader(str(path))
    docs = loader.load()
    if not docs:
        raise ValueError(f"PDF contains no extractable text: {path}")
    return docs


def _load_markdown(path: Path) -> List[Document]:
    text = path.read_text(encoding="utf-8")
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=_HEADERS)
    docs = splitter.split_text(text)
    return docs or [Document(page_content=text)]


def _load_text(path: Path) -> List[Document]:
    text = path.read_text(encoding="utf-8")
    return [Document(page_content=text)]


def _relative_source(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def _enrich(docs: List[Document], path: Path, doc_id: str, document_type: str) -> List[Document]:
    for d in docs:
        md = dict(d.metadata or {})
        md["doc_id"] = doc_id
        md["filename"] = path.name
        md["document_type"] = document_type
        md["source_path"] = _relative_source(path)
        if md.get("page") is not None:
            md["page"] = int(md["page"])
        d.metadata = md
    return docs


def load_knowledge_documents(paths: List[str]) -> List[Document]:
    """Load every supported document and attach doc-level metadata."""
    docs: List[Document] = []
    for raw in paths:
        path = Path(raw)
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTS:
            raise ValueError(f"Unsupported document type: {ext} ({path.name})")

        doc_id = _doc_id(path)
        dtype = _infer_document_type(path, ext)
        if ext == ".pdf":
            loaded = _load_pdf(path)
        elif ext in (".md", ".markdown"):
            loaded = _load_markdown(path)
        else:
            loaded = _load_text(path)

        docs.extend(_enrich(loaded, path, doc_id, dtype))
    return docs


def build_knowledge_store(
    documents: List[Document],
    embedder,
    persist_dir: str,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> Chroma:
    """Split documents into chunks, assign ``chunk_id``, and build + persist Chroma."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    splits = splitter.split_documents(documents)

    counters = {}
    for s in splits:
        md = dict(s.metadata or {})
        doc_id = md.get("doc_id", "unknown")
        idx = counters.get(doc_id, 0)
        md["chunk_id"] = f"{doc_id}:{idx}"
        counters[doc_id] = idx + 1
        s.metadata = md

    vectordb = Chroma.from_documents(
        splits,
        embedder,
        persist_directory=persist_dir,
    )
    vectordb.persist()
    return vectordb


def search_knowledge(vectordb: Chroma, query: str, k: int = 5, filter: dict = None) -> List[dict]:
    """Retrieve top-k chunks with metadata and a similarity score.

    Chroma returns an L2 *distance* (lower is more relevant). Because the
    embedding model L2-normalizes vectors, ``score = 1 - distance / 2`` is
    exactly the cosine similarity (higher is more relevant). The raw distance
    is also returned for transparency.

    ``filter`` is an optional Chroma metadata filter (e.g.
    ``{"document_type": "prd"}``).
    """
    hits = vectordb.similarity_search_with_score(query, k=k, filter=filter)
    results = []
    for doc, distance in hits:
        md = doc.metadata or {}
        results.append({
            "content": doc.page_content,
            "source": md.get("filename", ""),
            "source_path": md.get("source_path", ""),
            "document_type": md.get("document_type", ""),
            "page": md.get("page"),
            "section": md.get("section"),
            "chunk_id": md.get("chunk_id"),
            "score": 1 - float(distance) / 2,
            "distance": float(distance),
        })
    return results
