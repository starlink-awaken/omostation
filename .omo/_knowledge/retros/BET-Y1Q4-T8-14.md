---
schema: bet-retro/v1
bet_id: BET-Y1Q4-T8-14
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-05
type: ephemeral
---

# BET-Y1Q4-T8-14 retro — 结构化日志/诊断环/Prometheus 底座

## What changed

- 前序交付（已在 main，docstring 标注本 bet）：`telemetry/metrics.py`
  MetricsCollector（counter/histogram/持久化 + Prometheus exposition）、
  `commands/telemetry.py` status/export/reset、4 个单测。
- 本轮收尾增量：**DiagnosticsRing**（512 容量环形缓冲、线程安全、
  ERROR/WARNING 自动捕获 via `DiagnosticsLoggingHandler` 挂 root logger，
  observability 异常永不冒泡）；`cockpit telemetry diagnostics [--limit]`
  CLI（JSON + TTY 表）；status JSON 附 diagnostics 摘要；parser 两处
  choices 扩展。
- 测试 9/9（新增 5：record/snapshot、容量淘汰、clear、handler 自动捕获
  且 INFO 不入环、CLI diagnostics JSON）；ruff clean（顺手修 6 处 UP）。

## Q3 (打假)

- ledger 原写面 `telemetry.py`（单文件假设）与真实包布局不符——claim 被
  WORK_PACKET_SCOPE_MISMATCH 拦两次后修正为 6 面（含 _subcommands.py，
  parser choices 扩展必需）。教训：bet 铸造时写面按"当时的想象"写，
  claim 时才撞现实。
- work packet hash 在 start 钉死：改 ledger 必须重 start（两轮 run 作废
  c4ffae53/615b2f65）。

## Q4 (遗留)

- 诊断环为进程内内存环，未跨进程持久化（daemon 化后可加 storage_path 落盘）。
- 结构化日志轮转（spec §2.4 JSON 行 + 5MB×3）未在本轮实现——现有
  MetricsCollector 已有 JSON 持久化；独立日志文件轮转留 follow-up bet。
