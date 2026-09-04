---
type: ephemeral
created: 2026-09-03
---

# Documents Runtime Source/Owner Parity Inventory — Task 7B (work-weijian)

> Date: 2026-08-27
> Scope: `documents-content-plane-migrations.yaml` family `work-runtime`, restricted to the
> `@工作文档/卫健委/_runtime/**` and `@工作文档/卫健委/_control/**` sources (13 files).
> Method: static inspection of the live `/Users/xiamingxing/Documents` source bytes,
> source-call references, and installed crontab. No legacy Documents command was executed
> for this inventory beyond read-only hash/grep operations.

## Boundary and conclusion

This is an inventory, not a cutover: no source command is bridged, no schedule or client
configuration changes, no old source is retired, and no Documents file is changed. This
extends the same method used for Task 7A (`public-runtime`, `cockpit-runtime`,
2026-08-12) to the previously fully-`pending` `work-runtime` family's 卫健委 sources.

`work-runtime` may therefore advance from `pending` to `in_progress` for this subset.
It does not have per-source owner-command parity, consumer cutover evidence, a
compatibility bridge, or terminal-state evidence. The `@工作文档/*` sources for other
domains (国转中心, 利用科 etc.) covered by the same family glob are **not** inspected
here and remain `pending`.

## Evidence method

- SHA-256 values below were read from the live source bytes on 2026-08-27.
- "Active" means a current `crontab -l` entry (uncommented) was found; commented-out
  lines are labelled as historical/retired.
- No full audit was run; this inventory records no live health totals.

## 卫健委 runtime/control sources

| Source and SHA-256 | Purpose (from docstring) | Known consumer | Assessment |
|---|---|---|---|
| `_runtime/daily-health-run.py`
`a1b222a507aa82d805f726b5c655259f0cad9466c0f1ae09781ef2dcaeac7c10` | 卫健委 KEMS 每日健康巡检编排器 — 显式替代原 crontab 两条链式命令 | Installed cron daily 08:00 | **Active, consolidating.** Replaced two now-deleted scripts (`check-supervision-quarter.py`, `check-report-deadline.py` — both confirmed absent from disk; their crontab lines are commented out, consistent with a completed consolidation, not an accidental loss). |
| `_control/controller.py`
`ae39c2f205fc64ba08136fb30b007d29619dcb626f65fc0fbfca9e4a27da78b6` | 自动控制回路 — 扫描 signals → 匹配 CR 规则 → 输出动作指令 | Installed cron weekly Mon 09:00 | **Active.** No Workspace owner command inspected against this specific CR-rule-matching contract; no parity claim made. |
| `_control/predictor.py`
`1238089a2d5728e20c88ef9ec28b422bf3b024a629b08d2678fb546711228e20` | 情报预测层 — 从历史时间线提炼周期规律，预测下月/下季度 | Installed cron monthly (1st, 08:30) | **Active.** Same caveat as controller.py. |
| `_runtime/cron/ocr-incremental.sh` | (not read in this pass) | Installed cron 1st/16th monthly 10:00 | **Active**, not inspected beyond confirming the crontab entry is live. |
| `_runtime/check-proj-stage.py`
`35238bc1fccd9eb69f6a4e568add6124552e4c07120a3a3a752da3b71bf92c84` | 信息化项目 S0-S8 骨架完整性巡检 | None found (no cron/launchd) | On-demand tool, not scheduled. |
| `_runtime/check-proj-materials.py`
`c23500cb59397972150294239fad80d2036acb953c33071907c8ca1090c54b4a` | 信息化项目 S1 申报材料 13 项必要资料完备性核对 | None found | On-demand tool, not scheduled. |
| `_runtime/check-doc-governance.py`
`a2045b2edc853d18411e00c53c26c506bde010e398bac58fe4b4a9dade696945` | 文档与目录治理巡检 | None found | On-demand tool, not scheduled. |
| `_runtime/check-kems-health.py`
`ac1f122a99fe23cc33ad06c89b101192f7dd763f8fa738f625ffb70c3af10ad1` | KEMS知识库健康度巡检 — 老化知识/滞留文件/未归档文件/信号数量 | None found | On-demand tool, not scheduled. |
| `_runtime/relationship-reason.py`
`fdcf655fa2c4deba286c3deb197fcbbcd0f715dfc38a2b7e870b6fcff87b5604` | KEMS 关联推理引擎 — 实体→决策路径推导 | None found (manual CLI use: `python3 relationship-reason.py <实体>`) | On-demand tool, not scheduled. |
| `_runtime/gen-dashboard.py`
`e765d4a8c21f138bbdc491a307c44f0a7da5126eddeb3b10d0d050ea17d7f66f` | 本地自包含 Dashboard 生成器 — 自述"替代已失效的 @公共/_runtime/kems-v2/gen-dashboard.py（真源缺失）" | None found | On-demand tool. Docstring itself documents a prior broken cross-domain dependency that was already locally patched around. |
| `_runtime/_deprecated_gen-dashboard-local.py` | (filename self-declares deprecated) | None | Already retired in place; no action needed, no registration warranted. |
| `_runtime/commit-groups.sh` | (not read — shell script, no docstring header) | None found | On-demand tool, not scheduled. |
| `_runtime/host-deploy.sh` | (not read — shell script, no docstring header) | None found | On-demand tool, not scheduled. |
| `_runtime/signals-archive.py`
`9be217e3d51d777c980b49be14a57475373e581d64ca41b06287d680548efd91` | signals 归档 — 把噪音/已闭环信号归档到 _archive | None found (not scheduled) | **Bug found, zero current impact**: hardcodes `ROOT = "/sessions/compassionate-keen-davinci/mnt/卫健委"`, a cloud-sandbox path that does not exist on this machine. Confirmed via `ls` (No such file or directory). Because nothing schedules this script, the bug has not caused any observed failure — but a manual invocation today would fail immediately. Flagged for a future fix (replace hardcoded path with `os.path.dirname(...)`-relative resolution, matching the pattern already used in `relationship-reason.py`), not fixed in this pass since it falls outside "read-only inventory."

## Required next evidence before any further state change

Same three requirements as Task 7A: (1) per-active-source Workspace owner command with
interface/write/exit-code parity tests, (2) a compatibility bridge + telemetry for every
live cron consumer before any cutover, (3) keep source/consumer/rollback/confirmation-gate
declarations intact until owner implementation and consumer evidence are accepted.

Of the 13 files in scope, only 4 are cron-active (daily-health-run.py, controller.py,
predictor.py, ocr-incremental.sh) and therefore load-bearing for scheduled operation. The
other 9 are on-demand CLI tools with no scheduled consumer — their migration urgency is
lower and does not block any daily/weekly automation.
