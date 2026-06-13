# projects/omo Artifact Boundary (Reviewer Working Note)

**日期**: 2026-06-13  
**范围**: `projects/omo` 子仓内部历史 untracked artifacts 治理边界  
**目的**: 把 "哪些是应保留证据、哪些是历史漂移、哪些后续要治理" 说清楚，避免 reviewer 被 `git status` 噪声误导。

## 1. 当前问题

`projects/omo` 子仓当前不是 clean。除本轮 OPC closeout 相关修复外，还存在一批历史未跟踪文件，主要集中在：

- `.omo/_delivery/*.md|*.json`
- `.omo/tasks/active/*.yaml`
- `.omo/workers/runs/*`
- `.omo/d2_demo.py`
- `.omo/goals/current.yaml`
- `tests/test_opc_p3_thin_binding_demo.py`

这批文件不是同一性质，不能一锅端清理，也不能继续用“只剩一个 planned task”这种说法糊弄 reviewer。

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

### B. 历史 demo / probe / 临时 delivery 产物

这类文件不直接构成运行主线，但会污染 workspace clean 叙述：

- `.omo/_delivery/gbrain-probe-2026-06-11.md`
- `.omo/_delivery/kairon-probe-2026-06-11.md`
- `.omo/_delivery/metaos-probe-2026-06-11.md`
- `.omo/d2_demo.py`
- `tests/test_opc_p3_thin_binding_demo.py`

规则：

- 不在本轮 closeout 中伪装成“已治理”
- 后续单独做归档 / relocate / 删除决策
- 未决前统一标注为 historical artifacts

### C. 需要治理决策的状态文件

这些文件对系统行为有影响，不能靠 `.gitignore` 一把糊住：

- `.omo/goals/current.yaml`
- `.omo/tasks/active/*.yaml`
- `.omo/_delivery/audit-rollout/2026-06-12-5repos.json`

规则：

- 先判定 SSOT 与所有权，再决定是否纳入版本管理
- 未形成规则前，不得把其存在解释成 “0 dirty”

## 3. Reviewer 可接受口径

本轮可接受说法只有这一版：

> `projects/omo` 子仓内部仍存在历史 untracked artifacts。它们分为应保留治理证据、历史 demo/probe 产物、以及待治理状态文件三类。当前 closeout 只修复 OPC P5-P7 的 reviewer 争议，不宣称该子仓已 clean。

## 4. Next Action

1. 单独列出 `projects/omo` untracked 文件清单并按 A/B/C 三类打标签  
2. 对 B 类历史 demo / probe 产物做 relocate 或 archive 决策  
3. 对 C 类状态文件明确 SSOT / 是否纳入版本管理  
4. 形成一份子仓级治理 task，不与 OPC P5-P7 closeout 混写

补充：

- 精确清单见 `2026-06-13-projects-omo-untracked-inventory.md`
- C 类状态文件决策包见 `2026-06-13-projects-omo-c-class-decision-packet.md`
