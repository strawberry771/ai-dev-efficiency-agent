# =============================
# CONFIG
# =============================
from dotenv import load_dotenv
import os
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EMBEDDING_PATH = PROJECT_ROOT / "models" / "bge-small-zh-v1.5"
EMBEDDING_MODEL_NAME = "AI-ModelScope/bge-small-zh-v1.5"


def resolve_embedding_model() -> str:
    """Resolve the local embedding model path (runtime never hits the network).

    Priority:
      1. EMBEDDING_MODEL_PATH env var (explicit override).
      2. Project-local models/bge-small-zh-v1.5.
      3. Otherwise: raise a clear error.
    """
    env_path = os.getenv("EMBEDDING_MODEL_PATH")
    if env_path:
        return str(Path(env_path).expanduser().resolve())

    if DEFAULT_EMBEDDING_PATH.is_dir():
        return str(DEFAULT_EMBEDDING_PATH.resolve())

    raise FileNotFoundError(
        "Embedding model not found. Run scripts/download_embedding_model.py first."
    )


def load_config():
    load_dotenv()

    config = {
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
        "SERPER_API_KEY": os.getenv("SERPER_API_KEY"),
        "MODEL_NAME": "deepseek-chat",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "EMBEDDING_MODEL_NAME": EMBEDDING_MODEL_NAME,
        "EMBEDDING_MODEL_PATH": resolve_embedding_model(),
        "WORKSPACE_DIR": ".rag_workspace",
    }

    if not config["DEEPSEEK_API_KEY"]:
        st.error("❌ DEEPSEEK_API_KEY missing in environment.")
    if not config["SERPER_API_KEY"]:
        st.error("❌ SERPER_API_KEY missing in environment.")

    return config


CONFIG = load_config()
