---
status: active
lifecycle: ssot
owner: governance-team
last-reviewed: 2026-06-22
---

# P44 Closed-Loop Pattern — M3 Lifecycle Instance (Governance Catch-up + Drift 治本)

> **Generated**: 2026-06-22 (post-P44 R7)
> **SSOT**: `.omo/_truth/mof-version.yaml` v0.0.26
> **Purpose**: 用 M3 元元模型实例化 P44 闭环作为可复用模式
> **Inspired by**: P43 closed-loop-pattern (c2g → omo → mof 三层联动)

## 1. P44 与 P43 差异

P43 是"**债务驱动**"的闭环（5 debt evidence closure → governance 85→100）。
P44 是"**治理滞后**"的闭环：代码已收敛于 Phases 1-9，但治理状态未同步；状态数据漂移；新发债务预防。

| 维度 | P43 | P44 |
|------|-----|-----|
| 触发 | 5 debt evidence closure | wf-convergence 5 REMEDIATE 全 active 但代码已 done |
| 核心矛盾 | debt 缺证据 → governance 不能 pass | 治理状态滞后于实际代码 |
| Pattern 关键 | `c2g → omo → mof` 三层联动 | 同 P43, 但多了 `drift 校正` 环节 |
| mof-version | v0.0.7 → v0.0.12 (5 步) | v0.0.24 → v0.0.26 (2 步) |
| drift 处理 | 18 F821 ruff 修复 | mof-drift 7→1 (校正工具 + 修 1 真硬编码) |
| 子模块治理 | submodule_state_decoupling 教训 | 同 P43, 锁仓 P44 PLANNED |

## 2. P44 R1-R7 阶段映射

| Round | 主题 | 关键产物 | 治理面写入 |
|-------|------|---------|------------|
| R1 | 治理基线 | 32 files commit + 5 REMEDIATE 任务登记 + bin/mof-act | git + `.omo/_truth/` |
| R2 | c2g 立项 | c2g bet BET-d6d9 + P44-REMEDIATE-WF-CONV-CLOSE PLANNED | `projects/c2g/bets.json` + `.omo/tasks/planned/` |
| R3 | 关闭 REMEDIATE | 5 REMEDIATE + BET → done + close_remediations.py | `.omo/tasks/{planned,remediation,done}/` |
| R4 | deferred 物化 | 4 P44-DEFER PLANNED (Executor/omo/gbrain/sys.path) | `.omo/tasks/planned/P44-DEFER-*` |
| R5 | submodule 锁仓 | P44-SUBMODULE-PIN PLANNED | `.omo/tasks/planned/P44-SUBMODULE-PIN` |
| R6 | drift 治本 | mof-drift v2 校正 + omo_weekly_loop.py 修复 + 2 task done | `bin/mof-drift` + `projects/omo/...` |
| R7 | 子模块盘点 | 229 dirty 报告 + 8 P44 PLANNED 治理可见性 | `.omo/_knowledge/audits/` |

## 3. P44 模式关键 (可复用度)

| 环节 | 可复用度 | 复用条件 | 关键经验 |
|------|---------|---------|---------|
| **`c2g brainstorm` + 手动填 pitch** | **高** | 任意需求点 | LLM Gateway 不可用时回退 mock, pitch 必须手动补 Upstream/Appetite |
| **`omo broker` Python 直接调** | **高** | metadata: {} 必填 | `setdefault` 必须在 dict 上, None 上不工作 |
| **`promote_task_to_active` + `complete_task` 链路** | **高** | 任务 done 需 evidence_paths 物理存在 | approval_ref 对 L2/L3 必填 |
| **`close_remediations.py` 批量模式** | **高** | status=done + resolution_evidence + commit_ref | 一次性 close 全部 historical REMEDIATE |
| **`deferred-tracking` 物化** | **高** | 母项 closed 但子项 deferred | 不强行 close 母项, 显式 PLANNED 跟踪 |
| **`drift 校正` 工具 v2** | **高** | mof-drift 误报过多时 | 区分硬编码 vs 相对路径 + 排除 docker 项目 |
| **子模块治理 P43 教训** | **高** | submodule_state_decoupling | 根仓只 commit 元数据, 不批量 bump, 锁仓 PLANNED |

## 4. 三层联动 (c2g → omo → mof)

```
c2g brainstorm "Phase 44 治理"           # 需求侧建模 (R2)
   ↓ pitch (手动填 Upstream/Appetite)
c2g bet                                   # 战略登记 BET-d6d9
   ↓
omo governance ingress-task               # broker 物化 (Python 直接调)
   ↓ P44-REMEDIATE-WF-CONV-CLOSE
omo promote_task_to_active + complete_task # active → done (R3, R6)
   ↓
bin/mof-version record                     # mof-version 升级 v0.0.24→v0.0.26
   ↓
bin/mof-drift v2 校正                      # drift 7→1 (R6)
   ↓
git commit + submodule pointer bump        # 落地 (R5, R7)
```

## 5. 与 P43 闭环对比

