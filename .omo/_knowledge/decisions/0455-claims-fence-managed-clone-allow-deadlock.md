---
id: ADR-0455
status: ACCEPTED
lifecycle: spec
owner: architecture-governance
last-reviewed: 2026-09-24
type: ssot
related:
  - ADR-0453
  - PITFALL-GAT-010
---

# ADR-0455 — Claims legacy-publication fence 与 managed-clone allow 禁止的可满足性

- **Status**: ACCEPTED（2026-09-24 principal 批准方案 A；授权实现 publication-scoped allow）
- **Date**: 2026-09-23
- **Owner**: architecture-governance
- **Related**: Claims Authority WP1 lifecycle draft `07d655de…7682`；PITFALL-GAT-010；BET-Y1Q4-T10-145

## 问题

生产 Claims Authority 上，**同一 canonical interface** 同时要求：

1. **Op B/C fence 前置**：`issue_legacy_fence` 要求 `v1_allow_receipt_digest`
   指向 `effective_v1.decision == allow` 的 `observe-claim` 回执。
2. **Op A/B observe 校验**：`clone_identity_schema == agent-clone-identity/v2`
   （全部 attempt clone）时，`v1_decision=allow` → `V1_AUTHORITY_FORBIDDEN(managed_clone)`。

attempt 路径恒为 `agents/<actor>/attempts/<attempt>/ws` 且 identity schema 由
创建工具固定为 v2 → **无法铸造 allow receipt** → fence 不可发 → 已批准的
lifecycle Op B/C 无法完成（2026-09-23 执行实证：Op A 成功，B/C stop）。

## 备选

| 方案 | 描述 | 成本 | 风险 |
|------|------|------|------|
| **A. 专用 legacy-publication observe** | 在 v2 attempt 上允许一条仅绑定 exact `changed_paths` + fence 效果上限的 allow 分支；仍禁止任意 allow | 中 | 需严格 path/changeset 绑定，防 scope 膨胀 |
| **B. Publisher receipt** | fence 接受新 `publish-allow` 类回执（非 managed-clone observe），仍强制 fence/双读/一次性 push | 中高 | 新 receipt 类要进 graduation 证据映射 |
| **C. 非 attempt v1 拓扑** | legacy publication 放到非 attempts 布局（identity v1） | 高 | 与 current production path 校验、onboard 工具链冲突 |

## 倾向（供评审）

**方案 A**，理由：

- 不引入新 receipt 语义，保持 graduation 三类证据结构；
- 与 Op A 的 `expected_managed_clone_difference` 并存：v2 禁止「通用 allow」，
  只开放「绑定 publication 范围的 allow」；
- 效果上限仍由 draft 已批的一次 push/PR/squash 承载。

## 非目标

- 启用 instruction capability / v2 高于 shadow（仍需独立授权）
- 在本 ADR PROPOSED 状态下修改 `claims_authority.py`

## 执行门

1. ADR → ACCEPTED（独立 human review）
2. 实现 + focused tests（RED：通用 allow 仍拒；GREEN：绑定 publication 的 allow 可 fence）
3. 使用仍有效的 `DEC-20260923-CLAIMS-LIFECYCLE-R0-01` 窗口或续期授权，重跑 Op B/C
4. 不得 force / `--no-verify` / 改历史 receipt

## 证据

- 授权：`~/.local/share/zhixing-dashboard/claims-observation/lifecycle-human-approval.json`
- 执行状态：`.../lifecycle-execution-status.json`（Op A EXECUTED，B BLOCKED_PROTOCOL）
- PITFALL：`.omo/_knowledge/pitfalls/gate/PITFALL-GAT-010.yaml`
- 源码：`projects/omo/src/omo/workflow/claims_authority.py`（`_validate_observe_request` / `issue_legacy_fence`）

## 决策记录

- **2026-09-24**: principal 批准 ADR-0455 方案 A。允许在 `agent-clone-identity/v2` 上铸造
  **绑定 exact `changed_paths` + 单次 fence 效果上限** 的 `v1 allow` observe receipt；
  通用 allow 仍禁。实现后在有效授权窗 `DEC-20260923-CLAIMS-LIFECYCLE-R0-01`
  （至 2026-09-25T01:47:16Z）内重跑 Op B/C。
