---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# projects/omo Artifact Boundary (Reviewer Working Note)

**日期**: 2026-06-13  
**范围**: `projects/omo` 子仓内部历史 untracked artifacts 治理边界  
**目的**: 把 "哪些是应保留证据、哪些是历史漂移、哪些后续要治理" 说清楚，避免 reviewer 被 `git status` 噪声误导。

## 1. 当前问题

`projects/omo` 子仓当前不是 clean。除本轮 OPC closeout 相关修复外，还存在一批历史未跟踪文件，主要集中在：

- `.omo/_delivery/*.md|*.json`
- `.omo/tasks/archive/demo-phase29/*.yaml`
- `.omo/workers/runs/*`
- `.omo/_archive/demo-phase29/d2_demo.py`
- `.omo/goals/current.yaml`
- `tests/archive/test_opc_p3_thin_binding_demo.py`

这批文件不是同一性质，不能一锅端清理，也不能继续用“只剩一个 planned task”这种说法糊弄 reviewer。当前已经完成一轮边界收口，但还没到 clean；子仓 untracked 面已经从 51 收到 1。

## 2. 边界分类

### A. 应保留的治理证据

这些文件属于 OMO 运行证据或任务轨迹，不应在 closeout 里被当作“垃圾文件”：

- `.omo/workers/runs/` 下 dispatch / envelope / prompt / review / reclaim / approval 轨迹
- `.omo/tasks/planned/OPC-P6-SELF-EVOLUTION-nop-*.yaml`
- 与已登记任务直接关联的 acceptance / approval / promotion records

规则：

- 不得为了“看起来干净”而删除
- 不得把 `planned/` 任务改推 `active/`
- 必须保留 reviewer 可追溯性
- 当前通过 `projects/omo/.gitignore` 作为本地运行证据处理

### B. 历史 demo / probe / 临时 delivery 产物

这类文件不直接构成运行主线，但会污染 workspace clean 叙述：

- `.omo/_archive/probes/2026-06-11/gbrain-probe-2026-06-11.md`
- `.omo/_archive/probes/2026-06-11/kairon-probe-2026-06-11.md`
- `.omo/_archive/probes/2026-06-11/metaos-probe-2026-06-11.md`
- `.omo/_archive/demo-phase29/d2_demo.py`
- `tests/archive/test_opc_p3_thin_binding_demo.py`

当前状态：

- 已从主线目录迁走
- 当前通过 `projects/omo/.gitignore` 作为本地保留物处理
- 不等于已经 clean；只是语义边界不再污染 active / delivery 主叙事

### C. 需要治理决策的状态文件

这些文件对系统行为有影响，不能靠 `.gitignore` 一把糊住：

- `.omo/goals/current.yaml`
- `.omo/_delivery/audit-rollout/2026-06-12-5repos.json`

当前状态：

- `.omo/goals/current.yaml` 仍是 live SSOT，不能乱动
- `2026-06-12-5repos.json` 已按运行产物写入 `projects/omo/.gitignore`
- 未形成规则前，不得把其存在解释成 “0 dirty”

## 3. Reviewer 可接受口径

本轮可接受说法只有这一版：

> `projects/omo` 子仓内部仍存在 1 条有意保留的 untracked 状态文件，即 `.omo/goals/current.yaml`。`workers/runs` 治理证据、demo/probe/task 残留与 rollout 输出已退出 untracked 主噪声面。当前 closeout 不宣称该子仓已 clean。

## 4. Next Action

1. 已完成 `projects/omo` untracked 文件清单，并按语义分类  
2. 已完成 B 类历史 demo / probe 产物迁移到 archive  
3. 已把 5 个 demo active task 从 live active 面移出，并同步状态面  
4. 下一步只剩 `goals/current.yaml` 的版本管理决策

补充：

- 精确清单见 `2026-06-13-projects-omo-untracked-inventory.md`
- C 类状态文件决策包见 `2026-06-13-projects-omo-c-class-decision-packet.md`
