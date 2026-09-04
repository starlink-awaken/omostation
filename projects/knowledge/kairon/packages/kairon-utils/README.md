---
title: README
type: doc
---

# kairon-utils

> General-purpose utilities for kairon monorepo

从 `shared-lib` 拆出的独立包（2026-06-06）。

## 模块

| 模块 | 功能 |
|------|------|
| `logging` | 结构化 JSON 日志（JSONFormatter, StructuredLogger） |
| `retry` | 指数退避重试（RetryPolicy, RetryExecutor, CircuitBreaker） |
| `rate_limiter` | Token Bucket 速率限制 |
| `error_classifier` | 错误分类（TRANSIENT/PERMANENT/RATE_LIMIT/...） |
| `error_handler` | 统一错误处理 |
| `errors` | Agent 错误层次结构（AgentToolkitError 及其子类） |
| `concurrent` | 并发执行（ConcurrencyManager, ProgressTracker） |
| `deduplicator` | SHA256 内容去重 |
| `versioning` | 内容版本跟踪 |
| `rollback` | 事务回滚管理 |
| `sqlite_utils` | SQLite 连接管理（managed_connection） |

## 依赖

- 零运行时依赖（仅 stdlib）
- Python >= 3.10

## 测试

```bash
uv run --package kairon-utils pytest tests/ -v
# 167 passed
```
