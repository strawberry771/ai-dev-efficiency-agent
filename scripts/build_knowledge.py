"""Index the development knowledge base (data/documents/) into Chroma.

Usage:
    python scripts/build_knowledge.py

Reads every supported document in data/documents/ (PDF / Markdown / TXT),
embeds them with the local model and persists a Chroma store at
.rag_workspace/knowledge_db.
"""
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.config import CONFIG
from server.rag.embeddings import get_embedder
from server.rag.knowledge import SUPPORTED_EXTS, load_knowledge_documents, build_knowledge_store

DOCS_DIR = Path("data/documents")
PERSIST_DIR = Path(".rag_workspace/knowledge_db")


def main():
    paths = sorted(
        p for p in DOCS_DIR.glob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    )
    if not paths:
        raise SystemExit(f"No supported documents found in {DOCS_DIR}")

    docs = load_knowledge_documents([str(p) for p in paths])
    print(f"Loaded {len(docs)} raw segments from {len(paths)} files")

    embedder = get_embedder(CONFIG["EMBEDDING_MODEL_PATH"])

    if PERSIST_DIR.exists():
        shutil.rmtree(PERSIST_DIR)

    vectordb = build_knowledge_store(docs, embedder, str(PERSIST_DIR))
    print(f"Indexed {vectordb._collection.count()} chunks into {PERSIST_DIR}")


if __name__ == "__main__":
    main()
