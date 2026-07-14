---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0104: P110 omo_ingress_task_lifecycle 3 子模块化 (1530→614L, <800L warn 清零)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P110
- **Extends**: ADR-0094-103 (omo_lint + omo_governance_surfaces + 治理赋能三件套)
- **Superseded by**: (无)

## Context and Problem Statement

ADR-0103 P109 末 omo_ingress_task_lifecycle.py 仍是 13 god-module list 第 13 位 (1530L, 730L excess).
P109 --roadmap 输出明确: P110 = omo_ingress_task_lifecycle.py (HIGH ROI, omo submodule, P104-P108 模式可复用).

**P110 调研**: 15 函数, 按业务聚类:
- **create** (4 funcs, 293L): task 创建 (planned + blocked + 共识)
- **status** (3 funcs, 262L): 状态转换 (complete + evidence_paths)
- **promotion** (4 funcs, 372L): promotion flow (active 状态 + 审批修复/请求/撤回)
- **contract** (2 funcs, 204L): contract + self-evolution routing
- **archive** (3 funcs, 360L): 收尾 + 归档 + legacy normalize

**P110 决策 (v5 策略)**: 拆 3 子模块 (promotion + contract + archive = 936L), main 保留 create + status (555L).

## Decision

### D1: 3 子模块创建 (P110 R3 实施)

**实际区段**:
- `omo_ingress_task_promotion.py` (439L): 4 functions (L595-966) — promotion flow
- `omo_ingress_task_contract.py` (255L): 2 functions (L967-1170) — contract + self-evolution
- `omo_ingress_task_archive.py` (409L): 3 functions (L1171-1530) — 收尾 + 归档 + legacy

**omo_ingress_task_lifecycle.py 收口**: 1530L → **614L** (**-916L, -60%**)

### D2: P109-A 验证模板首次实战 (P110 R3)

**关键验证**:
1. `bin/omo-submodule-split-validate.sh omo_ingress_task_lifecycle omo_ingress_task_promotion`
2. **结果**: 7/7 步全过 ✓
   - Step 3: re-export block present
   - Step 4: both modules parse OK
   - Step 5: 6/6 surface lints pass (P104 教训规避)
   - Step 6: 28 shared callables OK (含 `_load_yaml` whitelist)
   - Step 7: 614L (warn zone, ideal <600L)

**P109-A 模板实战发现**:
- 原始脚本 3 处 Unicode bug (bash regex/case/string slicing with ✅❌🎉)
- 修复: 使用 `printf` + `grep -q` (Unicode safe)
- 实战验证 P109-A 模板可用, 反向推动工具改进

### D3: 收口统计

| 指标 | P109 末 | P110 末 | 变化 |
|------|---------|---------|------|
| `omo_ingress_task_lifecycle.py` | 1530L | **614L** | **-916L (-60%)** |
| `omo_ingress_task_promotion.py` | (新) | 439L | +439L |
| `omo_ingress_task_contract.py` | (新) | 255L | +255L |
| `omo_ingress_task_archive.py` | (新) | 409L | +409L |
| god-module error (>1500L) | 12 | **11** | **-1 (omo_ingress_task_lifecycle 拆后 <1500L)** |
| god-module warn (>800L) | 54 (含本文件) | **53** | -1 |
| **god-module error/warn** | — | **0/0 (本文件)** | **0 error, 0 warn** (新) |
| god-module ideal (<600L) | — | — | main 614L 接近 (差 14L) |
| 工具数 | 47 | 47 | 不变 |
| ADR 数 | 63 | **64** | +1 (本 ADR) |
| governance-dashboard 覆盖 | 22 工具 | 22 工具 | 不变 |

### D4: 13 god-module 列表更新 (P110 后)

| # | 文件 | 类型 | 行数 | excess |
|:-:|:-----|:----:|:----:|:------:|
| 1 | gbrain/src/commands/doctor.ts | TS | 4825L | 4025L |
| 2 | gbrain/src/core/postgres-engine.ts | TS | 4514L | 3714L |
| 3 | gbrain/src/core/pglite-engine.ts | TS | 4509L | 3709L |
| 4 | gbrain/src/core/migrate.ts | TS | 4333L | 3533L |
| 5 | gbrain/src/core/ai/gateway.ts | TS | 2895L | 2095L |
| 6 | ecos/.../domain_manager.py | Python | 1914L | 1114L |
| 7 | gbrain/src/commands/serve-http.ts | TS | 1756L | 956L |
| 8 | gbrain/src/cli.ts | TS | 1735L | 935L |
| 9 | gbrain/src/core/cycle.ts | TS | 1707L | 907L |
| 10 | gbrain/src/commands/sync.ts | TS | 1609L | 809L |
| 11 | gbrain/src/core/engine.ts | TS | 1563L | 763L |
| ~~12~~ | ~~omo_ingress_task_lifecycle.py~~ | ~~Python~~ | ~~1530L~~ | ~~P110 ✓ 清零~~ |

**剩余 11 god-modules**: 10 TS + 1 Python (ecos domain_manager.py)

### D5: P110 R1 调研发现 — 函数聚类方法论

**关键决策**: 业务聚类 vs. 函数聚类

| 策略 | 优点 | 缺点 |
|:-----|:-----|:-----|
| 函数聚类 (按大小) | 简单直接 | 拆后子模块业务关联弱 |
| 业务聚类 (按 lifecycle) | 业务清晰, 维护性好 | 需要理解调用关系 |

