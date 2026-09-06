---
schema_version: specification/v1
spec_version: "1.0.0"
title: "架构健康度量化 — 6 维度周报"
bet_id: BET-Y1Q4-T6-18
created: "2026-09-05"
status: accepted
---

# 架构健康度量化 — 6 维度周报

## 目标

定义场景/架构/进化/运维/防腐/感知 6 维度量化指标，每周自动生成报告。

## 6 维度定义

| # | 维度 | 英文 | 采集源 | 指标 |
|---|------|------|--------|------|
| 1 | 场景成熟度 | scene_maturity | scene-card lifecycle YAML | draft/shadow/assisted/supervised/routine 分布 |
| 2 | 架构合规 | arch_compliance | gac-local-gate results | pass/fail/waiver 比例 |
| 3 | 进化活跃度 | evolution_active | bet-ledger candidate→done 周期 | 本周关闭 bet 数、平均周期 |
| 4 | 运维韧性 | ops_resilience | submodule 指针漂移检测 | 漂移数、最老漂移天数 |
| 5 | 防腐健康 | anti_decay | doc-ssot-lint / governance checks | 违规数、连续零违规天数 |
| 6 | 感知覆盖 | percept_coverage | .agents/skills/INDEX.md + agent-workflows | skills 数 / workflows 数 / 未注册率 |

## 交付物

1. `docs/plans/architecture-health-dimensions.md` — 6 维度定义文档
2. `bin/arch-health-meter.py` — 数据采集脚本，输出 JSON
3. `docs/reports/architecture-health-weekly.md` — 周报模板（由 cron 或手动触发生成）

## 验收标准

```bash
test -f docs/reports/architecture-health-weekly.md  # 周报存在
python bin/arch-health-meter.py --json               # 输出合法 JSON 含 6 维度
```

## 非目标

- 不引入外部 SaaS 监控
- 不做实时告警（仅周报）
- 不改现有治理流程，只做读取采集
