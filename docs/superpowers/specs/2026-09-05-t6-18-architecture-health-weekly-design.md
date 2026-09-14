---
schema_version: specification/v1
spec_version: 1.0.0
title: T6-18 架构健康度 6 维度量化 + 周报自动化
bet_id: BET-Y1Q4-T6-18
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
---

# T6-18 架构健康度 6 维度量化 + 周报自动化

## 1. 目标

将当前散落在 `.omo/standards/health-metrics-semantics.md` 的 4 指标 (health_score / health_score_raw / health_score_evidence / product-health) + `cockpit audit` 6 维度, 收敛成 6 个稳定的 维度-指标 对, 接入周报 cron, 每周自动生成 `docs/reports/architecture-health-weekly.md` 摘要.

## 2. 6 维度 (5 主 + 1 辅助)

| 维度 | 主指标 | 含义 | 数据源 |
|------|------|------|------|
| **场景** (Scene) | scene_card 总数 + lifecycle 分布 | 场景库规模与升级进度 | `docs/scene-cards/*.yaml` frontmatter |
| **架构** (Architecture) | 5+4+1+1 层级一致性 + DFSQ/SFOP 槽位占用 | 架构骨架健康 | `bin/gac/check-sfop-slots.py` + `check-execution-chain.py` |
| **进化** (Evolution) | 3Y bet done 比例 + 滚动 7d | bet 兑现率 | `docs/plans/3y-bet-ledger.yaml` status + done_at |
| **运维** (Operations) | runtime 在线率 + daemon 心跳 | 服务健康 | `.omo/state/runtime.json` + `bin/observability/*` |
| **防腐** (Anti-Corrosion) | GaC drift 项数 + 治理 SSOT 漂移 | 治理债 | `bin/gac/meta-doctor.py --json` + `bin/ssot/ssot-guardian.py` |
| **感知** (Perception) | agent skill/workflow 覆盖率 + 沉默 workflow | 自动化覆盖率 | `bin/agent-workflow.py compliance` + skill INDEX |

## 3. In scope

1. `bin/arch-health-meter.py` — 跑 6 维度的数据采集, 输出 JSON + 简短 markdown 摘要
2. `docs/reports/architecture-health-weekly.md` — 周报模板 (6 维度表 + 趋势图占位 + action items)
3. `.omo/standards/architecture-health-six-dim.md` — 6 维度定义 (SSOT)
4. `bin/ops/launchd/com.omostation.arch-health-weekly.plist` — launchd snippet (示例, 不自动注册)
5. 周报手动运行方式: `bash bin/ops/architecture-health-weekly.sh` (wrap 上面脚本)

## 4. Out of scope

- 不集成到 cockpit (留作 follow-up)
- 不修改 health_score 现有 4 指标 (只新增 6 维度, 平级关系)
- 不做趋势可视化 (用文字描述)

## 5. 验收

1. `python3 bin/arch-health-meter.py --json` → exit 0, 含 6 维度数值
2. `python3 bin/arch-health-meter.py` → 打印 markdown 表格
3. `test -f docs/reports/architecture-health-weekly.md` → exit 0
4. `.omo/standards/architecture-health-six-dim.md` 含 6 维度定义
5. `make gac-local-gate` → exit 0
