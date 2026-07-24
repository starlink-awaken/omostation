---
title: STRAT-P81 Stage 0 closeout (review-hardened · v2)
date: 2026-07-24
type: audit
stage: S0
strat: STRAT-P81
workorder: .omo/plans/strat-p81-stage0-handoff.md
pr: null
supersedes: 2026-07-24-p81-stage0-closeout.md
---

# STRAT-P81 Stage 0 closeout (v2 · review-hardened)

## 0. TL;DR

| Stage | 状态 | 备注 |
|-------|------|------|
| **S0** | **OPEN (work complete)** | 6 项验收齐全 (#1/#3 留 human) |
| **S1** | **LOCKED** | 需 M1 验收 + 物理 ≥4 |
| **S2/S3** | **LOCKED** | 需 S1 达标 |

## 1. S0 验收清单 (Gate table)

| # | 交付 | 状态 | Evidence |
|---|------|------|----------|
| S0.1 | M1 决策收件箱 | ✅ | `needs-human-p81-m1-acceptance.yaml` + ADR-0228 |
| S0.2 | P80 4 残留清偿 | ✅ | `2026-07-24-p81-s0-phase45-residuals.md` 7/7 GREEN |
| S0.3 | 物理探测 | ⚠️ fail-closed | 1/4, `2026-07-24-p81-s0-physical-probe-failclosed.md` |
| S0.4 | bos_stdio evidence | ✅ | `BOS-MIGRATION-CANDIDATE-MAP-2026-07-24.md` (89/19/2 分组) |
| S0.5 | 决策单总览 | ✅ | `STRAT-P81-MASTER-DECISION-INBOX-2026-07-24.md` |
| S0.6 | BET-c87a 收尾备 | ✅ | `BET-C87A-CLOSEOUT-PREP-2026-07-24.md` |

## 2. 关键数字更正

| 项 | audit 旧值 | SSOT 实时 | 备注 |
|----|-----------|-----------|------|
| stdio-ish ratio | 0.692 (117/169) | **0.6391 (108/169)** | 已 < 0.65 目标 |
| HTTP 服务数 | 24→5 | 24→**1** | 仅 `bos://memory/kos/rest-api` |
| KOS REST 测覆 | 未审 | 2/11 = **18%** | 9 盲区 |

## 3. 红线守门

- ✅ 物理无手填(G-DEL.1/3 仍 fail-closed)
- ✅ bos_stdio 无 transport label 剧场化
- ✅ task 归档走 tracked `.omo/tasks/archived/`,不走 gitignore
- ✅ 无 S1 自宣解锁
- ✅ 无 S3 涌现无 kill-switch 启动

## 4. 未拍板项 (人类拍板汇总)

| # | 卡片 | 选项 |
|---|------|------|
| 1 | `needs-human-p80-physical-hosts` | A/B/C (复活 / Tailscale / 云) |
| 2 | `needs-human-p81-m1-acceptance` | A/B/C (通过 / 拒绝 / 延期) |
| 3 | `needs-human-batch2-physical-recovery-checklist` | 触发待 #1 |
| 4 | `needs-human-p80-phase45-bos-stdio` | A/B/C (internal / mcp_proxy / 修订口径) |
| 5 | `needs-human-batch3-proposal` | A/B/C (物理 / 角色 / 收尾) |
| 6 | `needs-human-batch2-role-expansion-proposal` | A/B (装 / 不装) |

## 5. S0 → S1 切换前置

### 5.1 形式门禁 (必须全 ✅)

| Gate | 现状 | 责任人 |
|------|------|--------|
| 物理 ≥4 (`reachable_physical_hosts`) | 1/4 ❌ | human |
| M1 验收 (3 门禁) | 待审 | human |
| health_score ≥ 95 | 98 ✅ | agent |
| GAC 异常分 ≥ 90 | 92 ✅ | agent |
| 决策单 6 卡 | 全 candidate | human |

### 5.2 S1 启动剧本 (4 步)

1. 物理恢复 → 重跑 `python3 bin/delivery/measure_physical.py --auto-default-lan --start`
2. `reachable_physical_hosts ≥ 4` → G-DEL.3 measure (物理)
3. G-DEL.1 4 机 schedule success > 99%
4. 写 M1 acceptance ADR + 翻 brief §1 S1 = OPEN

### 5.3 风险预案

| 风险 | 缓解 |
|------|------|
| 单机回归 | Tailscale 化 + 不休眠基线 |
| 假绿回潮 | fail-closed + phase-gate-check CI |
| 战线过长 | Stage 串行,纵贯线 2 条 |

## 6. 已被剧场化盯上的黑名单

(`2026-07-24-p81-s0-phase45-residuals.md` + `2026-07-24-p81-stage0-closeout.md` 记录)

- ❌ 改 `transport: mcp_proxy` 保留 `command[]` 无 `mcp_tool` (rejected)
- ❌ 改 gitignore 隐藏 archived (reverted)
- ❌ 假装物理机在线 (rejected)
- ❌ 自宣物理 meets_gate (rejected)
- ❌ 自宣 G-DEL.2b 官方通过 (terminal: official_announce=false)

## 7. 评审 (同等日 review)

与 batch1 closeout 评审一致,执行乐观/悲观双向查证。

| 评审项 | 状态 | 备注 |
|--------|------|------|
| workorder 闭环 | ✅ | `strat-p81-stage0-handoff.md` 4 步骤 OK |
| PR 状态 | ⏳ | 未生成,Stage 0 收尾后启 #484 |
| 任务归档 | ✅ | tracked `.omo/tasks/archived/`,active 26 |
| 文档 SSOT | ✅ | INDEX 4 行新增 |
| 健康分 | ✅ | 98 持平 |

## 8. 接下来(N+1)

### 8.1 拍板后立即可启

- **#4 拍板 A 选项** → 启动 `bos_stdio` 真实迁移工程(worktree + ADR)
- **#4 拍板 B 选项** → mcp_proxy + ProxyManager dispatch 验证工程
- **#7 收尾** → KOS REST API 9 测覆补全

### 8.2 拍板前 Agent 自持

- 维持 health ≥ 95
- 维持 P74 `warn_count=0`
- 不再写新工程代码
- 等人类拍板

## 9. 引用

- STRAT-P81: `.omo/_knowledge/decisions/STRAT-P81-strategic-roadmap.md`
- 决策单: `.omo/_knowledge/decisions/STRAT-P81-MASTER-DECISION-INBOX-2026-07-24.md`
- bos_stdio 候选: `.omo/_knowledge/decisions/BOS-MIGRATION-CANDIDATE-MAP-2026-07-24.md`
- BET-c87a 收尾: `.omo/_knowledge/decisions/BET-C87A-CLOSEOUT-PREP-2026-07-24.md`
- 物理探测: `.omo/_knowledge/audits/2026-07-24-p81-s0-physical-probe-failclosed.md`
- 残留重 verify: `.omo/_knowledge/audits/2026-07-24-p81-s0-phase45-residuals.md`
- Stage0 handoff: `.omo/plans/strat-p81-stage0-handoff.md`
- ADR-0228 M1 提前验收: `.omo/_knowledge/decisions/0228-m1-acceptance-physical-deferred-reorder.md`
- ADR-0232 G-DEL.2b 官方通过: `.omo/_knowledge/decisions/0232-g-del-2b-official-pass.md`
