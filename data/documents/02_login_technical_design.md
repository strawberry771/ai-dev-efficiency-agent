# 登录系统 — 技术设计

> **Demo / synthetic development document（演示用合成文档）。** 本文为 AI 研发效能
> Agent 演示所虚构，不描述任何真实系统。

## 总体架构

后端为 FastAPI 服务，认证流程由 `auth` 模块编排，依赖 MySQL（用户数据）与
Redis（短时状态）。

## API

- `POST /auth/password` — 密码登录
- `POST /auth/sms/send` — 发送短信验证码
- `POST /auth/sms/login` — 验证码登录
- `POST /auth/phone/change` — 修改手机号

## 错误码

- `1001` 密码错误
- `1002` 验证码错误
- `1003` 验证码过期
- `1004` 账号已锁定
- `1005` 请求过于频繁

## Redis 验证码

验证码存储在 Redis 中：key 为 `sms:code:{phone}`，value 为 6 位验证码与重试计数，
TTL 为 `300` 秒（5 分钟）。使用 Redis 是因为验证码短时有效、读多写少，且 Redis 支持
原子 TTL 过期。

## MySQL 用户数据

`user` 表存储账号、密码哈希、手机号、账号状态等字段。密码只保存加盐哈希。

## Rate Limit

基于 Redis 限流：同一手机号发送验证码 60 秒内最多一次；登录失败计数使用
`login:fail:{account}`，TTL 15 分钟，达到 5 次触发锁定。

## 登录日志

登录尝试写入 MySQL 的 `login_log` 表，字段包含账号、时间、IP、结果、失败原因，用于
满足 PRD 的审计要求。
