---
schema_version: standard/v1
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-05
type: ssot
bet_id: BET-Y1Q4-T6-18
---

# 架构健康度 6 维度量化标准 (T6-18 SSOT)

> 与 `.omo/standards/health-metrics-semantics.md` (4 个 health_score 指标) 平级, 不替代. 6 维度是周报视角; 4 个 health_score 是单值治理视角.

## 6 维度总览

| 维度 | 主指标 | 取值 | 权威源 | 采集脚本 |
|------|------|:---:|------|------|
| **场景** (Scene) | scene_card 总数 + lifecycle 分布 | count | `docs/scene-cards/*.yaml` frontmatter | `rg -c '^---$' docs/scene-cards/ \| head -1` + 解析 lifecycle 字段 |
| **架构** (Architecture) | SFOP 槽位一致性 (5+4+1+1 唯一性) + DFSQ 层数 | bool/count | `bin/gac/check-sfop-slots.py --json` + `check-execution-chain.py` | 同左 |
| **进化** (Evolution) | 3Y bet done 比例 (含 done_at 在最近 30d) | ratio | `docs/plans/3y-bet-ledger.yaml` 解析 status | `bin/arch-health-meter.py` 内联 |
| **运维** (Operations) | runtime 在线率 (daemon + 5 服务) | ratio | `.omo/state/runtime.json` + `bin/observability/check-runtime.sh` | 简化为 `cockpit status --json` |
| **防腐** (Anti-Corrosion) | GaC drift 项数 + 治理 SSOT 漂移告警 | count | `bin/gac/meta-doctor.py --json` + `bin/ssot/ssot-guardian.py` | 同左 |
| **感知** (Perception) | skill INDEX 注册数 + workflow 沉默数 | count | `.agents/skills/INDEX.md` + `.omo/_truth/registry/agent-workflows/INDEX.md` | 静态解析 |

## 6 维度的相互独立性

6 维度刻意正交, 不合并为单分:
- **场景** 衡量产品覆盖面 (用得多)
- **架构** 衡量骨架稳定 (不变)
- **进化** 衡量兑现率 (事在推进)
- **运维** 衡量服务存活 (7x24)
- **防腐** 衡量治理债 (越少越好)
- **感知** 衡量自动化覆盖 (agent 工具箱)

合并为 1 个分 (如 weighted_score) 是反模式 — 维度是诊断, 不是 KPI.

## 周报节选 (`.docs/reports/architecture-health-weekly.md`)

| 维度 | 当前 | 上周 | 趋势 | 备注 |
|------|------|------|------|------|
| 场景 | 23 cards (5 assisted/8 shadow/10 draft) | 22 (5/7/10) | +1 | 1 升级 |
| 架构 | 4/4 SFOP 槽 OK + 5+4+1+1 一致 | OK | 持平 | — |
| 进化 | 8/325 bet done (2.5%, 30d 内 +3) | 7/322 | +1 | 速率回升 |
| 运维 | 5/7 在线 (71%) | 7/7 | -2 | 2 daemon 离线 |
| 防腐 | 1 drift (retro 指 path 漂移) | 0 | +1 | 本周需修 |
| 感知 | 40 skills + 31 workflows (0 沉默) | 同 | 持平 | — |

## 实现路径

1. `bin/arch-health-meter.py` 跑 6 维度数据采集, 输出 JSON + markdown 摘要
2. `bin/ops/architecture-health-weekly.sh` 包上面 + 写 `docs/reports/architecture-health-weekly.md`
3. launchd snippet 在 `bin/ops/launchd/com.omostation.arch-health-weekly.plist` (示例, 不自动注册)

## 与现有指标的关系

| 现有 (4 health_score) | 6 维度对应 |
|------|------|
| health_score | = 防腐 (low drift) + 感知 (high coverage) 的合成 |
| health_score_raw | = 6 维度的 raw sum (无权重) |
| product-health | = 运维 (runtime 在线率) |
| audit (6 维度) | **本 bet 重新定义 6 维度 = 场景/架构/进化/运维/防腐/感知, 替代 cockpit audit 的 6 维度** (governance/lint/radar/ssot/gitlink/ops 命名不直观) |

## Out of scope (本 bet)

- 不做趋势图 (用文字 + delta 列)
- 不修改 `.omo/standards/health-metrics-semantics.md` 的 4 health_score 指标
- 不集成到 cockpit
- 不自动注册 launchd (脚本提供, 人工装)

---

*T6-18 设计 · 2026-09-05 · 5 主维度 + 1 辅助维度 (防腐), 与 health_score 平级, 不合并*
