# Control Plane — 控制面

> 定义方向、阶段状态、门禁、决策快照。
> 只保留**当前态**，历史进入 knowledge/process 或 archive。

## 核心 SSOT

| 文件 | 职责 |
|------|------|
| `goals/current.yaml` | 当前 Phase 目标与 Waves |
| `state/system.yaml` | 系统状态、健康分、债务、阶段完成记录 |
| `_control/governance-overlay/current.yaml` | 治理叠加层当前快照 |
| `_control/governance-overlay/autopilot-policy.yaml` | 自动治理策略 |
| `_control/governance-overlay/roadmap.yaml` | 治理路线图与里程碑 |
| `_control/task-center/control/current.yaml` | 当前控制决策（预算/门禁） |

## 写入规则

- 新增内容必须先判平面：是否属于"方向/状态/门禁/决策"？
- 历史状态不堆积，完成即归档至 `_knowledge/process/` 或 `_archive/`
- 所有控制面文档必须可回指 truth 面的底层任务/标准
