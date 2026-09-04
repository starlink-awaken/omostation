---
schema_version: specification/v1
spec_version: 1.0.0
title: T10-48 root-resolvable completion evidence repair
bet_id: BET-Y1Q3-T10-52
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---

# T10-48 根仓证据可解析性修复

## Intent

将 T10-48 completion matrix 中依赖 gitlink 内部文件的测试与回放 receipt，
改为根仓跟踪、CI 无需初始化子模块即可解析的证据报告。

## Constraints

- 仅修改 completion evidence 引用与根仓证据文档。
- 不修改 resident ledger 实现、子模块指针、宿主机数据库、进程或 launchd。
- 不修复或重写其他 BET 的历史 completion debt。

## Acceptance

- 根仓 lint 不再为 T10-48 报 `COMPLETION_FILE_REF_MISSING` 或 `BET_DONE_`。
- focused resident-status test 的命令、结果和边界在根仓报告中可审计。
