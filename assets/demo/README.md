# Demo Screenshots

> **Demo screenshots will be generated after local deployment.**

本目录用于存放「AI 研发效能 Agent」的**真实运行截图**（产品 Demo 展示用）。
当前仓库**尚未内置截图**——以下 4 张截图需在本地把系统跑起来后，从真实运行界面截取，
**不生成、不使用任何伪造的运行截图**。

## 需要的 4 张截图

| 文件名 | 展示内容 | 对应能力 |
| --- | --- | --- |
| `01_chat.png` | 用户提问 → Agent 回答 + Citation 来源 | 知识问答 |
| `02_agent_trace.png` | Agent 执行过程：Intent → Tool → Retrieved → Latency | Agent Router / Tool 调用 / 检索 |
| `03_source_reference.png` | 回答中的引用：Source / Section | RAG 可溯源 |
| `04_feedback.png` | 采纳 / 修改后采纳 / 不采纳 按钮 | 人工反馈闭环 |

## 如何生成真实截图

1. **环境准备**（详见根目录 `README.md`「安装与配置」）：
   安装依赖、配置 `.env`（`DEEPSEEK_API_KEY`）、下载 Embedding 模型
   （`python scripts/download_embedding_model.py`）、构建知识库
   （`python scripts/build_knowledge.py`）。

2. **启动后端**：
   ```bash
   uvicorn server.main:app --host 0.0.0.0 --port 8000
   ```

3. **启动前端**：
   ```bash
   streamlit run client/app.py
   ```

4. 浏览器打开 `http://localhost:8501`，按下方示例提问并截取对应画面。

### 各截图对应示例

- **`01_chat.png`** — 输入 `验证码连续输错 5 次会发生什么？`，
  截取「问题 + 回答 + Citation」区域，展示知识问答能力。
- **`02_agent_trace.png`** — 展开回答下方的「🔍 Agent 执行过程」，
  截取 `Intent` / `Tools` / `Retrieved chunks` / `Latency`，突出 Agent Router、Tool 调用与检索过程。
- **`03_source_reference.png`** — 展开「📎 Citation」，截取 `Source` / `Section`
  （如 `01_login_prd.md` · 连续失败策略），突出 RAG 可溯源。
- **`04_feedback.png`** — 截取回答下方的「✅ 采纳 / ✏️ 修改后采纳 / ❌ 不采纳」按钮区域，
  展示反馈闭环（记录 `accepted` / `edited_and_accepted` / `rejected`，用于统计采纳率）。

## 截取后

将 4 张 PNG 按上表文件名放入本目录，根目录 `README.md` 的「Demo 演示（产品截图）」一节
即可引用它们展示。
