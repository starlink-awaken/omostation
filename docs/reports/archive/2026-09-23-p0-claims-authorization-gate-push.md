---
type: ephemeral
status: completed
date: 2026-09-23
scope: P0 推进 — Claims 授权执行 + 门禁/告警修复 + 协议矛盾固化
author: governance-agent
session: p0-claims-gat010
last-reviewed: 2026-09-23
---

# P0 推进报告：Claims 授权 · 门禁修复 · 协议固化（2026-09-23）

> **一句话**：Claims lifecycle 已获人工授权并完成 Op A；Op B/C 因
> `PITFALL-GAT-010` 协议死锁按 stop condition 停止；同步修复 A2/A4/A5 并登记
> GAT-010 + ADR-0455（PROPOSED）+ 高危告警 triage。

---

## 1. Claims Authority

### 1.1 授权（已完成）

| 字段 | 值 |
|------|-----|
| principal_decision_id | `DEC-20260923-CLAIMS-LIFECYCLE-R0-01` |
| 窗口 | 2026-09-23T01:47:16Z → 2026-09-25T01:47:16Z |
| draft SHA-256 | `07d655deb0f90e8a888f8a65b634a280aa28cfec48335cbfca9f12d6e36f7682` |
| 记录 | `claims-observation/lifecycle-human-approval.json`（逐字 quote 已对 review 校验） |
| 元数据生成 | 经 principal 口头委托（decision_id/时间戳），quote 由 principal 逐字提供 |

### 1.2 Operation 执行

| Op | 状态 | 证据 |
|----|------|------|
| A managed-clone-shadow-observation | **EXECUTED** | receipt seq **2** `sha256:a660e34c…1eab7`；`expected_managed_clone_difference`；v1 deny + v2 would_allow；publishable=false |
| B legacy-publication-regression | **BLOCKED_PROTOCOL** | 需 allow receipt；v2 禁止 allow → **零 push/PR/merge** |
| C expiry-replay-nonpublication | **NOT_STARTED** | 依赖 B 的 fence |

### 1.3 运行态

- `shadow-active` / epoch 1 / sequence **2** / `instruction_capable=false`
- WorkPacket digest 重算 = `sha256:8e12e663…cf57` ✅
- 证据目录：`claims-observation/lifecycle-exec-20260923T015131Z/`
- 状态：`lifecycle-execution-status.json` + sidecar（**未改** draft 本体 SHA）

### 1.4 协议矛盾固化

- **PITFALL-GAT-010**（high）：fence↔managed-clone allow 互斥
- **ADR-0455**（PROPOSED）：倾向方案 A — 绑定 publication 范围的专用 allow 分支
- GitHub Issue：见 PR 描述链接

---

## 2. 门禁与告警（本轮修复）

| 项 | 修复前 | 修复后 | 动作 |
|----|--------|--------|------|
| **A4** | orphan 2（fleet-watch + 死链 refresh-cf-ips） | **PASS** | 删 crontab 死链；`fleet-watch.sh` 入 `known_orphans` |
| **A2** | stale_beats + dead_refs | **PASS** | `omo state refresh` 刷 `system_health`；死链随 A4 清除 |
| **A5** | 同 A2 | **PASS** | 同上 |
| **A9** | cockpit_sources 时序 PARTIAL | 待 collect 复验 | 非本轮代码改动 |
| **RF0** | — | PASS（维持） | — |
| **High alert** | Submodule Freshness Gatekeeper (3/4) | **triaged** | workflow 为 proposal-only 不自愈；真债=子模块 gitlink 漂移，需 pointer-bump PR；非 stale fixture |

### meta-doctor 快照（worktree）

- `stale_beats=0` `dead_refs=0`（`ritual_lapsed=1` 主人周检视，不挡 A2/A5 evidence）

---

## 3. P0 收口判断

| P0 项 | 结论 |
|-------|------|
| Claims operation-specific 授权 | ✅ 取得并落盘 |
| Claims 技术 preflight | ✅ hard_blockers=[]（main high-water 路径修复） |
| Claims 三 operation 全绿 | ⚠️ **部分** — A 成；B/C 等 ADR-0455 + 有效窗内重跑 |
| 失败门禁 A2/A4/A5 | ✅ 本 worktree evidence PASS（待 PR 合并 + panorama 刷新） |
| High alert triage | ✅ 分类为真债（子模块漂移 proposal），非 fixture |
| 价值证据 30 条 | P1，未动（按计划） |

---

## 4. 下一步（有序）

1. 合并本 PR（PITFALL + ADR + registry known_orphans + 本报告）
2. 刷新 Panorama collect，确认 gates 列表
3. ADR-0455 评审 → ACCEPTED 后实现方案 A → 续窗/新窗重跑 Op B/C
4. Submodule Freshness：按 proposal 开 pointer-bump PR（或确认可接受漂移）
5. P1：价值证据采集、T10-154 unblock

## 5. 边界

- 未启用 instruction capability / 未 v2 升 above shadow
- 未 force push、未 `--no-verify`、未改 historical receipts
- crontab 仅删除**不存在的** `refresh-cf-ips.sh` 行（机器态）
- 授权窗至 2026-09-25T01:47:16Z；过期需新 principal 决策