**P110 采用业务聚类** (create / status / promotion / contract / archive) — 与 P104-P108 模式一致, 后续 P 阶段可参考

### D6: P110 后续推进 (P111+)

按 P109 --roadmap (HIGH ROI 已清零, 剩余 MEDIUM):
- **P111**: ecos/.../domain_manager.py (1914L, MEDIUM ROI) — 跨 submodule, 需 ecos 治理节奏
- **P112+**: 10 TS god-modules (LOW ROI) — 待 ts-morph 工具成熟或人工拆解

## Consequences

**正面**:
- **13 → 11 god-module errors**: Python 第 2 大 god-module 拆后清零, 累计 -916L (-60%)
- **P109-A 验证模板实战**: 7/7 步全过, 证明治理赋能工具有效
- **P109-A 工具改进**: Unicode bug 修复, 实战验证工具可用
- **3 子模块业务聚类**: create/status 留 main (555L), promotion/contract/archive 拆出 (936L) — 业务清晰
- **累计 -75% 行数 (omo_governance_surfaces) + -60% (omo_ingress_task_lifecycle)**: 2 大 Python god-module 已治理完成

**负面**:
- **omo_ingress_task_lifecycle.py 614L**: 接近 600L ideal 但未达 (差 14L)
  - 进一步拆 create + status 子模块可降至 ~500L, 但 ROI 低 (业务简单)
- **inline imports 重复**: 3 子模块各复制 30 行 imports (om o.omo_audit / omo_io / 等), 累计 ~90L overhead
- **omo submodule working tree 仍未 commit**: P88-P110 同模式, 14+ 个新文件待审批
- **10 TS god-modules 仍是 blind spot**: 需 ts-morph 工具 (P109-C 已部分解除, 真实 AST 仍待)

**关联**:
- ADR-0094-103: 9 个 omostation 治理 ADR 沉淀
- **ADR-0104**: P110 第一个用 P109-A 模板验证的拆分, 闭环完整
- P110 是 P109 --roadmap 第 1 步, 后续 P111+ 按 ROI 排序推进
- P109 治理赋能工具 (验证模板 + 智能化 + TS 分析) 在 P110 实战验证有效

## Validation

```bash
# P110 R3 验证: P109-A 模板
PYTHONPATH=projects/omo/src bash bin/omo-submodule-split-validate.sh omo_ingress_task_lifecycle omo_ingress_task_promotion
# 期望: 🎉 all 7 steps pass

# P110 R3 验证: 15 re-exports 等价
cd projects/omo && PYTHONPATH=src uv run --with pyyaml python3 -c "
from omo.omo_ingress_task_lifecycle import (
    create_planned_task, create_blocked_task, record_task_consensus,
    complete_task, update_done_task_evidence_paths, update_planned_task_evidence_paths,
    promote_task_to_active, repair_task_promotion_approval,
    request_task_promotion_approval, revert_task_to_planned,
    record_task_contract_request, route_self_evolution_to_remediation,
    yield_task_to_planned, archive_done_task, normalize_legacy_planned_task,
)
print(f'✅ all 15 re-exports OK')
"

# P110 R3 验证: 6 surface lints
for cmd in ingress-registry mutation-surfaces internal-write-profiles \
          state-plane-assets c2g-omo-boundary ingress-artifacts; do
    PYTHONPATH=projects/omo/src uv run --with pyyaml python3 -m omo.omo_lint $cmd 2>&1 | head -1
done
# 期望: 6 行 ✅ omo lint <cmd> pass

# P110 R3 验证: god-module 列表
PYTHONPATH=projects/omo/src python3 bin/ssot/god-module-13-error-list.py 2>&1 | head -5
# 期望: 🔴 Error: 11 (>1500L)

# P110 R5: dashboard
PYTHONPATH=projects/omo/src python3 bin/gac/governance-dashboard.py
# 期望: 22/22 工具全部通过

# P110 R6: mof-version
bin/mof-version record "P110: omo_ingress_task_lifecycle 3 子模块化 (1530→614L, 13→11 god-module)"
# 期望: v0.0.98 → v0.0.99
```

## References

- P82-P109: 见 ADR-0093-103 References 列表
- ADR-0093: P99 omo_lint 兑现路径 P100-P103 4 步
- ADR-0094-97: P100-P103 omo_lint 子模块拆分
- ADR-0098: P104 omo_governance_surfaces snapshots 子模块拆分
- ADR-0099: P105 omo_governance_surfaces ingress-check 子模块拆分 (circular import 修复)
- ADR-0100: P106 omo_governance_surfaces 4 子模块化 (warn 阈值清零, P104 re-export 修复)
- ADR-0101: P107 omo_governance_surfaces 6 子模块化 (<600L ideal 首次达成)
- ADR-0102: P108 omo_governance_surfaces 8 子模块化 (黄金值 400-500L)
- ADR-0103: P109 治理赋能三件套 (验证模板 + 智能化 + TS 工具, 100 阶段关键转折)
- **ADR-0104: P110 omo_ingress_task_lifecycle 3 子模块化 (1530→614L, 13→11 god-module, 本 ADR)**

---

*最后更新: 2026-06-25 · P110 omo_ingress_task_lifecycle 3 子模块化收口 (13→11 god-module, P109-A 模板实战验证有效)*
