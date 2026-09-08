"""AI 研发效能 Agent — Streamlit frontend.

Talks to the FastAPI backend (``server/main.py``) over HTTP. Two-panel layout:

  * left  — 研发知识库：上传文件、文档类型、已索引文档
  * right — 对话 + Agent Answer / 调用路径 / Citation，底部反馈按钮

The "Agent 执行过程" expander shows only the deterministic pipeline
(intent → tools → retrieved chunks → latency); it never surfaces any LLM
chain-of-thought or hidden reasoning.
"""
import uuid

import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="AI 研发效能 Agent",
    page_icon="🛠️",
    layout="wide",
)

st.title("🛠️ AI 研发效能 Agent")
st.caption("知识库问答 · 历史 Issue 检索 · 测试用例生成 · 引用溯源 · 人工反馈")

# -----------------------------
# Session state
# -----------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "chat" not in st.session_state:
    st.session_state.chat = []  # list[dict]: role, content, meta
if "feedback" not in st.session_state:
    st.session_state.feedback = {}  # task_id -> feedback label


def _api(method: str, path: str, **kwargs):
    """Call the backend and return the parsed JSON, or None on failure."""
    try:
        resp = requests.request(method, f"{API_BASE}{path}", timeout=120, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


# -----------------------------
# Left panel — knowledge base
# -----------------------------
left, right = st.columns([1, 2.2], gap="large")

with left:
    st.subheader("📚 研发知识库")

    uploaded = st.file_uploader(
        "上传文件",
        type=["pdf", "md", "markdown", "txt"],
        help="上传后自动分词、嵌入并增量索引到本地 Chroma 向量库",
    )
    if uploaded is not None:
        with st.spinner("上传并索引中…"):
            result = _api(
                "POST",
                "/documents/upload",
                files={"file": (uploaded.name, uploaded.getvalue())},
            )
        if result and "error" in result:
            st.error(result["error"])
        elif result:
            st.success(f"已索引 {uploaded.name}（{result.get('chunks', 0)} 个分块）")
        else:
            st.error("上传失败：请确认后端已启动（uvicorn server.main:app）。")

    st.markdown("**已索引文档**")
    docs = _api("GET", "/documents")
    if docs:
        rows = docs.get("documents", [])
        if rows:
            st.caption(f"共 {len(rows)} 份文档")
            # document type filter
            types = ["全部"] + sorted({r["document_type"] for r in rows})
            picked = st.selectbox("文档类型", types, key="doc_type_filter")
            if picked != "全部":
                rows = [r for r in rows if r["document_type"] == picked]
            for r in rows:
                st.markdown(
                    f"- **{r['filename']}** · `{r['document_type']}` · {r['chunks']} chunks"
                )
        else:
            st.info("暂无已索引文档。")
    else:
        st.warning("无法获取已索引文档（后端未启动？）。")

# -----------------------------
# Right panel — conversation
# -----------------------------
with right:
    st.subheader("💬 对话")

    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            if msg["role"] == "assistant" and msg.get("meta"):
                meta = msg["meta"]

                st.markdown("**调用路径**：" + " → ".join(meta.get("path", [])))
                if meta.get("tools_used"):
                    st.markdown("**使用工具**：" + "、".join(meta["tools_used"]))
                st.markdown(f"**耗时**：{meta.get('latency_ms', 0)} ms")

                if meta.get("requires_confirmation"):
                    st.warning("⚠️ 该回答建议人工确认。")

                cites = meta.get("citations", [])
                if cites:
                    with st.expander(f"📎 Citation（{len(cites)}）"):
                        for c in cites:
                            loc = c.get("section") or c.get("page") or ""
                            st.markdown(
                                f"- `{c.get('source', '')}`" + (f" · {loc}" if loc else "")
                                + (f" · `{c.get('chunk_id', '')}`" if c.get("chunk_id") else "")
                            )

                # Agent execution process — deterministic facts only, no CoT
                with st.expander("🔍 Agent 执行过程"):
                    st.markdown(f"**Intent**：`{meta.get('intent', '')}`")
                    st.markdown(f"**Tools**：`{meta.get('tools_used', [])}`")
                    st.markdown("**Retrieved chunks**：")
                    for i, item in enumerate(meta.get("retrieved", []), 1):
                        if item.get("source", "").startswith("ISSUE-"):
                            st.markdown(
                                f"{i}. `{item.get('source')}` {item.get('title', '')} "
                                f"（score={item.get('score')}）"
                            )
                        else:
                            loc = item.get("section") or item.get("page") or ""
                            st.markdown(
                                f"{i}. `{item.get('source')}`{(' · ' + str(loc)) if loc else ''} "
                                f"（score={item.get('score')}）\n\n"
                                f"> {(item.get('excerpt') or '').strip()}"
                            )
                    st.markdown(f"**Latency**：{meta.get('latency_ms', 0)} ms")

    prompt = st.chat_input("输入研发问题，例如：验证码连续输错5次会发生什么？")

    if prompt:
        st.session_state.chat.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Agent 处理中…"):
                data = _api(
                    "POST",
                    "/chat",
                    json={"session_id": st.session_state.session_id, "message": prompt},
                )

            if data is None:
                answer = "后端未响应，请确认已启动 uvicorn server.main:app。"
                meta = {}
            else:
                answer = data.get("answer", "")
                meta = {
                    "task_id": data.get("task_id"),
                    "intent": data.get("intent"),
                    "path": data.get("path", []),
                    "tools_used": data.get("tools_used", []),
                    "retrieved": data.get("retrieved", []),
                    "citations": data.get("citations", []),
                    "latency_ms": data.get("latency_ms", 0),
                    "requires_confirmation": data.get("requires_confirmation", False),
                }

            st.markdown(answer)
            st.session_state.chat.append({"role": "assistant", "content": answer, "meta": meta})

# -----------------------------
# Feedback (bottom, for the latest assistant turn)
# -----------------------------
assistant_turns = [m for m in st.session_state.chat if m["role"] == "assistant"]
if assistant_turns:
    last = assistant_turns[-1]
    task_id = (last.get("meta") or {}).get("task_id")
    if not task_id:
        pass
    else:
        fb = st.session_state.feedback.get(task_id)
        st.divider()
        st.markdown("**这条回答有帮助吗？**")
        if fb is None:
            col_a, col_b, col_c = st.columns([1, 1, 1])
            with col_a:
                if st.button("✅ 采纳", key=f"acc-{task_id}"):
                    _api("POST", "/feedback", json={"task_id": task_id, "feedback": "accepted", "edited": False})
                    st.session_state.feedback[task_id] = "accepted"
                    st.rerun()
            with col_b:
                if st.button("✏️ 修改后采纳", key=f"edit-{task_id}"):
                    st.session_state.feedback[task_id] = "editing"
                    st.rerun()
            with col_c:
                if st.button("❌ 不采纳", key=f"rej-{task_id}"):
                    _api("POST", "/feedback", json={"task_id": task_id, "feedback": "rejected", "edited": False})
                    st.session_state.feedback[task_id] = "rejected"
                    st.rerun()
        elif fb == "editing":
            edited = st.text_area("修改后的答案", key=f"edit-area-{task_id}")
            if st.button("提交修改", key=f"submit-edit-{task_id}") and edited.strip():
                _api(
                    "POST",
                    "/feedback",
                    json={"task_id": task_id, "feedback": "edited_and_accepted", "edited": True, "edited_answer": edited},
                )
                st.session_state.feedback[task_id] = "edited_and_accepted"
                st.rerun()
        else:
            st.caption(f"已反馈：{fb}")
