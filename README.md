# AI 研发效能 Agent

一个面向研发团队的 **RAG 智能助手**：基于本地知识库（PRD / 技术设计 / 测试资料）与历史 Issue 库，提供**知识问答、历史故障检索、测试用例生成**三大能力，并做到**引用可溯源、答案可人工反馈、指标可量化**。

后端为 **FastAPI + LangGraph**，前端为 **Streamlit**，向量检索使用 **Chroma + 本地 bge-small-zh-v1.5 中文 Embedding**，LLM 使用 **DeepSeek（deepseek-chat）**。

---

## Demo 演示（产品截图）

| 截图 | 展示内容 |
| --- | --- |
| `assets/demo/01_chat.png` | 知识问答：用户提问 → Agent 回答 + Citation 溯源 |
| `assets/demo/02_agent_trace.png` | Agent 执行过程：Intent → Tool → Retrieved → Latency |
| `assets/demo/03_source_reference.png` | 引用溯源：Source / Section（RAG 可溯源） |
| `assets/demo/04_feedback.png` | 人工反馈闭环：采纳 / 修改后采纳 / 不采纳 |

> ⚠️ 截图待补充：本仓库当前未内置运行截图。真实截图将在本地部署后从真实运行界面截取（**不伪造**），
> 截取方式见 [`assets/demo/README.md`](assets/demo/README.md)。

---

## 1. 项目目标与能力

目标：把「检索增强」落到研发日常场景，让助手**只回答有依据的内容，并保留每一步的引用来源**。核心能力：

1. 多文档知识库（PDF / Markdown / TXT，带文档类型元数据）
2. 历史 Issue 库检索（关键词加权打分）
3. 三大确定性工具：知识检索 / Issue 检索 / 测试用例生成
4. 意图路由（知识 / Issue / 测试用例 / 闲聊 四分类）
5. LangGraph 确定性工作流（非 LLM 自由 tool-calling）
6. 引用溯源（Citation）——只引用真实检索到的来源，杜绝编造
7. 证据不足降级（检索不到依据时如实告知，不强行回答）
8. 人工反馈闭环（采纳 / 修改后采纳 / 不采纳）
9. SQLite 指标统计（完成率、采纳率、编辑率、延迟分位数）
10. 结构化测试用例输出（`basis_type` 区分「文档依据 / AI 建议」）
11. FastAPI 接口 + Streamlit 双面板 UI
12. 离线可复现的评测（产品指标评测脚本 + 30 条数据集）

---

## 2. 系统架构

