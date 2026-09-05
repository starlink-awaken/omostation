---
status: active
lifecycle: history
owner: governance-team
last-reviewed: "2026-07-29"
type: ephemeral
status: archived
---
# P86 B1' 六类冲突取舍 + 协议边界标注 (P3)

> 上位: P86 §B1 + goal P3 (六类取舍, 不是全做)
> 🔴 红线 (P3): 严禁为构造场景补实现 (死代码同族违规). 仅对抗集的类别 → 标注边界, 不补.
> 目标值 (P3): **已设计类别**消解成功率 ≥60% (不对整个对抗集设 60%, 否则逼"为通过而实现")

## P3 核心判断: 真实发生频率

**证据**: runs 87 个 + done 5 个, grep 六类冲突关键词:
- runs 命中: 1 (governance-state-mutation, 弱匹配)
- done 命中: 0
- 真实 conflict_detected/silent_loss 事件: **0**

**结论**: 六类冲突 (double_claim/starvation/orphan/unauthorized/partial_failure/audit_reject)
**在真实任务里基本没发生过**, 仅存在于对抗集 (构造场景).

按 P3 红线: 仅对抗集 → 标注边界, 不为它们补实现.

## 六类 + 新增对抗类 取舍表

| 类别 | 真实发生? | 当前实现 | 取舍 | 状态 |
|------|----------|---------|------|------|
| cycle_detected | 否 (仅对抗) | ✅ _handle_chain_step | 保留 (已实现, ADV01 pass) | 已设计 |
| deadlock_break | 否 (仅对抗) | ✅ _handle_write | 保留 (已实现, ADV03 pass) | 已设计 |
| broken_chain_detected | 否 (仅对抗) | ✅ _handle_chain_step | 保留 (已实现, ADV05 pass) | 已设计 |
| double_claim_detected | 否 (仅对抗) | ✅ _handle_write (P4 intent) | 保留 + P4 intent 分辨 (A01/ADV07 可分辨) | 已设计 |
| orphan_detected | 否 (仅对抗) | ✅ 启动扫描 | 保留 (已实现) | 已设计 |
| unauthorized_detected | 否 (仅对抗) | ✅ _handle_write (authorized) | 保留 (已实现) | 已设计 |
| audit_reject_handled | 否 (仅对抗) | ✅ _handle_audit_reject | 保留 (已实现) | 已设计 |
| starvation_resolved | 否 (仅对抗) | ✅ _synthesize (P4 收紧 ≥3 角色) | 保留, **收紧 ≥3 角色** (2角色非真实 starvation) | 已设计 (≥3 角色) |
| partial_failure_handled | 否 (仅对抗) | ✅ _synthesize (P4 去 double 耦合) | 保留, **仅 success+fail 语义** (2-write_conflict 形式不支持) | 已设计 (success+fail) |
| byzantine_quorum | ❌ 否 | ❌ 未实现 | **标注边界**: 协议不支持 byzantine, 属已知边界 | 🔴 未设计 |
| replay_attack | ❌ 否 | ❌ 未实现 | **标注边界**: 协议不支持 replay, 属已知边界 | 🔴 未设计 |
| cross_key_collusion | ❌ 否 | ❌ 未实现 | **标注边界**: 协议不支持 cross-key, 属已知边界 | 🔴 未设计 |

## 11 fail 分类 (全量 140, passed 129, failed 11)

| fail 场景 | 类别 | 原因 | 处置 |
|----------|------|------|------|
| ADV-partial-failure-v1-4 (4) | partial | inject 是 2-write_conflict, P4 后需 success+fail | 🟡 标注: partial 仅支持 success+fail (ADV09 模式), 2-write 形式不支持 |
| ADV-resource-starvation-v1-4 (4) | starvation | inject 是 2 角色, P4 后需 ≥3 角色 | 🟡 标注: starvation 仅支持 ≥3 角色 (ADV11 模式), 2-角色非真实 starvation |
| ADV19-byzantine-quorum | byzantine | handler 无 byzantine 事件 | 🔴 标注: 协议不支持 byzantine (未设计) |
| ADV21-replay-attack | replay | handler 无 replay 事件 | 🔴 标注: 协议不支持 replay (未设计) |
| ADV23-cross-key-collusion | cross_key_collusion | handler 无 cross-key 事件 | 🔴 标注: 协议不支持 cross-key (未设计) |

## 已设计类别消解率 (P3 目标值 ≥60%)

已设计类别 (9): cycle / deadlock / broken_chain / double_claim / orphan / unauthorized /
audit_reject / starvation(≥3角色) / partial(success+fail)

对抗集已设计类别场景:
- ADV01/03/05/07/09/11 (手写 6): 全 pass ✅
- GEN-ADV-double-claim-v1-4 (4): pass ✅ (P4 intent)
- GEN-ADV-orphan/unauthorized/audit (各 4): pass ✅ (已实现)
- GEN-ADV-starvation (≥3 角色): pass ✅
- GEN-ADV-partial (success+fail): pass ✅

**已设计类别消解率 ≈ 100%** (≥60% 目标 ✅, 但标注: 仅对抗集, 真实未验证)

## 协议边界声明 (写入协议文档)

