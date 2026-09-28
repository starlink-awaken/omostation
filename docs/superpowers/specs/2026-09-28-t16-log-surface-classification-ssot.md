---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-28
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: 日志面分类 SSOT — 把「可轮转日志」与「追加式状态」从人工枚举改为登记驱动
bet_id: BET-Y2Q4-T16-02
created: 2026-09-28
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
related: ADR-0458
---

# 日志面分类 SSOT — 把「可轮转日志」与「追加式状态」从人工枚举改为登记驱动

## 背景

`bin/ssot/log-rotate.py` 判定「什么可以轮转」的方式是**文件名 pattern + 硬编码名单**：

- `LOG_PATHS`：手工枚举的目录
- `LOG_PATTERNS = ("*.log", "*.out.log", "*.err.log", "*.jsonl", "*.err")`
- `SKIP_NAMES`：`{"agora-events.json", "agora-proxy-services.json", "agora-audit.db"}`

仓内**没有任何 SSOT 区分「日志」与「追加式状态」**。这一缺口在 2026-09-28 修复
`resident-orchestrator` 日志目录漏扫时直接暴露（见 BET-Y2Q4-T16-01 同期修复）：

- 要让 `daemon.log`（18.75MB）进入轮转，必须给 `LOG_PATHS` 加一行
- 但同一目录下的 `receipts.jsonl` 是**追加式回执账本**，轮转即 copytruncate 即清零
- 只能靠**再往 `SKIP_NAMES` 手写一个文件名**来堵

也就是说：每新增一个日志目录，就要重新做一次「哪些能轮转、哪些不能」的人工判定，
且**漏判的代价是静默丢失证据链**（无报错、无告警，只是文件变空）。

## 事故形态

`--daily` 的语义是「**跨天即轮转，不看阈值**」（`log-rotate.py:101-108`）。
crontab 每天 03:00 执行 `--daily`。因此把一个追加式账本误纳入扫描范围，
**不是潜在风险而是即时风险** —— 次日 03:00 就会被清零。

已确认处于该风险面、当前靠"目录没被加进 LOG_PATHS"侥幸未暴露的账本：

| 路径 | 体量 | 性质 |
|---|---:|---|
| `.omo/_delivery/agent-workflows/events.jsonl` | 468KB | workflow 事件账本 |
| `.omo/_delivery/resident-orchestrator/receipts.jsonl` | 674KB | 回执账本 |
| `.omo/_delivery/ingress/value-evidence.jsonl` | 89KB | **BET 价值证据** |
| `.omo/_delivery/observability/events.jsonl` | 21KB | 可观测事件 |

若当初采用 `base.glob` → `base.rglob` 的"通用"修法，这四个会在次日全部被清零
（另会扫到 `/tmp` 下 101 个并发 agent 的 worktree / scratchpad / test-shard 文件）。

## 决策

建立 **日志面分类 SSOT**，由登记驱动轮转资格，取代人工枚举。

### 分类词表（三类，互斥）

| 类别 | 含义 | 轮转资格 |
|---|---|---|
| `log` | 可丢弃的运行日志 | **可**轮转 |
| `state` | 追加式状态/证据账本 | **禁止**轮转 |
| `projection` | 生成器可重建的运行时投影 | 由投影面自身策略决定，默认不轮转 |

### 登记形态

新增 `.omo/_truth/registry/log-surfaces.yaml`，`schema: log-surfaces/v1`：

```yaml
surfaces:
  - path: .omo/_delivery/resident-orchestrator/daemon.log
    class: log
    owner: governance-team
  - path: .omo/_delivery/ingress/value-evidence.jsonl
    class: state
    owner: governance-team
    retention: indefinite
    note: BET 完成证据, 清零即断证据链
```

### 消费方式

- `log-rotate.py` 启动时读该注册表，构建轮转资格集合
- `class: state` 的路径**硬性排除**，且排除须在报告（`--dry-run`）中可见，
  不允许像现状一样静默
- `class: log` 且所在目录未在 `LOG_PATHS` 的，作为**未覆盖告警**报出
  （即：登记了但扫不到 —— 与 ADR-0457 的 launchd 漂移同族问题）
- 保留 `LOG_PATHS` / `LOG_PATTERNS` 作为**兜底扫描面**，但注册表登记的
  `state` 路径优先且不可覆盖

## 阶段门

同 ADR-0457 的三段式（shadow → warning → fail），理由相同：新门禁直接 fail
会因存量未分类而锁死主干。

| 阶段 | 行为 |
|---|---|
| shadow | 只报告未分类路径与 state 误纳候选，不阻断 |
| warning | 报警 + 清理期限，仍不阻断 |
| fail | 未分类路径阻断轮转 |

## 非目标

- 不做通用保留期策略引擎（不引入 TTL / 分层存储）
- 不改 5MB 阈值与 `--daily` 语义
- 不决定各面的保留时长（`retention` 字段先只登记不执行）
- 不修 `/tmp` 的扫描范围（仍只扫 `LOG_PATHS` 声明的根，非递归）

## 验收

1. 注册表存在且 schema 为 `log-surfaces/v1`，`log-rotate.py` 能消费
2. 上表 4 个追加式账本全部 `class: state`，且在任何轮转模式下均不出现在
   `rotate:` 行
3. `--dry-run` 输出新增「未分类路径」与「被排除的 state 路径」两段计数
4. 4 个此前漏扫的日志目录（`event-ingest` / `perception-inbox` /
   `personal-signals` / `agent-workflows`）在注册表中登记为 `class: log`
5. `--dry-run` 的候选数可由注册表复算

## 顺带登记的既有缺口

- `adr-number-check.py` 的 `ADR_PATTERN = r"^(\d{4})-"` 只认裸编号前缀，
  带 `ADR-` 前缀的 ADR 文件不被统计（已在 ADR-0457 记录，本单不修）