```mermaid
flowchart TB
    subgraph Experience["交互层 · Experience"]
        direction LR
        USER(["研发人员"])
        UI["Streamlit 双面板<br/>文档上传 · 任务对话 · Agent Trace"]
        REVIEW["人工确认<br/>采纳 · 修改后采纳 · 不采纳"]
    end

    subgraph Access["接入层 · FastAPI"]
        direction LR
        API["API Gateway<br/>/documents · /chat · /feedback · /metrics"]
        SESSION[("内存 Session<br/>会话上下文")]
        RT["Lazy Runtime Singleton<br/>模型与索引惰加载"]
    end

    subgraph Orchestration["Agent 编排层 · LangGraph"]
        direction LR
        WF["确定性 Workflow<br/>状态流转与分支编排"]
        ROUTER{"Intent Router<br/>结构化输出 + 规则兜底"}
        K["search_knowledge"]
        I["search_issue"]
        T["generate_test_cases"]
        DIRECT["direct_answer"]
    end

    subgraph Intelligence["模型与结果治理"]
        direction LR
        LLM[["DeepSeek<br/>deepseek-chat"]]
        CITE["Citation Builder<br/>仅从检索 metadata 生成"]
        GUARD{"证据与不确定性检查"}
        ANSWER["可追溯结果<br/>答案 · 引用 · 执行路径"]
    end

    subgraph Knowledge["知识与数据层"]
        direction LR
        DOCS[("data/documents<br/>PRD · 技术设计 · 测试资料")]
        INGEST["多文档解析与分块<br/>PDF · MD · TXT · DOCX"]
        EMB["本地 Embedding<br/>bge-small-zh-v1.5"]
        CH[("Chroma<br/>知识向量库")]
        ISSUES[("issues.json<br/>历史问题库")]
    end

    subgraph Feedback["反馈与度量层"]
        direction LR
        TRACKER["Metrics Tracker<br/>任务、意图、耗时、反馈"]
        SQLITE[("SQLite<br/>product_metrics.db")]
        SUMMARY["效果指标<br/>完成率 · 采纳率 · 修改率 · P95"]
    end

    USER --> UI
    UI -->|HTTP / JSON| API
    API --> SESSION
    SESSION --> API
    API --> RT
    RT --> WF
    WF --> ROUTER

    ROUTER -->|知识问答| K
    ROUTER -->|历史问题| I
    ROUTER -->|测试生成| T
    ROUTER -->|通用对话| DIRECT
    ROUTER -.-> LLM

    API -->|文档入库| INGEST
    DOCS --> INGEST
    INGEST --> EMB
    EMB --> CH
    K -->|相似度检索| CH
    I -->|关键词加权| ISSUES
    T -->|结构化生成| LLM
    DIRECT --> LLM

    K --> CITE
    I --> CITE
    T --> CITE
    LLM --> CITE
    CITE --> GUARD
    GUARD --> ANSWER
    ANSWER --> API

    API -->|待确认结果| UI
    UI --> REVIEW
    REVIEW -->|POST /feedback| API
    API --> TRACKER
    TRACKER --> SQLITE
    SQLITE --> SUMMARY

    classDef actor fill:#0F172A,color:#F8FAFC,stroke:#0F172A,stroke-width:1.5px;
    classDef apiNode fill:#EAF2FF,color:#172554,stroke:#3B82F6,stroke-width:1.5px;
    classDef serviceNode fill:#EEF2FF,color:#312E81,stroke:#6366F1,stroke-width:1.5px;
    classDef decisionNode fill:#FFF7E6,color:#78350F,stroke:#F59E0B,stroke-width:1.5px;
    classDef toolNode fill:#ECFDF5,color:#064E3B,stroke:#10B981,stroke-width:1.5px;
    classDef dataNode fill:#F5F3FF,color:#4C1D95,stroke:#8B5CF6,stroke-width:1.5px;
    classDef guardNode fill:#FFF1F2,color:#881337,stroke:#F43F5E,stroke-width:1.5px;
    classDef metricNode fill:#F0FDFA,color:#134E4A,stroke:#14B8A6,stroke-width:1.5px;

    class USER actor;
    class UI,API,ANSWER apiNode;
    class SESSION,RT,WF serviceNode;
    class ROUTER,GUARD decisionNode;
    class K,I,T,DIRECT,INGEST toolNode;
    class DOCS,EMB,CH,ISSUES,SQLITE dataNode;
    class LLM,CITE,REVIEW guardNode;
    class TRACKER,SUMMARY metricNode;

    style Experience fill:#F8FAFC,stroke:#CBD5E1,stroke-width:1px;
    style Access fill:#F8FAFC,stroke:#CBD5E1,stroke-width:1px;
    style Orchestration fill:#F8FAFC,stroke:#CBD5E1,stroke-width:1px;
    style Intelligence fill:#F8FAFC,stroke:#CBD5E1,stroke-width:1px;
    style Knowledge fill:#F8FAFC,stroke:#CBD5E1,stroke-width:1px;
    style Feedback fill:#F8FAFC,stroke:#CBD5E1,stroke-width:1px;
```

---

## 3. 工作流（确定性流水线）

与上游「LLM 自由 tool-calling」不同，本项目的意图路由与工具调用是**确定性的**——意图分类后直接进入固定分支，不存在隐式推理循环。