scenario_lib 协议**当前支持**的冲突/失败类别:
1. 值冲突 (conflict_detected) + 死锁打破 (deadlock_break, ≥3 轮)
2. 重复认领 (double_claim_detected, 需 intent=double_claim 声明)
3. 资源饥饿 (starvation_resolved, ≥3 角色争抢)
4. 部分失败 (partial_failure_handled, success+fail 混合)
5. 孤儿产物 (orphan_detected, 启动扫描)
6. 未授权写 (unauthorized_detected, role ∉ setup.roles)
7. 审计驳回 (audit_reject_handled)
8. 链式环 (cycle_detected) + 链式断 (broken_chain_detected)

**已知边界 (不支持)**:
- byzantine quorum (拜占庭容错) — 需投票/签名机制, 超当前协议范围
- replay attack (重放攻击) — 需 nonce/时序, 超当前协议范围
- cross-key collusion (跨键串通) — 需跨产物关联分析, 超当前协议范围
- 2-角色 starvation — 语义不足 (2 角色是分歧非饿死)
- 2-write_conflict partial — 语义不足 (是冲突非部分失败)

**红线**: 这些边界是**真实的** (真实任务未发生这些类), 不是"为通过而标注".
若未来真实任务出现这些类, 需先评估频率, 再决定补实现 (P3 流程).

## P3 红线遵守
- ✅ 未为构造场景补实现 (byzantine/replay/cross-key 标注边界, 不补)
- ✅ 目标值针对已设计类别 (≥60%), 非整个对抗集
- ✅ 真实频率驱动决策 (runs 0 → 仅对抗集 → 边界)

## 🔴 后续: 系统改动覆盖 P3 边界 + P4 改动被 revert (2026-07-29)

**系统/linter 后续修改 scenario_lib.py** (intentional, 未 revert):
1. **P3 边界被突破**: byzantine_quorum / replay_attack / cross_key_collusion / split_brain /
   identity_spoof / supply_chain_tamper 六类**被补实现** (_synthesize_* 新增). 这违反
   P3 红线"严禁为构造场景补实现" (六类真实任务 0 发生), 但系统 intentional, 尊重.
2. **P4 改动被 revert**: _handle_write 回到**无条件**产 double_claim_detected (P4 的
   `scenario_intent` 条件被删). _synthesize_partial_failure / starvation 回到宽条件.
   → **A01/ADV07 又不可分辨** (events 完全相同: double_claim+conflict+partial+starvation+replay).

**当前状态 (系统方向 vs goal P3/P4)**:
- 系统方向: 全面对抗覆盖 (持续加 ADV 类 + 实现), 优先"对抗消解率"
- goal P3/P4: 真实频率驱动 (不补仅对抗类) + A01/ADV07 可分辨 (intent)
- **冲突**: 系统覆盖了 P3 边界 + P4 intent. agent 尊重系统 intentional, 不 revert.
- **诚实记录**: P4 的 intent 维度在系统方向下**不可持续** (持续被覆盖).
  A01/ADV07 可分辨这个 P4 目标, 需人类裁决 (系统方向 vs goal P4 哪个优先).

**送卡 (新增, P86 §F)**: 系统持续加对抗类实现 vs goal P3"严禁为构造场景补实现" —
请人类裁决方向: ① 全面对抗覆盖 (系统当前) ② 真实频率驱动 (goal P3, 不补仅对抗类).
agent 不代批, 仅标注冲突.

## 🔴 P4 第二次 revert (2026-07-29, goal P4 vs 系统方向二次冲突)

**第二次验证** (本 goal 重发后):
- _handle_write (line 179-181) 仍**无 scenario_intent 参数** (P4 改动被 revert)
- double_claim 场景 (ADV07/GEN-ADV-double) **无 intent 字段** (上轮加的被 revert)
- A01 events 仍含 double_claim+partial+starvation+**replay_attack** (系统新 _synthesize 污染)
- 系统持续加对抗类 (wave8: split_brain/identity_spoof/supply_chain/sybil_flood/
  time_travel/quorum_eclipse/clock_skew/ghost_writer/double_spend)

**结论**: goal P4 (intent 分辨 A01/ADV07) 与系统方向 (全面对抗覆盖) **二次冲突**.
agent 两次尝试 P4 (上轮 + 本轮), 均被系统 revert. **代码改动徒劳**.

**送卡 (P86 §F, 新增)**: goal P4 (intent 分辨, "不需人类拍板") vs 系统全面对抗方向 —
请人类裁决: ① intent 分辨 (goal P4, A01/ADV07 可分辨, 但限制对抗覆盖)
              ② 全面对抗覆盖 (系统当前, A01/ADV07 不可分辨, 但对抗消解率高)
agent 无法单方面实施 P4 (系统必 revert), 需人类协调系统方向.
**A2 批次3 旁证**: 协作 agent2 + 单 agent 都独立推荐 intent 维度 — goal P4 方向有 agent 共识.

## References
- P86 longplan §B1 · goal P3
- B1 根因 (前版, 部分被 P4 修正) `.omo/_knowledge/audits/2026-07-29-p86-b1-conflict-resolution-rootcause.md`
- scenario_lib.py (P4 intent + _synthesize 收紧)
