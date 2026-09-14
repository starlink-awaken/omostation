---
type: ephemeral
status: archived
---

# 协作场景库（能力轨 · STRAT-P84 W1）

> 测**协作机制响应质量**（能力轨），**不计入产能轨**。
> 🔴 红线 (P84 §0): 构造场景只进能力轨, 绝对不计产能轨 (与"造任务凑数"同级最高级违规)。

## 位置
`.omo/_delivery/collab-scenarios/` · runner: `bin/collab/run-scenario.py`

## 场景 schema（声明式 YAML, 机器可读）

```yaml
---
status: active
lifecycle: ssot
owner: governance-team
last-reviewed: 2026-07-28
---
id: A01-product-divergence          # 唯一 ID (类前缀 + 序号)
category: A_conflict                # A_conflict | B_failure_injection | C_decomposition | D_reuse_pair
adversarial: false                  # W1.2 对抗集标记 (库 ≥20% 须对抗)
seed: 42                            # 可复现 (同 seed 同结果)
description: ...
setup:
  blackboard:                       # 黑板初始产物
    - {key: artifact_x, value: null}
  roles: [research, delivery]       # 参与角色
inject:                             # 注入事件 (冲突/故障), 顺序确定性
  - {type: write_conflict, role: research, target: artifact_x, value: "方案A"}
expected:
  behavior: conflict_detected_and_resolved
  max_resolution_rounds: 3
  silent_loss: 0                    # 硬红线 (=0)
verdict:                            # 机器可读判定准则
  - criterion: conflict_logged
    check: events_contain
    args: {kind: conflict_detected}
  - criterion: no_silent_loss
    check: silent_loss_eq
    args: {expected: 0}
```

## 四大类（W1 建框架, W2 填满 ≥100）
| 类 | 目标 | 测什么 |
|----|------|--------|
| **A 冲突原型** | ≥20 种 | 产物分歧/优先级/资源争抢/审计驳回/协商死锁/双认领 |
| **B 失败注入** | ≥8 种 | 角色超时/子任务失败重分派/角色不可用/产物损坏/黑板写失败 |
| **C 分解组合** | ≥6 种 | 链式/星型/菱形/环检测 复合任务 |
| **D 复用配对** | ≥6 对 | 先 A 后相似 B, 直接测黑板命中率 |

## inject type → 事件 kind 映射（runner 规则）
| inject.type | 产生事件 kind | 协作机制约束 |
|-------------|--------------|-------------|
| `write_conflict` | `write` 或 `conflict_detected` (分歧时) | 产物分歧检测 |
| `role_timeout` | `role_timeout` | 角色超时检测 |
| `subtask_fail` | `subtask_fail` (reassigned 看有无 reassign_to) | 失败重分派 |
| `chain_step` | `chain_step_done` 或 `silent_loss` (依赖缺) | 依赖拓扑 + 静默丢失 |

## verdict check 函数（机器可读判定）
| check | args | 判定 |
|-------|------|------|
| `events_contain` | `{kind}` | 事件流含指定 kind |
| `resolution_rounds_le` | `{max}` | 协商轮次 ≤ max |
| `silent_loss_eq` | `{expected}` | 静默丢失 == expected (硬红线 0) |
| `final_artifact_present` | `{key}` | 黑板最终含产物 |
| `all_writers_resolved` | `{key}` | 同一产物多写者已收敛 |

## 对抗集（W1.2, ≥20%）
由专门角色设计**试图让管线失败**的输入 (矛盾需求/循环依赖/超长链/恶意模糊/相互否定验收),
设计者**不预设正确答案**。至少 3 个**真的失败** (全过 = 对抗不足, 须上报并加强)。

## Runner
```bash
python3 bin/collab/run-scenario.py .omo/_delivery/collab-scenarios/A01-product-divergence.yaml
python3 bin/collab/run-scenario.py --dir .omo/_delivery/collab-scenarios/   # 全量跑批
python3 bin/collab/run-scenario.py --dir ... --json                         # 机器可读
```

## 熔断条件（P84 §熔断, 长期有效）
- 🔴 构造场景计产能轨 = 最高级违规
- 🔴 对抗场景全过不加强 = 自欺 (须上报并补设计)
- 🔴 对照实验协作劣于单 agent 不上报 = 违规
- 🔴 静默丢失 >0 = 立即停管线写卡

## 双轨分列原则（BRIEF）
- **能力轨** (本库): 场景数/覆盖/通过率/对抗失败率/冲突消解成功率/协商轮次
- **产能轨** (真实 backlog): 真实任务数/完成率/人工直做/静默丢失 (≠ 本库)
- BRIEF 两块**必须分列**, 禁止合并成单一"任务数"
