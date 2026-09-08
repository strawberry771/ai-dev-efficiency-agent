import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from server.config import CONFIG
from server.rag.embeddings import get_embedder
from server.rag.index import index_knowledge_base
from server.rag.knowledge import SUPPORTED_EXTS, add_document_to_store
from server.agent.workflow import build_workflow, run_workflow
from server.metrics.tracker import MetricsTracker
from shared.utils import file_sha256
from server.observability.langsmith import init_langsmith

init_langsmith()

app = FastAPI(title="AI 研发效能 Agent API")

WORKSPACE = Path(CONFIG["WORKSPACE_DIR"])
UPLOAD_DIR = WORKSPACE / "uploads"
KNOWLEDGE_DB = WORKSPACE / "knowledge_db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -----------------------------
# Runtime (lazy singleton)
# -----------------------------
_runtime = {}
_runtime_lock = threading.Lock()


def _build_runtime():
    embedder = get_embedder(CONFIG["EMBEDDING_MODEL_PATH"])
    llm = ChatOpenAI(
        model=CONFIG["MODEL_NAME"],
        temperature=0,
        api_key=CONFIG["DEEPSEEK_API_KEY"],
        base_url=CONFIG["DEEPSEEK_BASE_URL"],
    )
    vectordb, _, _ = index_knowledge_base(embedder, str(KNOWLEDGE_DB))
    graph = build_workflow(vectordb, llm)
    return {"embedder": embedder, "llm": llm, "vectordb": vectordb, "graph": graph}


def _get_runtime():
    if "graph" not in _runtime:
        with _runtime_lock:
            if "graph" not in _runtime:
                _runtime.update(_build_runtime())
    return _runtime


def _add_document(path: str):
    """Append a new document to the live store in place.

    Reuses the existing runtime singleton; the compiled graph holds the same
    ``vectordb`` object, so new chunks are visible to subsequent queries without
    a rebuild (which would hit Windows file locks on the open Chroma directory).
    """
    rt = _get_runtime()
    with _runtime_lock:
        chunks = add_document_to_store(rt["vectordb"], path)
    return rt["vectordb"], chunks


# -----------------------------
# Session store (in-memory)
# -----------------------------
SESSIONS = {}


# -----------------------------
# Schemas
# -----------------------------
class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    task_id: str
    answer: str
    intent: str
    citations: list
    latency_ms: int
    requires_confirmation: bool
    success: bool


class FeedbackRequest(BaseModel):
    task_id: str
    feedback: str  # accepted | edited_and_accepted | rejected
    edited: bool = False
    edited_answer: Optional[str] = None


# -----------------------------
# Health
# -----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


# -----------------------------
# Document upload
# -----------------------------
@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTS:
        return {"error": f"Unsupported document type: {ext}"}

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    data = await file.read()
    file_id = file_sha256(data)
    dest = UPLOAD_DIR / f"{file_id}{ext}"
    dest.write_bytes(data)

    _, chunks = _add_document(str(dest))
    return {
        "filename": file.filename,
        "stored_as": dest.name,
        "chunks": chunks,
    }


# Backward-compatible alias
@app.post("/upload_pdf")
async def upload_pdf(file: UploadFile = File(...)):
    return await upload_document(file)


# -----------------------------
# Chat
# -----------------------------
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    rt = _get_runtime()
    task_id = str(uuid.uuid4())

    history: List[BaseMessage] = SESSIONS.get(req.session_id, [])
    history = history + [HumanMessage(content=req.message)]

    started = _now_iso()
    state = run_workflow(rt["graph"], history, req.session_id, task_id)
    finished = _now_iso()

    tracker = MetricsTracker(str(WORKSPACE / "product_metrics.db"))
    tracker.record_task(
        task_id=task_id,
        session_id=req.session_id,
        intent=state.get("intent", "general_chat"),
        started_at=started,
        finished_at=finished,
        latency_ms=state.get("latency_ms", 0),
        success=bool(state.get("success", False)),
    )

    answer = state.get("final_answer", "")
    SESSIONS[req.session_id] = history + [AIMessage(content=answer)]

    return ChatResponse(
        task_id=task_id,
        answer=answer,
        intent=state.get("intent", "general_chat"),
        citations=state.get("citations", []),
        latency_ms=state.get("latency_ms", 0),
        requires_confirmation=bool(state.get("requires_confirmation", False)),
        success=bool(state.get("success", False)),
    )


# -----------------------------
# Feedback
# -----------------------------
@app.post("/feedback")
def feedback(req: FeedbackRequest):
    tracker = MetricsTracker(str(WORKSPACE / "product_metrics.db"))
    ok = tracker.record_feedback(req.task_id, req.feedback, req.edited, req.edited_answer)
    return {"status": "ok" if ok else "task_not_found"}


# -----------------------------
# Metrics summary
# -----------------------------
@app.get("/metrics/summary")
def metrics_summary():
    tracker = MetricsTracker(str(WORKSPACE / "product_metrics.db"))
    return tracker.summary()
