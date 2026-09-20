# Knowledge Search Skill（知识问答）

| 项 | 内容 |
| --- | --- |
| Skill 名称 | Knowledge Search Skill（知识问答） |
| 目标 | 帮助研发从 PRD / 技术设计 / 测试资料中检索**有依据**的答案 |
| 输入 | 研发知识类问题，如「验证码连续输错 5 次会发生什么？」 |
| 调用工具 | `search_knowledge`（`server/rag/knowledge.py`，Chroma 向量检索 + `document_type` 过滤） |
| 输出 | 带引用的答案，用 `[1][2]` 标注真实来源（`source` / `section`） |
| 失败处理 | 最高相似度低于阈值（`MIN_SIMILARITY = 0.45`）时判为证据不足，返回固定提示「当前知识库未检索到足够依据。」，不强行编造 |
| 对应意图 | `knowledge_query`（`server/agent/router.py`） |

## 调用链路

```
用户问题 → Router 判为 knowledge_query
        → search_knowledge 检索知识库（top_k + 相似度阈值）
        → prepare_citations 从检索结果元数据构建引用
        → LLM 仅依据检索片段作答 + [1][2] 标注
```