```mermaid
flowchart TD
    START(["START"]) --> INIT["初始化任务状态<br/>session_id · task_id · messages"]

    subgraph Routing["① 意图识别"]
        CLASSIFY["classify_intent<br/>DeepSeek 结构化输出"]
        VALID{"IntentDecision<br/>是否合法？"}
        FALLBACK["确定性规则兜底<br/>保证路由可用"]
        ROUTE{"route_by_intent"}

        CLASSIFY --> VALID
        VALID -->|是| ROUTE
        VALID -->|否 / 模型异常| FALLBACK --> ROUTE
    end

    INIT --> CLASSIFY

    subgraph Branches["② 确定性工具分支"]
        RK["retrieve_knowledge<br/>search_knowledge"]
        KE{"score ≥ 阈值<br/>且存在有效片段？"}
        RI["retrieve_issue<br/>search_issue"]
        IE{"找到真实<br/>issue_id？"}
        RTK["检索需求上下文<br/>search_knowledge"]
        TE{"需求依据<br/>是否充足？"}
        GT["generate_test_cases<br/>Pydantic Schema + basis_type"]
        DA["direct_answer<br/>通用对话"]
    end

    ROUTE -->|knowledge_query| RK --> KE
    ROUTE -->|issue_query| RI --> IE
    ROUTE -->|test_case_generation| RTK --> TE
    ROUTE -->|general_chat| DA

    subgraph Guardrails["③ 证据边界与降级"]
        NO_K["知识库依据不足<br/>返回固定降级提示"]
        NO_I["未找到历史 Issue<br/>不生成虚构编号"]
        MARK["标记能力边界<br/>documented / ai_suggestion"]
    end

    KE -->|是| GFA
    KE -->|否| NO_K
    IE -->|是| GFA
    IE -->|否| NO_I
    TE -->|是| GT --> MARK --> GFA
    TE -->|否| NO_K
    DA --> GFA

    subgraph Assembly["④ 结果组装与溯源"]
        GFA["generate_final_answer<br/>仅使用已检索上下文"]
        PC["prepare_citations<br/>从 metadata 去重组装"]
        CHECK{"insufficient_evidence<br/>或高不确定性？"}
        FLAG["requires_confirmation = true<br/>建议人工确认"]
        RESULT["结构化响应<br/>答案 · 引用 · 工具 · 耗时"]

        GFA --> PC --> CHECK
        CHECK -->|是| FLAG --> RESULT
        CHECK -->|否| RESULT
    end

    NO_K --> RESULT
    NO_I --> RESULT

    subgraph HumanLoop["⑤ Human-in-the-loop 与指标闭环"]
        TASK[("记录任务<br/>intent · latency · success")]
        CONFIRM{"用户反馈"}
        ACCEPT["采纳<br/>accepted"]
        EDIT["修改后采纳<br/>edited_and_accepted"]
        REJECT["不采纳<br/>rejected"]
        METRICS[("SQLite Metrics<br/>完成率 · 采纳率 · 修改率 · 延迟")]

        RESULT --> TASK --> CONFIRM
        CONFIRM --> ACCEPT --> METRICS
        CONFIRM --> EDIT --> METRICS
        CONFIRM --> REJECT --> METRICS
    end

    METRICS --> END(["END"])

    classDef terminal fill:#0F172A,color:#F8FAFC,stroke:#0F172A,stroke-width:2px;
    classDef process fill:#EAF2FF,color:#172554,stroke:#3B82F6,stroke-width:1.5px;
    classDef decision fill:#FFF7E6,color:#78350F,stroke:#F59E0B,stroke-width:1.5px;
    classDef tool fill:#ECFDF5,color:#064E3B,stroke:#10B981,stroke-width:1.5px;
    classDef fallback fill:#FFF1F2,color:#881337,stroke:#F43F5E,stroke-width:1.5px;
    classDef output fill:#EEF2FF,color:#312E81,stroke:#6366F1,stroke-width:1.5px;
    classDef human fill:#F0FDFA,color:#134E4A,stroke:#14B8A6,stroke-width:1.5px;
    classDef store fill:#F5F3FF,color:#4C1D95,stroke:#8B5CF6,stroke-width:1.5px;

    class START,END terminal;
    class INIT,CLASSIFY,FALLBACK,GFA,PC process;
    class VALID,ROUTE,KE,IE,TE,CHECK,CONFIRM decision;
    class RK,RI,RTK,GT,DA tool;
    class NO_K,NO_I,MARK,FLAG fallback;
    class RESULT output;
    class ACCEPT,EDIT,REJECT human;
    class TASK,METRICS store;

    style Routing fill:#F8FAFC,stroke:#CBD5E1,stroke-width:1px;
    style Branches fill:#F8FAFC,stroke:#CBD5E1,stroke-width:1px;
    style Guardrails fill:#FFF9FA,stroke:#FECDD3,stroke-width:1px;
    style Assembly fill:#F8FAFC,stroke:#CBD5E1,stroke-width:1px;
    style HumanLoop fill:#F6FFFD,stroke:#99F6E4,stroke-width:1px;
    linkStyle default stroke:#64748B,stroke-width:1.25px;
```

