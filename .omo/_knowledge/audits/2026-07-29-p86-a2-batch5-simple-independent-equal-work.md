---
status: active
lifecycle: history
owner: governance-team
last-reviewed: "2026-07-29"
type: ephemeral
status: archived
---

# P86 A2 批次5: scenario_lib 等量并行微基准（已降级）

> ⚠️ **冷启动**: 协作收益**现行定论**只读  
> [`.omo/_knowledge/audits/2026-07-29-p86-a2-collaboration-gain-map.md`](2026-07-29-p86-a2-collaboration-gain-map.md)  
> （5.4x 作废 · batch5 demote · 多 agent 真 dispatch 3 类型 shortfall · ADR-0289/0290）


> 🔴 **DEMOTE (2026-07-29 skeptic)**: 本实验是 ThreadPool × `scenario_lib.run_scenario`，  
> **不是** 多 agent / 协作管线 vs 单 agent 真 dispatch。  
> **禁止** 用于 A2 真 dispatch 定论表、**禁止** 支撑 C 波「多 agent 协作适用面」正收益声称。  
> 仅作「独立 well_defined 单元可并行」的机制附录。

## 方法

对 3 个独立 designed 场景顺序 vs 线程池并行各跑 `run_scenario`：

- ADV01 / ADV03 / ADV05

| 模式 | 墙钟 |
|------|------|
| 顺序 | **0.032s** |
| 并行包络 | **0.019s** |

## 允许的结论

- scenario runner 对独立单元可并行加速（机制层）

## 禁止的结论

- 「简单独立批量多 agent 协作墙钟优 1.65x」  
- 任何替代已作废 **5.4x** 的多 agent 定论  
