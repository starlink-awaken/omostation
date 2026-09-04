---
lifecycle: entry
owner: governance-team
last_updated: 2026-08-18
type: ssot
last_updated: 2026-09-03
---
# docs — 文档治理入口

## 作用

`docs/` 承载仓库级文档与治理资产，包括架构、索引、路线图、流程报告与扫描产物。该目录是新成员和 AI 代理的第一入口之一。

## 治理入口

- 根仓治理总控：[`../AGENTS.md`](../AGENTS.md)
- 代码库结构与入口：[`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- 项目元数据：[`../docs/project-registry.yaml`](project-registry.yaml)

## 修改约定

- 变更文档时保持“来源可追溯”：扫描/验证命令应写入产物正文或变更说明。
- 不把临时数据表/临时产物放到 docs 长期存储；如需归档放入 `docs/operations/` 并注明生成命令。

## 常用操作

- `make doc-ssot-lint`
- `make gac-local-gate`
- `make ssot-guardian`