---

## 4. 仓库结构

```
.
├── client/app.py                 # Streamlit 双面板 UI
├── assets/demo/                  # 产品演示截图（本地部署后生成，见 assets/demo/README.md）
├── server/
│   ├── main.py                   # FastAPI 接口 + 懒加载 runtime
│   ├── config.py                 # 环境变量 + 本地 Embedding 路径解析
│   ├── agent/
│   │   ├── workflow.py           # LangGraph 确定性工作流（默认路径）
│   │   ├── core_tools.py         # 三大核心工具 + 测试用例 Schema
│   │   ├── router.py             # 意图路由器（DeepSeek 结构化输出 + 关键词兜底）
│   │   ├── state.py              # WorkflowState TypedDict
│   │   ├── graph.py              # 上游旧版 agentic 图（保留，非默认路径）
│   │   └── tools.py              # 上游旧版 Serper/arXiv 工具（保留，非默认路径）
│   ├── rag/
│   │   ├── knowledge.py          # 多文档加载 / 切分 / 建库 / 检索（核心）
│   │   ├── index.py              # 目录扫描 + 全量建索引
│   │   ├── embeddings.py         # 本地 bge-small-zh-v1.5（CPU、L2 归一化）
│   │   ├── loaders.py            # 上游旧版 PDF loader（保留）
│   │   └── vectorstore.py        # 上游旧版 vectorstore（保留）
│   ├── issues/issue_store.py     # 历史 Issue 关键词检索
│   ├── metrics/tracker.py        # SQLite 指标 + 反馈
│   └── observability/langsmith.py # LangSmith 追踪（上游保留）
├── shared/utils.py               # file_sha256 等小工具
├── data/
│   ├── documents/                # 3 份中文演示文档（PRD/技术设计/测试说明）
│   └── issues/issues.json        # 10 条合成历史 Issue
├── evaluation/
│   ├── run_product_eval.py       # 产品指标评测脚本
│   ├── run_ragas.py              # 上游 RAGAS 脚本（保留）
│   ├── datasets/dev_agent_eval.json
│   └── results/latest.json       # 真实评测结果
├── scripts/
│   ├── build_knowledge.py        # 离线建索引
│   └── download_embedding_model.py
└── tests/                        # pytest 测试套件（32 条）
```

---

## 5. 数据设计

- **知识文档**：`data/documents/` 下 3 份中文演示文档，覆盖登录系统的 PRD、技术设计、测试用例说明。**均为演示用合成文档（Demo / synthetic development document）**，不描述任何真实公司或系统，文件头均带免责声明。
- **历史 Issue**：`data/issues/issues.json` 下 10 条合成 Issue（`ISSUE-001` ~ `ISSUE-010`），字段含 `issue_id / title / module / symptom / root_cause / resolution / severity / tags / created_at`。
- **向量库**：Chroma 持久化于 `.rag_workspace/knowledge_db`（已 gitignore）。
- **Embedding**：`AI-ModelScope/bge-small-zh-v1.5`（512 维中文），下载到本地 `models/bge-small-zh-v1.5`（权重不提交 Git）。

---

## 6. RAG 元数据设计

每个检索分块（chunk）都带如下元数据，供引用与过滤：

| 字段 | 含义 |
| --- | --- |
| `doc_id` | 文档内容 SHA-256 前 16 位（内容寻址，去重/定位） |
| `filename` | 源文件名 |
| `document_type` | 语义文档类型：`prd` / `technical_design` / `test_spec`（由文件名推断） |
| `source_path` | 相对项目根路径 |
| `page`（PDF） / `section`（Markdown） | 分块位置 |
| `chunk_id` | `{doc_id}:{idx}`，唯一分块标识 |
| `score` / `distance` | 余弦相似度 / Chroma L2 距离 |

> 相似度换算：由于 Embedding 做了 L2 归一化，`score = 1 - distance / 2` 即为余弦相似度。**代码里明确区分 distance 与 similarity，不把 distance 误当相似度。**

---

## 7. 核心工具（三大确定性工具）

