# Test Case Generation Skill（测试用例生成）

| 项 | 内容 |
| --- | --- |
| Skill 名称 | Test Case Generation Skill（测试用例生成） |
| 目标 | 根据需求文档自动生成结构化测试用例，减少重复编写、补足边界覆盖 |
| 输入 | 测试用例生成请求，如「根据登录 PRD 生成测试用例」 |
| 调用工具 | `search_knowledge`（检索需求依据）→ `generate_test_cases`（`server/agent/core_tools.py`，DeepSeek 结构化输出） |
| 输出 | 结构化用例数组，字段含 `id / title / precondition / steps / expected_result / priority / source_basis / basis_type` |
| 失败处理 | 无文档依据时用例以 `basis_type=ai_suggestion` 生成，并在响应中提示「建议人工确认」，不伪装成有文档支持 |
| 对应意图 | `test_case_generation`（`server/agent/router.py`） |

## 依据类型（basis_type）

- `documented`：该用例由检索到的文档依据明确支持，`source_basis` 列出「文件名#章节」来源。
- `ai_suggestion`：该用例为 AI 补充建议，知识依据中无明确要求，`source_basis` 为空。

## 调用链路

```
用户问题 → Router 判为 test_case_generation
        → search_knowledge 检索需求依据
        → generate_test_cases 依据需求 + 检索上下文生成结构化用例
        → 区分 documented / ai_suggestion
```