| 维度 | P43 (v0.0.12) | P44 (v0.0.26) |
|------|---------------|---------------|
| 闭环时长 | 5 Rounds | 7 Rounds |
| commits | 12 | 6 (R1-R7) |
| 物化 PLANNED | 0 (全 debt 直接 close) | 9 (1 done + 8 deferred) |
| drift 项 | 18 F821 修复 | 7→1 校正 |
| 子模块治理 | 4 子项目 lint=0 | 13 子模块盘点 + 8 PLANNED |
| 模式文档 | `.omo/_knowledge/patterns/p43-closed-loop-pattern.md` | `.omo/_knowledge/patterns/p44-closed-loop-pattern.md` (本文件) |
| 收口报告 | `.omo/_knowledge/audits/2026-06-19-p43-closed-loop.md` | `.omo/_knowledge/audits/2026-06-22-p44-closed-loop-closeout.md` |

## 6. P44 关键产物清单

### 已 done
- 5 REMEDIATE-WF-CONV-* (commit 02898ccd)
- BET-WF-CONVERGENCE-REAL (commit 02898ccd)
- P44-REMEDIATE-WF-CONV-CLOSE (commit f9744533)
- P44-SUBMODULE-PIN (commit f9744533)
- 3 P43 历史 (R5 之前)

### 已 PLANNED (deferred-tracking)
- P44-DEFER-EXECUTOR-SPLIT (medium)
- P44-DEFER-OMO-SUBPKG (medium)
- P44-DEFER-GBRAIN-OPS-SPLIT (low)
- P44-DEFER-GBRAIN-TODOS (P3)
- P44-DEFER-SYS-PATH-INSERT (medium, 校正后无新发现)
- P44-DEFER-SUBMODULE-PUSH (P1, 2 子仓待推)
- P44-BET-3b90-FOLLOWUP (P2, human product)

### 已收口报告
- `.omo/_knowledge/audits/2026-06-22-p44-closed-loop-closeout.md` (R5)
- `.omo/_knowledge/audits/2026-06-22-p44-r7-submodule-dirty-audit.md` (R7)
- `.omo/_knowledge/patterns/p44-closed-loop-pattern.md` (本文件)

## 7. 治理验证

| 指标 | P43 收口 | P44 收口 | 状态 |
|------|---------|---------|------|
| omo governance | 100 A+ | 100 A+ | ✅ 持续 |
| mof-drift | 0 (治本) | 1 LOW (gbrain TODOs, deferred) | ✅ 改善 |
| mof-version | v0.0.12 | v0.0.26 | ✅ 升级 14 步 |
| debt 总数 | 33 (29 closed + 4 deferred) | 37 (33 closed + 4 deferred) | ✅ 收敛 |
| 5+3+1 治理面 | 全绿 | 全绿 | ✅ 持续 |
| X1-X4 约束 | 0 违规 | 0 违规 | ✅ 持续 |

## 8. 失败模式与教训 (P44 增项)

1. **omo broker metadata 注入陷阱**: 手写 yaml 不能有 `metadata: null`，必须 `metadata: {}` 让 setdefault 注入
2. **drift 工具误报**: 粗粒度 grep `sys.path.insert` 不能区分硬编码 vs 相对路径
3. **planned → done 路径**: 必须 `promote_task_to_active` → `complete_task` 两步，evidence_paths 物理存在
4. **子模块 dirty 是子仓的事**: 根仓 gitlink MATCH 即合规，子仓内部 dirty 锁仓 PLANNED

## 9. 复用模板

```bash
# 1. c2g brainstorm (LLM Gateway 可用时直接走)
c2g --adapter ecos brainstorm "<主题>"

# 2. 手动补 pitch Upstream/Appetite
# (LLM Gateway 不可用时回退 mock，需手填)

# 3. bet
c2g --adapter ecos bet .c2g_data/pitches/<file>.md

# 4. omo broker 物化 (Python 直接调, metadata: {} 必填)
python3 -c "
import sys; sys.path.insert(0, 'projects/omo/src')
from pathlib import Path
from omo.omo_ingress import create_planned_task
task_data = {..., 'metadata': {}}
create_planned_task(Path('.omo'), task_data=task_data, ingress_plane='c2g', source_ref='BET-xxx')
"

# 5. promote + complete (evidence_paths 物理存在)
python3 -c "
import sys; sys.path.insert(0, 'projects/omo/src')
from pathlib import Path
from omo.omo_ingress import promote_task_to_active, complete_task
promote_task_to_active(Path('.omo'), task_id='PXX-...', actor='agent-runtime')
# 加 evidence_paths 到 active yaml
complete_task(Path('.omo'), task_id='PXX-...', actor='agent-runtime')
"

# 6. mof-version record
bin/mof-version record "<描述>"

# 7. drift 校正 (粗粒度工具误报时)
# 改 bin/mof-drift count_sys_path_hacks 区分硬编码/相对路径

# 8. commit (Atomic 强制)
git add -A && git add -f .omo/_delivery/ingress/tasks/PXX-*.yaml
git commit -m "..."
```

## 10. 关联

- Pattern 来源: `.omo/_knowledge/patterns/p43-closed-loop-pattern.md`
- Schema: `projects/ecos/src/ecos/ssot/mof/m2/omo_task.yaml`
- L0 Constraints: `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`
- 收口报告: `.omo/_knowledge/audits/2026-06-22-p44-closed-loop-closeout.md`
- 子模块盘点: `.omo/_knowledge/audits/2026-06-22-p44-r7-submodule-dirty-audit.md`
- 8 PLANNED 任务: `.omo/tasks/planned/P44-*.yaml`