定义于 `server/agent/core_tools.py`，由工作流**直接调用**（非 LLM tool-calling），返回结构化 dict：

1. **`search_knowledge(query, document_type, top_k)`** — 检索知识库，返回 `{results, insufficient_evidence}`。相似度低于阈值（`MIN_SIMILARITY=0.45`）时判定「证据不足」。
2. **`search_issue(query, top_k)`** — 关键词加权检索历史 Issue（标题命中 ×2，正文 ×1），返回空列表即「未命中」，**绝不从空结果编造 Issue 编号**。
3. **`generate_test_cases(requirement, retrieved_context, count)`** — 用 DeepSeek 结构化输出生成测试用例，`basis_type` 严格区分 `documented`（有文档依据）与 `ai_suggestion`（AI 补充建议）。

---

## 8. 意图路由

`server/agent/router.py` 将用户输入分为四类：`knowledge_query / issue_query / test_case_generation / general_chat`。

- 主路径：DeepSeek `with_structured_output(IntentResult, method="function_calling")`。
- 兜底路径：LLM 调用异常时回退到确定性关键词规则，**始终返回合法意图**。

---

## 9. 引用溯源与非编造（Citation / No Fabrication）

- 引用（citation）**只来自真实检索结果**，在 `prepare_citations` 节点从 `retrieved_context` 元数据构建，不包含任何模型幻觉来源。
- 最终答案 prompt 明确要求「仅根据检索片段回答，用 `[1][2]` 标注引用来源，不要编造来源或超出片段内容」。
- 检索不到依据时返回固定提示（`当前知识库未检索到足够依据。` / `未找到匹配的历史 Issue。`），而非强行生成。
- 测试用例中 `basis_type=ai_suggestion` 会显式标注为「AI 建议」，并在响应中提示「建议人工确认」。

---

## 10. Human-in-the-Loop（人工反馈闭环）

- 前端对每条回答提供 **采纳 / 修改后采纳 / 不采纳** 三个按钮。
- 采纳率偏低或出现「AI 建议」型测试用例时，回答会追加 `（建议人工确认）` 提示。
- 反馈通过 `POST /feedback` 写回 SQLite，供指标统计与后续优化参考。

---

## 11. 指标定义（Metrics）

`server/metrics/tracker.py` 以 SQLite 表 `tasks` 记录每任务一行（仅任务元数据与反馈，不存查询/答案内容）。`GET /metrics/summary` 返回：

| 指标 | 定义 |
| --- | --- |
| `task_completion_rate` | 成功任务数 / 总任务数 |
| `acceptance_rate` | （采纳 + 修改后采纳）/ 有反馈任务数 |
| `direct_accept_rate` | 直接采纳 / 有反馈任务数 |
| `human_edit_rate` | 修改后采纳 /（采纳 + 修改后采纳） |
| `latency_ms.mean / p50 / p95` | 端到端延迟均值与分位数 |

---

## 12. 前置条件

- Python 3.11+
- 依赖安装工具：`uv` 或 `pip`（本环境用 `.venv` + `pip`）
- 环境变量（`.env`，已 gitignore，模板见 `.env.example`）：
  - `DEEPSEEK_API_KEY`（必需，用于 LLM）
  - `SERPER_API_KEY`（可选——仅上游旧版 web 搜索工具使用，**默认工作流不依赖**）
  - `EMBEDDING_MODEL_PATH`（默认 `models/bge-small-zh-v1.5`）
- 本地 Embedding 模型：运行 `python scripts/download_embedding_model.py` 下载到 `models/`（运行时**不联网**）。

---

## 13. 安装与配置

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -e .

