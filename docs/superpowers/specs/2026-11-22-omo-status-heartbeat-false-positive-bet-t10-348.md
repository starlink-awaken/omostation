---
schema: md/v1
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-22
accepted: "2026-11-22 Principal 批准 — BET 草案全文过目后指令「全面推进落地」（session goal），按 ADR-0203 立新 BET 落地"
bet_id: BET-Y2Q4-T10-348
spec_version: 1.0.0
---

# omo-status 心跳假阳性修复 — healthy_count 真算规范

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-348`

## 目标

消除 swarm 可观测性的健康度假阳性：心跳陈旧（≥600s）的 agent 群不得再显示
"HEALTHY / N/N Agents Active"。修复后 `bin/omo-status` 的 header 徽标如实反映
per-agent 秒龄判定。

## 根因（2026-11-22 实测证据）

- `projects/cockpit/src/cockpit/tui/swarm_collector.py`（collect 路径）：
  `ok_count = data.get("ok_count", agent_count - failed)` 直接采用心跳 tick JSON
  **自报**的 ok_count，`healthy_count=ok_count` 与同一循环内 per-agent 的
  `sec_ago < 600 → healthy/stale` 真判定脱钩。心跳文件是 25 天前写的，自报
  数字永远是当时的 6。
- `projects/cockpit/src/cockpit/tui/swarm_cli.py`（render 路径）：header 徽标
  `healthy_count > 0 → HEALTHY`，单个 agent stale 也亮绿灯。
- 现场证据：2026-11-22 12:10:26Z 快照，6 个 agent SEEN 全部 2178608s（约 25 天），
  显示 "● HEALTHY · 6/6 Agents Active"。

## 修复方案

1. `swarm_collector.py`：`healthy_count` 改为对已构造的 `heartbeats` 列表按
   `status == "healthy"` 真算；心跳文件自报的 `ok_count`/`failed` 不再作为
   健康度来源（保留 total_agents 现状）。
2. `swarm_cli.py`：header 徽标改为 `healthy_count == total_agents 且
   total_agents > 0` 才 HEALTHY，否则 DEGRADED（沿用现有两态渲染）。
3. 新增回归测试 `src/cockpit/tests/test_swarm_heartbeat_staleness.py`：
   陈旧 ts（>600s）→ healthy_count == 0；新鲜 ts（<600s）→ healthy_count == total；
   自报 ok_count 不作为健康度来源。
4. `swarm_app.py`（TUI 状态栏，circuit_breaker 检查发现的同构消费方）：
   `#val-agents` 绿色判定同步收紧为全绿才绿，与 swarm_cli 同判。

## 验证

- `cd projects/cockpit && uv run pytest src/cockpit/tests/ -q` — 新测试通过且
  既有套件无回归。
- `bin/omo-status --no-subprojects` — 陈旧心跳现场 header 显示 DEGRADED。

## 回滚

`git revert` 恢复两文件原判定；无数据迁移、无状态写入、无接口变更，回滚零成本。

## 非目标

- 不改心跳写入方（resident daemon tick JSON 结构）与 600s 判定阈值。
- 不动 agent 表格的 SEEN 列与 per-agent status 显示（现状已正确）。
- 不处理 scene-card 69/70 blocker（治理数据缺 trial 记录，非代码缺陷，另案裁决）。
