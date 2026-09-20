# Skill 定义（能力拆解）

> 本目录把「AI 研发效能 Agent」的 Agent 能力拆成三个 **Skill**，每个 Skill 对应代码中
> `server/agent/router.py` 的一个意图（intent）与 `server/agent/core_tools.py` 的一个核心工具，
> 由 **Intent Router** 决定调用哪个 Skill——即「把 Agent 拆成可复用能力，而非一个黑盒」。

## Skill → Intent → Tool 映射

| Skill | 对应意图 | 核心工具 | 定义文档 |
| --- | --- | --- | --- |
| Knowledge Search（知识问答） | `knowledge_query` | `search_knowledge` | [knowledge_search_skill.md](knowledge_search_skill.md) |
| Issue Analysis（历史问题诊断） | `issue_query` | `search_issue` | [issue_analysis_skill.md](issue_analysis_skill.md) |
| Test Case Generation（测试用例生成） | `test_case_generation` | `search_knowledge` → `generate_test_cases` | [testcase_generation_skill.md](testcase_generation_skill.md) |

> 另有 `general_chat`（闲聊）意图，直接由 LLM 回答，不绑定业务工具。

## 设计原则

1. **确定性工具优先**：三个核心工具都是确定性能力，由工作流直接调用（非 LLM 自由 tool-calling），
   返回结构化结果，便于测试与复现。
2. **引用可溯源**：每个 Skill 的输出都携带真实来源（`source` / `section` / Issue 记录），杜绝编造。
3. **失败有兜底**：检索不到依据 / 无匹配 Issue 时如实告知，不强行回答；测试用例无文档依据时
   以 `basis_type=ai_suggestion` 显式标注「AI 建议」。

## 演进方向

将上述 Skill 进一步暴露为 **MCP Tool**（供外部 Agent 通过 Model Context Protocol 调用）是后续演进方向；
当前版本以「意图路由 + 确定性工作流」的方式内置在服务端，未引入 MCP 依赖。
