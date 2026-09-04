---
lifecycle: entry
owner: governance-team
last_updated: 2026-08-18
type: ssot
last_updated: 2026-09-03
---
# AGENTS.md — docs

## Scope

`docs/` 维护治理文档、说明书和过程证据说明，属于长期可追溯资产。新增或修改文档前需保持与 SSOT 链接一致。

## 约束

1. 根仓规则优先，所有文档改动应避免直接硬编码当前状态值（健康数值、计数、端口等）。
2. 文件删除/重命名前确认是否有下游索引或引用（如 `ARCHITECTURE.md`、`docs/INDEX-*.md`）。
3. 过程文档、扫描报告需要说明生成来源命令和时间戳。

## 文档约定

- 使用相对链接，优先指向 SSOT/约定文件，不重复托管权威事实。
- 工具扫描报告应附命令、范围和生成时间。

## 常用命令

- `make doc-ssot-lint`
- `make ssot-guardian`
- `make gac-local-gate`

