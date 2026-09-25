---
schema_version: specification/v1
spec_version: 1.0.0
title: Multi-Registry Alias Resolver — governance-checks / L0-constraints / hook-manifest unification
bet_id: BET-Y2Q4-SH-4
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
---

# BET-Y2Q4-SH-4 — Multi-Registry Alias Resolver

## Context

诊断 `#4310` 发现 `bin/gac/check-rule-wiring-coverage.py` 报告 42/86 (49%) governance-checks 规则在可执行体语料 (bin/**, .githooks/**, .github/workflows/**, hook-manifest.yaml) 零引用。

但该工具自身标注"已知假阳边界：三个注册表 id 词汇互异"。证据：
- `check-l0-constraints.py` 用 `X2-C05` 等命名
- governance-checks.yaml 用 `CR-M0-STAGE-GATE` 等命名
- hook-manifest.yaml 用 hook handler 路径
- bin executors 用实函数名引用

**根因 R3 (部分)**: 同一规则 4 处证据，但**词汇不统一**，工具无法 cross-reference。

## Goal

建立 **registry alias map**，统一 3 套注册表的 id 词汇：
1. governance-checks.yaml (主仓 SSOT, 86 条规则)
2. L0-constraints.yaml (子仓 ecos SSOT, 91 条规则)
3. hook-manifest.yaml (主仓 hook 执行体)

## Non-goals

- **不重写注册表** — alias map 是新增 SSOT，原注册表不变（避免破坏其他工具）
- **不替 owner 决定权威源** — 4 个决策点之一需 owner 拍板哪个注册表是权威，其他向其映射
- **不强行覆盖零引用** — alias 找不到的才是真零引用；alias 找到的视为"已接线"

## Done when

- `bin/gac/registry-alias-map.yaml` 新增：
  - 三套注册表所有规则的等价映射 (双向)
  - 每个映射附 4 处证据引用 (governance-checks.yaml + L0-constraints.yaml + hook-manifest.yaml + bin executors 实际引用)
- `bin/gac/check-rule-wiring-coverage.py` 升级 `--strict` 模式：
  - 使用 alias map 把跨注册表 id 统一
  - 49% 零引用降为 ≤ 15%
  - 真零引用 vs alias 命名区分（输出不同 severity）
- 接入 `make gac-local-gate`：真零引用 ≥ 5% 时 WARN（不阻断 CI）；< 5% 时 PASS
- 单元测试覆盖 ≥ 20 个跨注册表等价 case
- 实证：跑完后 #30 finding 应被识别为"已知 alias，未真零引用"或"真零引用，已分类"

## Verification

```bash
uv run --with pyyaml python bin/gac/check-rule-wiring-coverage.py --strict --json
make gac-local-gate
```

## 关联债务

- 完成后应能 close:
  - `DEBT-20260920-RULE-WIRING-DECL-EXEC-GAP` (medium severity, owner-decision-class)
    - 注：本 BET 完成 alias map 后，**该债的真零引用候选减至 ≤ 15%**，owner 可决策是否关闭
- 关联发现 (from #4310):
  - **#30** 42/86 (49%) governance-checks 规则零引用

## Bootstrap authorization

- workflow: `project-code-change`
- agent: governance-agent
- 优先级: P1
- 依赖: 无（独立）