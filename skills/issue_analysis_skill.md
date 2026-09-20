# Issue Analysis Skill（历史问题诊断）

| 项 | 内容 |
| --- | --- |
| Skill 名称 | Issue Analysis Skill（历史问题诊断） |
| 目标 | 帮助研发快速定位历史 Bug / 故障，复用已有解决方案 |
| 输入 | 历史问题 / 故障类提问，如「验证码正确但登录失败怎么办？」 |
| 调用工具 | `search_issue`（`server/issues/issue_store.py`，关键词加权打分检索历史 Issue） |
| 输出 | 问题原因 + 解决方案 + 来源（真实 Issue 记录，如 `ISSUE-001`） |
| 失败处理 | 无匹配 Issue（`results` 为空）时返回固定提示「未找到匹配的历史 Issue。」，不编造案例 |
| 对应意图 | `issue_query`（`server/agent/router.py`） |

## 调用链路

```
用户问题 → Router 判为 issue_query
        → search_issue 关键词加权检索历史 Issue（title / symptom / root_cause 等字段）
        → LLM 依据真实 Issue 记录作答（根因 + 解决方案）
```