# 下载本地 Embedding 模型（一次性）
python scripts/download_embedding_model.py
```

在项目根目录创建 `.env`：

```bash
DEEPSEEK_API_KEY=你的_DeepSeek_Key
SERPER_API_KEY=           # 可选
EMBEDDING_MODEL_PATH=models/bge-small-zh-v1.5
```

---

## 14. 运行

### 1) 启动后端 API

```bash
uvicorn server.main:app --port 8000
```

首次调用会自动懒加载：本地 Embedding → 索引 `data/documents` + `.rag_workspace/uploads` → 构建 LangGraph 图。

### 2) 启动 Streamlit 前端

```bash
streamlit run client/app.py --server.port 8501
```

打开 http://localhost:8501 。左侧为知识库（上传文件 / 文档类型 / 已索引文档），右侧为对话（答案 / 调用路径 / Citation / Agent 执行过程），底部为反馈按钮。

---

## 15. API 参考

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 健康检查 |
| `POST` | `/documents/upload` | 上传文档（pdf/md/txt），增量索引 |
| `GET` | `/documents` | 已索引文档列表 |
| `POST` | `/chat` | 对话（返回答案/意图/引用/路径/延迟等） |
| `POST` | `/feedback` | 提交反馈（accepted / edited_and_accepted / rejected） |
| `GET` | `/metrics/summary` | 指标汇总 |

`POST /chat` 请求/响应示例：

```jsonc
// 请求
{ "session_id": "abc", "message": "验证码连续输错5次会发生什么？" }
// 响应（节选）
{
  "task_id": "…", "answer": "…", "intent": "knowledge_query",
  "citations": [{"source": "01_login_prd.md", "section": "连续失败策略", "chunk_id": "…"}],
  "path": ["classify_intent", "retrieve_knowledge", "generate_final_answer", "prepare_citations"],
  "tools_used": ["search_knowledge"], "latency_ms": 3695,
  "requires_confirmation": false, "success": true
}
```

---

## 16. 测试

```bash
python -m pytest tests/ -v
```

32 条测试覆盖：文档摄入、知识检索、Issue 检索、意图路由、测试用例 Schema、反馈、指标、API 集成。**最新一次全量运行：32 passed。**

---

## 17. 评测（Evaluation）

离线评测脚本 `evaluation/run_product_eval.py` 直接运行编译后的工作流（不依赖服务器），对 `evaluation/datasets/dev_agent_eval.json` 的 **30 条数据**（10 知识 + 10 Issue + 10 测试用例）逐条运行并统计：

```bash
python evaluation/run_product_eval.py
```

**真实评测结果**（`evaluation/results/latest.json`，非人工编造）：

| 指标 | 数值 |
| --- | --- |
| Intent Accuracy（意图准确率） | **0.9667**（29/30） |
| Source Hit Rate（知识来源命中率） | **1.0**（10/10） |
| Issue Hit Rate（Issue 命中率） | **0.9**（9/10） |
| Test Case Schema Pass Rate | **1.0**（10/10） |
| Task Completion Rate | **1.0** |
| Mean Latency | **5233.9 ms** |

> 唯一未命中的是 `i008`（「Redis 验证码 key 不设 TTL 会怎样？」）：该问句以「会怎样」发问，意图路由将其判为知识问答而非历史 Issue 查询——这是一个真实的边界情形，已如实保留在结果中，未做任何数据修补。

---

## 18. 已知问题与局限

1. **意图边界歧义**：以「会怎样 / 为什么」发问的历史问题可能被路由为知识问答（见上 `i008`）。
2. **检索质量依赖 Embedding 与阈值**：`MIN_SIMILARITY=0.45` 为当前标定值，换文档集后需重标定。
3. **Issue 检索为关键词法**：无向量索引，长尾/同义表达召回有限。
4. **Windows 文件锁**：增量上传采用 `add_documents` 原地追加，避免对打开中的 Chroma 目录做 `rmtree`。
5. **SERPER 状态**：默认工作流不使用 web 搜索；`SERPER_API_KEY` 仅为上游旧版 `tools.py` 的可选依赖。
6. **演示数据为合成**：知识文档与 Issue 均为演示用虚构内容，不代表真实生产数据。

---

## 19. 安全注意事项

- `.env` 与 `DEEPSEEK_API_KEY` **从未提交**；`.env.example` 仅保留空占位。
- Embedding 模型权重在 `models/`（已 gitignore），**不提交 Git**。
- 前端「Agent 执行过程」只展示确定性信息（意图 / 工具 / 检索分块 / 延迟），**不展示链式思考（CoT）或隐式推理**。
- 后端异常**不会把 Python stack trace 原样返回前端**；`run_workflow` 统一捕获并返回友好错误。

---

## 20. 技术栈

FastAPI · LangGraph · LangChain · Chroma · HuggingFace `bge-small-zh-v1.5` · DeepSeek `deepseek-chat` · Streamlit · SQLite · Pydantic · pytest

---


