---
type: ssot
---

# AGENTS.md — .githooks

## Scope

`.githooks` 承载本地 Git hooks 与提交前/提交后行为。该目录直接影响提交门禁。

## Governance

- 修改 hooks 前先评估对主仓提交流程的影响。
- 对于关键钩子，保留回滚路径和验证方法。
- 变更后执行本地钩子相关 smoke（如 make gac-local-gate）以确认行为可控。
- 只改仓库治理相关行为，不加入无关脚本。

