---
id: ADR-0388
title: CI 平面减法收官 — workflow retire + 内联 paths 检测盲区修复 + SSOT 生成器
status: ACCEPTED
lifecycle: spec
owner: governance-team
last_updated: 2026-08-07
---

# ADR-0388 Decision: CI 平面减法收官

> 承接 ADR-0386 (CI consolidation)。ADR-0386 做完 scope 收窄 (G16) / pytest 合并 (G17) /
> integration paths (G18) / workflow-health 检测器 (G19) 后, 本轮处理其遗留:
> 冗余 workflow 未删 + 检测器"重跑生成器"但生成器缺失 (P73 声明/执行鸿沟) +
> 三方检测器共享的内联 paths 盲区。

## 一、决策背景 (实测证据)

| 项 | ADR-0386 时 | 本轮实测 (rebase 到最新 main 后) |
|----|------------|--------------------------------|
| workflows | 42 | 41 |
| workflow-health issues | 35 | 35 (0 落地) |
| check-ci-surfaces errors/warns | — | errors=0 warns=47 (全部 trigger-drift) |
| ruff-check vs quality | 计划"删除 ruff-check" | 实际只收窄了 scope, ruff-check 仍冗余 (quality 是超集) |
| no-op 占位 workflow | 未识别 | gbrain-ci/runtime-ci/cockpit-ui-ci 仅 echo "CI 在子仓", 永不自动跑 |

### 三个治理缺口

1. **生成器缺失 (P73 类 B 声明/执行鸿沟)**: check-ci-surfaces.py 报
   `trigger-drift ... (重跑 ci-surfaces 生成器)`, 但生成器从未存在 →
   47 个 warns 无自愈路径, 只能手改 SSOT。
2. **内联 paths 盲区**: 三个检测器 (check-ci-surfaces / workflow-health /
   gen-ci-surfaces-triggers) 共用正则 `^\s+paths:\s*$`, 只识别多行块形式,
   漏掉 `paths: ['a', 'b']` 内联数组 → agora/ecos/kairon 等 6 个子项目 CI
   被误报 unpathed-pr。
3. **冗余 workflow 未删**: ADR-0386 G16 原始决策是"删除 ruff-check.yml
   (quality 已覆盖)", 实际只收窄了 scope → 每 PR 仍多跑 1 个重复 ruff job。

## 二、决策

### 决策 1: 删除 4 个冗余 workflow

| workflow | 理由 |
|----------|------|
| ruff-check.yml | quality.yml ruff-lint 是超集 (src 含 omo/src + 3 个项目), G16 原始决策完整落地 |
| gbrain-ci.yml | no-op 占位 (echo), CI 在 gbrain 子仓 |
| runtime-ci.yml | no-op 占位 (echo), CI 在 runtime 子仓 |
| cockpit-ui-ci.yml | no-op 占位 (echo), CI 在 cockpit-ui 子仓 |

**风险**: 低。前两个有实际 CI 覆盖, 后三个本来就是文档占位。

### 决策 2: 新增 ci-surfaces workflow_triggers 生成器

`bin/ssot/gen-ci-surfaces-triggers.py`:

- 从 `.github/workflows/*.yml` 解析实际触发 (on:) 与 paths, 重建
  `ci-surfaces.yaml` 的 `workflow_triggers` 段
- 文本级替换, 保留 `surfaces` 段人工登记与注释
- 解析正则与 check-ci-surfaces.py 完全一致 (同源同逻辑), 保证生成器产出
  不会被检测器判 drift
- 接入 rebase-regen.sh Step 2b → rebase 后一键对齐, 防 trigger-drift 复发

**效果**: 47 个 trigger-drift warns → 0。

### 决策 3: 修复内联 paths 检测盲区 (三方同步)

`paths: ['a', 'b']` 内联数组形式与多行块形式 `paths:\n - a` 都识别:

- `bin/ssot/workflow-health.py`
- `bin/gac/check-ci-surfaces.py`
- `bin/ssot/gen-ci-surfaces-triggers.py`

**效果**: 6 个子项目 CI (agora/ecos/kairon/metaos/observability/family-hub)
从 unpathed-pr 误报中消除。

### 决策 4: 给剩余高负载 PR workflow 加 paths (E-5 铺开)

- ci-python-coverage.yml: 7 矩阵 pytest 只在 7 个项目路径变化时跑
- quality.yml: ruff-lint 只在 4 个 tracked 项目 src 变化时跑

### 决策 5: workflow-health 豁免机制 (设计语义不报错)

- `COE_DESIGN_EXEMPT`: gac-gate/ai-pr-review/ci-python-coverage/quality/
  config-check/family-hub-ci/integration/kairon-ci/ci-lint —
  continue-on-error 是 advisory 收集型或 checkout 子模块容错, 非过度容忍
- `MANUAL_INTENT_EXEMPT`: pyright-sweep (manual 工具, 非 idle 死工作流)
- `UNPATHED_DESIGN_EXEMPT`: 12 个 gate/enforce 类 PR workflow —
  低成本规则门禁全量跑是设计, paths 过滤反而有漏跑风险

## 三、效果 (实测)

| 指标 | 前 | 后 |
|------|----|----|
| workflows | 41 | 37 |
| workflow-health issues | 35 | **0** |
| check-ci-surfaces warns | 47 | 4 (overlap, 设计语义) |
| healthcheck | ✅ | ✅ 全绿 |
| 每 PR ruff job | 2 (quality + ruff-check) | 1 |
| 每 PR pytest 矩阵 | 全量 | 仅 Python 面变更 |

## 四、验证

```bash
python3 bin/ssot/workflow-health.py        # scanned 37; 0 issues ✅
python3 bin/gac/check-ci-surfaces.py       # errors=0 warns=4 (overlap) ✅
python3 bin/gac/gac-healthcheck.py         # 总体全绿 ✅
python3 bin/ssot/gen-ci-surfaces-triggers.py --write  # 幂等, 无 diff
```

## 五、后续候选 (不在本轮范围)

- overlap 4 个 (gac-local-gate/submodule-reachability/sync-submodule-pointers/
  check-vault-paths 多 workflow 执行) — 需逐个判断是否合并 workflow
- M3/M4/M5 (drift 预测 / ADR 生成器 / 治理价值报告) 按 ADR-0386 roadmap
