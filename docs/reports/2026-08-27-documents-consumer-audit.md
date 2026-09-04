---
type: ephemeral
created: 2026-09-03
---

# Documents consumer audit — 2026-08-27

入口：`bin/gac/documents-domain-owner-job.py consumer-audit`；实现位于
`lib/documents_consumer_audit.py`，复用既有 Documents owner job，未新增第二个
`bin/` 顶层入口。

## Result

The read-only audit ran against `/Users/xiamingxing/Documents`, the current user
crontab snapshot, active LaunchAgents, and `Documents/Claude/Scheduled`. It wrote
the machine-readable result to:

`.omo/evidence/20260827T140753Z-project-code-change-9bc6fddc/documents-consumer-audit-live.json`

Status is `violations` (expected before cutover), not a false green:

| Metric | Result |
| --- | ---: |
| active consumers | 191 |
| crontab consumers | 9 |
| active LaunchAgent consumers | 1 |
| scheduled skill consumers | 1 |
| domain-gateway execution references | 180 |
| unmatched active consumers | 12 |

The 9 live crontab consumers are 8 `@公共/_runtime` jobs and 1
`@工作文档/卫健委/_runtime/cron/ocr-incremental.sh`. The active LaunchAgent is
`com.learningevolution.concept-weave.monthly`, invoking
`@学习进化/_control/scripts/run-monthly-weave.sh`.

## Unmatched consumers

The 12 unmatched references are treated as hard blockers for cutover. They
include legacy `驾驶舱/scripts/*`, `@公共/kems-v2/kems-cross-check.py`, and
`@学习进化/2-knowledge/.../ecos-constraint-validator.py`. They need explicit
owner mapping or archival classification before any schedule switch.

## Evidence quality

- Comment-only crontab lines are ignored.
- Disabled and archived LaunchAgent directories are excluded from active scans.
- LaunchAgent scanning inspects only `Program`/`ProgramArguments`, not log paths.
- Consumer IDs and output ordering are deterministic.
- The scanner never executes discovered commands and writes evidence only under
  the supplied Workspace root.

## Decision

`runtime/cache/bridge` cleanup and schedule cutover remain **not ready**. The
next implementation wave should add or verify Workspace owner commands for the
9 live scheduled consumers, resolve the 12 unmatched references, then perform a
separate precise confirmation before changing host schedules.

## 2026-08-28 复核 (BET-Y1Q3-T10-23 claim 轮)

重跑 live scan (真宿主 crontab/LaunchAgents/Scheduled/域网关引用):

- total consumers: **191** (与 08-27 基线一致)
- families: public-runtime 105 · family-dashboard-app 35 · cockpit-runtime 18 ·
  learning-content-archives 9 · root-oneoff-assets 8 · work-runtime 3 · learning-runtime 1
- **unmatched: 12 → 0** — 08-27 列出的 12 个 legacy 引用 (驾驶舱/scripts/*,
  kems-cross-check.py, ecos-constraint-validator.py 等) 已全部获得 family 归类
- forbidden_executors: 0 · workspace_read_owners: 12 · errors: []

结论更新: cutover 的"unmatched 硬阻塞"已解除; 剩余前置 = 为 11 个
live scheduled consumers (9 crontab + 1 LaunchAgent + 1 scheduled skill)
验证 Workspace owner 命令后, 可单独精确确认切换。切换动作本身仍需
Workspace owner (人) 批准 — 本报告仅提供硬证据。
