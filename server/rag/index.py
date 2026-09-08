"""Index the development knowledge base from source directories."""
import shutil
from pathlib import Path
from typing import List

from server.rag.knowledge import (
    SUPPORTED_EXTS,
    load_knowledge_documents,
    build_knowledge_store,
)

# Demo docs (committed) plus user uploads (gitignored).
DOCUMENT_DIRS = [Path("data/documents"), Path(".rag_workspace/uploads")]


def collect_document_paths(dirs: List[Path] = None) -> List[Path]:
    dirs = dirs or DOCUMENT_DIRS
    paths: List[Path] = []
    for d in dirs:
        if d.is_dir():
            paths.extend(sorted(
                p for p in d.glob("*")
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
            ))
    return paths


def index_knowledge_base(embedder, persist_dir: str, dirs: List[Path] = None):
    """Load all documents and (re)build + persist the Chroma store.

    Returns ``(vectordb, doc_count, chunk_count)``.
    """
    paths = collect_document_paths(dirs)
    docs = load_knowledge_documents([str(p) for p in paths])

    # Clean rebuild so stale chunks from previous indexes never linger.
    p = Path(persist_dir)
    if p.exists():
        shutil.rmtree(p)

    vectordb = build_knowledge_store(docs, embedder, persist_dir)
    return vectordb, len(docs), vectordb._collection.count()
