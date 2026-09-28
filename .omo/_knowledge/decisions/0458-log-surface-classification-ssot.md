---
schema: md/v1
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-28
type: ssot
id: ADR-0458
related: ADR-A, ADR-0457, ADR-0249
tags: [log-rotation, ssot, append-only, state-vs-log, evidence]
---

# ADR-0458 — 日志面分类 SSOT：轮转资格登记驱动，不由文件名与人工名单决定

- **Status**: ACCEPTED（2026-09-28 principal 批准立项与 shadow 阶段；warning/fail 转段须另走一次确认）
- **Date**: 2026-09-28
- **Related**: ADR-A（调度编译器）、ADR-0457（launchd 平面漂移门，同族的"声明覆盖面≠实际覆盖面"）、
  ADR-0249（治理预算）、BET-Y2Q4-T16-02

## 背景与问题

`bin/ssot/log-rotate.py` 判定轮转资格靠**文件名 pattern + 硬编码 `SKIP_NAMES`**，仓内无 SSOT。
2026-09-28 修复 `resident-orchestrator` 日志目录漏扫时该缺口直接暴露
（同期修复见 BET-Y2Q4-T16-01 前的 commit `8f106f3bd`）：

- `LOG_PATHS` 声明了 `.omo/_delivery`，但该目录直属 `.log` 为 0，10 个日志全在
  `resident-orchestrator/` 子目录；非递归 `base.glob` 扫不到，
  `daemon.log` 18.75MB（超 5MB 阈值 3.7 倍）自 2026-09-15 起从不轮转，
  而 `--dry-run` 报 "0 over 5242880 bytes" —— **报告可信地说了假话**
- 同一目录下的 `receipts.jsonl` 是追加式回执账本，轮转即 copytruncate 即清零
- 唯一的防护手段是**再往 `SKIP_NAMES` 手写一个文件名**

### 关键：漏判代价是静默的

`--daily` 语义为「跨天即轮转，不看阈值」（`log-rotate.py:101-108`），crontab 每天 03:00 执行。
把追加式账本误纳入扫描范围**不是潜在风险而是即时风险** —— 次日 03:00 清零，
无报错、无告警，只是文件变空。

四个已确认处于该风险面、当前靠"目录尚未被加进 `LOG_PATHS`"侥幸未暴露的账本：

| 路径 | 体量 | 性质 |
|---|---:|---|
| `.omo/_delivery/agent-workflows/events.jsonl` | 468KB | workflow 事件账本 |
| `.omo/_delivery/resident-orchestrator/receipts.jsonl` | 674KB | 回执账本 |
| `.omo/_delivery/ingress/value-evidence.jsonl` | 89KB | **BET 价值证据** |
| `.omo/_delivery/observability/events.jsonl` | 21KB | 可观测事件 |

若当初采用 `base.glob` → `base.rglob` 的"通用"修法，这四个会在次日全部被清零，
并额外扫到 `/tmp` 下 101 个并发 agent 的 worktree / scratchpad / test-shard 文件。
**一个看似更彻底的修复，会同时销毁证据链与他人工作区。**

## 决策

建立**日志面分类 SSOT**，轮转资格由登记驱动，不再由文件名与人工名单决定。

三类互斥词表：

| 类别 | 含义 | 轮转资格 |
|---|---|---|
| `log` | 可丢弃的运行日志 | 可轮转 |
| `state` | 追加式状态 / 证据账本 | **禁止**轮转 |
| `projection` | 生成器可重建的运行时投影 | 默认不轮转 |

消费者 `log-rotate.py` 须：

1. 读 `.omo/_truth/registry/log-surfaces.yaml`（`schema: log-surfaces/v1`）
2. `class: state` 的路径硬性排除，且**排除须在 `--dry-run` 报告中可见**，不得静默
3. 登记为 `class: log` 但所在目录不在 `LOG_PATHS` 的，作为**未覆盖告警**报出
4. 保留 `LOG_PATHS` / `LOG_PATTERNS` 作兜底扫描面，但注册表中的 `state` 优先且不可覆盖

阶段门与 ADR-0457 同为 shadow → warning → fail：新门禁直接 fail 会因存量未分类锁死主干
（E5 事故：ADR-0380 上线即检出 18 个 rewind）。

## 影响面与不做的事

- **不改**：5MB 阈值、`--daily` 语义、`/tmp` 的扫描范围（仍非递归）
- **不做**：通用保留期策略引擎（不引入 TTL / 分层存储）；`retention` 字段先只登记不执行
- **不做**：决定各面保留时长
- **不改**：`runtime-projections.yaml`（已覆盖 `metrics-store` / `anomaly-events`，
  但不覆盖 `.omo/_delivery` 下的账本 —— 这正是缺口所在）

## 验收

见 spec `docs/superpowers/specs/2026-09-28-t16-log-surface-classification-ssot.md` §验收：
注册表可被消费、四个账本在任何轮转模式下均不出现、`--dry-run` 新增两段计数、
四个此前漏扫的日志目录登记为 `class: log`、候选数可由注册表复算。
