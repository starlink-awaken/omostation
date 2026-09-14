---
id: ADR-0235
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last-reviewed: 2026-07-25
related:
  - 0230-agent-registry-node-role-capability.md
  - STRAT-P81-strategic-roadmap.md
supersedes: []
amends: []
type: ssot
---

# ADR-0235: ROLE_CATALOG C1 扩展 — research/delivery 第二波角色

## Context

STRAT-P81 Batch3 C1 要求角色广度 3→5（research/delivery 正式实装）。
Batch2 B3 eval 页（`audits/2026-07-24-batch2-role-expansion-eval.md`）已画清边界：

| Role | 价值 | 边界 | 风险 |
|------|------|------|------|
| research | KOS 检索/文献合成 | 只读知识面; 不可 claim 代码 | 幻觉污染 SSOT |
| delivery | 交付卡/X3 冲刺登记 | 只写 delivery/X3 投影; 无代码写权 | 凑数（已禁）|

交接单 §F.4：第 **6+** 角色才需人类拍板，C1 到 5 为止在授权内。

## Decision

1. **扩展 `bin/_archive/2026-08-conv3/role_framework.py::ROLE_CATALOG`** 加两个 RoleSpec：
   - **research**: capabilities=(read-evidence, search-kos, synthesize-knowledge)；
     can_send=(research_result, progress, block)；can_recv=(assign, research_request, verify_result)；
     private_scope_prefix=private.research；legacy=researcher
   - **delivery**: capabilities=(register-delivery, write-x3-projection, closeout-delivery)；
     can_send=(delivery_registered, progress, block)；can_recv=(assign, delivery_request, complete)；
     private_scope_prefix=private.delivery；legacy=deliverer
2. **governance 扩展 dispatch 能力**：加 dispatch-research/dispatch-delivery + research_request/delivery_request (can_send) + research_result/delivery_registered (can_recv)。不破坏现有 assign→claim_ack→handoff→verify→complete 三角色协议。
3. **边界 enforce（eval 页红线）**：research/delivery 均无 write-code/claim-path；`RoleProtocolBus.publish` enforce can_send/can_recv（越界 raise PermissionError）。
4. **常量分组**：`SECOND_WAVE_ROLES=(research, delivery)`；`ALL_ROLES=FIRST_SHIP_ROLES+SECOND_WAVE_ROLES`；`LEGACY_ROLE_MAP` 补 researcher/deliverer。
5. **x3-role-metrics 投影**：暂不加 0% 占位（避免拉低 BRIEF 显示）；等 ≥15 任务试点有真实数据再投影。
6. **试点门槛**：验收要求 ≥15 真实任务对照 3 角色基线，数据入 audits（后续轮推进）。

## Confirmation

- 5 角色可实例化（`RoleRegistry.register(ALL_ROLES)`）
- 协议消息通：gov↔research (research_request/result)，gov↔delivery (delivery_request/registered)
- 边界 enforce：research/delivery 无 write-code/claim-path；research 不能 send assign (PermissionError)
- 回归保护：`run_three_role_handshake` 仍 completed=True（3 角色协议不破坏）
- `tests/test_role_framework_c1.py` **8 tests pass**

## Status

**ACCEPTED** for Batch3 C1 role catalog extension (2026-07-25)。试点对照数据待 ≥15 任务跑满后入 audits。
