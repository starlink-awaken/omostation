---
type: ssot
---

# AGENTS.md — knowledge

## Scope

`projects/knowledge` 承载 `gbrain` + `kairon` 知识工程复合体。变更需考虑子项目独立性与跨项目依赖。

## 前置要求

1. 阅读根仓 [`../../AGENTS.md`](../../AGENTS.md) 与 [`../../CLAUDE.md`](../../CLAUDE.md)。
2. 阅读本项目 `README.md`。
3. 检查 `git status --short`（根仓与本项目）。
4. 涉及治理/SSOT 变更按 ADR-0203 走 `agent-workflow`。

## 子项目

- `gbrain` — PostgreSQL + pgvector 权威存储（TypeScript, `bun test`）
- `kairon` — 16 包 monorepo（Python, `make test-diff`）

## 常用命令

```bash
# 顶层
uv run pytest tests/ -v

# gbrain
cd gbrain && bun test

# kairon
cd kairon && make test-diff
```

## 验证

- 文档类变更：`make doc-ssot-lint`（根仓）
- 代码类变更：对应子项目 `bun test` / `make test-diff`
