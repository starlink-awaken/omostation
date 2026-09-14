---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T8-14
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T8-14 结构化分级日志、Metrics 环形缓冲与 Prometheus 导出设计

## 1. 目标

为 cockpit 引入轻量可观测底座：`MetricsCollector` 环形缓冲区（有界、无锁
竞争路径最小化）、Prometheus exposition 格式导出、`cockpit telemetry`
查询/导出命令，以及错误/警告自动进入诊断环形缓冲区的结构化日志通道。

## 2. In scope

1. `projects/cockpit/src/cockpit/telemetry.py`（新文件）：
   - `MetricsCollector`：counter/gauge/histogram 三类指标，每类环形缓冲
     （默认 2048 点），线程安全（`threading.Lock`，单写多读）。
   - Prometheus 文本 exposition（`# HELP/# TYPE/<metric>{labels} value`）。
   - 诊断环形缓冲区：ERROR/WARNING 级日志事件自动入环（含时间戳/事件名/
     上下文标签），容量上限后淘汰最旧。
   - 结构化日志：JSON 行格式 + 按大小轮转（默认 5MB × 3 份）。
2. `cockpit telemetry` 命令（在 `commands/` 层以最小接线路由到 telemetry.py）：
   `cockpit telemetry --json`（快照）、`cockpit telemetry --export`（Prometheus
   文本）、`cockpit telemetry --diagnostics`（诊断环）。
3. 单测 `projects/cockpit/tests/test_telemetry.py`：指标登记/快照/导出格式/
   环形淘汰/轮转/诊断捕获。

## 3. Explicitly out of scope

- 不引入 Prometheus server / Grafana / 新守护进程；只做文本导出端点面。
- 不新增第二指标体系；不动 omo/agora 现有 telemetry。
- 不把指标接入个人价值（value_indicator_policy=false）。

## 4. 验收（对齐 ledger done_when）

1. `cockpit telemetry` 支持指标查询与 Prometheus 导出。
2. 错误与警告自动进入诊断环形缓冲区（含淘汰语义）。
3. `uv run --project projects/cockpit pytest projects/cockpit/tests/test_telemetry.py`
   exit 0。
