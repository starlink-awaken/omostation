---
lifecycle: history
owner: governance-team
last_updated: "2026-07-29"
---
# P86 B1: 协作冲突消解六类失效根因判定

> 上位: P86 §B1 (冲突消解攻坚, 与 A 波并行)
> 🔴 熔断红线 (P86 §熔断): 不混口径/不为变绿改断言/不代批 §F
> 结论性质: **根因判定** (B1 验收: 每类根因 + 修复或显式降级). 修复实施归 B2.

## 触发数据 (批次3, 机制模拟口径)

A_conflict 对抗集 **1/27 = 4% 消解成功率**. 六类失效 criterion 分布:
| criterion | 失败次数 |
|-----------|---------|
| double_claim_detected | 5 |
| starvation_resolved | 5 |
| audit_reject_handled | 4 |
| orphan_detected | 4 |
| partial_failure_handled | 4 |
| unauthorized_detected | 4 |

## 根因判定 (逐类)

handler 实际只产生 9 种基础事件:
`write / conflict_detected / deadlock_break / role_timeout / subtask_fail /
cycle_detected / broken_chain_detected / chain_step_done / unknown_inject`

六类对抗冲突期望的专属事件, handler **均不产生**:

| 类 | 期望事件 | handler 现状 | 根因类型 |
|----|---------|------------|---------|
| double_claim | double_claim_detected | 仅 conflict_detected (不区分值冲突 vs 重复认领) | 🔴 **协议没设计** |
| starvation | starvation_resolved | 无资源争抢/饥饿检测 | 🔴 **协议没设计** |
| orphan | orphan_detected | 无"任务无人认领"检测 | 🔴 **协议没设计** |
| unauthorized | unauthorized_detected | 无角色权限校验 | 🔴 **协议没设计** |
| partial_failure | partial_failure_handled | 仅 subtask_fail (reassign_to 字段), 无"部分失败兜底"语义 | 🔴 **协议没设计** |
| audit_reject | audit_reject_handled | 无审计驳回通道 | 🔴 **协议没设计** |
| deadlock (ADV03) | deadlock_break (args.kind) | ✅ deadlock_break | 已实现, ADV03 pass (前版"命名不一致"为误判 — criterion **名** deadlock_broken 是标签, 实际检查 args.kind=deadlock_break 匹配 handler; 已纠正) |
| cycle (ADV01) | cycle_detected | ✅ cycle_detected | 已实现, ADV01 pass |
| broken_chain (ADV05) | broken_chain_detected | ✅ broken_chain_detected | 已实现, ADV05 pass |

## 统一根因

> **协作管线协议 (scenario_lib) 没有设计这 6 类对抗冲突的检测/消解事件类型.**
> handler 只覆盖"值冲突 (conflict_detected) + 死锁打破 (deadlock_break) + 超时 (role_timeout)
> + 子任务失败 (subtask_fail) + 链式环/断 (cycle/broken_chain_detected)".
>
> 对"重复认领 / 资源饥饿 / 孤儿任务 / 越权操作 / 部分失败兜底 / 审计驳回"这 6 类
> **真实多 agent 高风险场景**, 协议既不检测也不消解 → verdict criterion 永远 fail.

这是 **decl-exec-gap 的镜像**: 这次不是"声明了没执行", 而是"场景(声明)要求了, 但协议(执行层)
根本没这个能力". C2 ADR (多轮协商+冲突消解) ACCEPTED 但实测失效 — 失效在协议设计层.

## 修复方向 (B2, 待实施)

每类加一个 handler 检测分支 + 专属事件. 复杂度评估:

| 类 | 修复要点 | 复杂度 | 副作用风险 |
|----|---------|--------|-----------|
| double_claim | `_handle_write` 检测 ≥2 不同 role 写同 key (认领语义) | 🔴 **架构困境** | **A01(正常冲突) 与 ADV07(double_claim) inject 结构完全相同** (2 不同 role 写同 key 不同 value), handler 无法区分"值冲突"vs"重复认领" — inject 语义重载, 见 B3 |
| deadlock 命名 | deadlock_break → 修正 verdict 期望或事件名 | 极低 | 无 |
| partial_failure | `_handle_subtask_fail` 加 partial 兜底 (reassign + 标记) | 中 | 需定义"partial"语义 |
| orphan | 加"任务无人认领"扫描 (run 结束时) | 中 | 需 blackboard 任务注册 |
| unauthorized | 加角色权限矩阵 + 校验 | 高 | 需协议加权限模型 |
| starvation | 加资源配额 + 公平调度检测 | 高 | 需协议加资源模型 |
| audit_reject | 加审计钩子 + 驳回通道 | 中 | 需协议加审计层 |

**首个里程碑 (B2 目标值 ≥60%)**: 先修低复杂度 3 类 (double_claim + deadlock 命名 + partial_failure),
理论上可把消解率从 4% 推到 ~40% (3/6 类覆盖). 达到 60% 需再修 orphan.

## 降级选项 (B3, 若架构性难解)

若 unauthorized / starvation 判定为"需协议加权限/资源模型, 成本超 P86 范围":
→ **显式声明本版不支持这两类对抗冲突**, 场景库标 `unsupported`, 从对抗集排除 (不算 fail).
→ 送卡 §F.2 请人类决策: 重构协议加模型 vs 缩小协作适用面.

**不得含糊带过** (P86 §B3): 不能既不修也不标 unsupported, 让 4% 假装是"待优化".

## 本轮交付 (B1)
- ✅ 六类根因判定完成 (4 类协议没设计 + 1 类命名 bug + 2 类已实现样本问题)
- ⬜ B2 修复 (待实施, 首修 double_claim + deadlock 命名 + partial_failure)
- ⬜ B2 回归 + ≥60% 目标验证 (真 dispatch 口径, 非模拟)
- ⬜ B3 若 unauthorized/starvation 架构难解 → 送卡

## 口径声明 (熔断合规)
- 本判定基于**机制模拟** (run-scenario, handler 事件流), 非 真 dispatch
- B2 修复后的回归**必须用真 dispatch** (P86 §B2), 不用模拟 (熔断: 不混口径)
- 根因判定本身口径无关 (代码层事实), 但修复收益验证须真 dispatch
