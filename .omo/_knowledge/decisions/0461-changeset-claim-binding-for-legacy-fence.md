---
schema: md/v1
status: PROPOSED
lifecycle: spec
owner: architecture-governance
last-reviewed: 2026-10-02
type: ssot
id: ADR-0461
related: ADR-0455, ADR-0459
tags: [claims-authority, legacy-publish-fence, changeset, bind, plumbing]
---

# ADR-0461 — changeset 侧携带 claim 绑定, 使 legacy publish fence 可被满足

- **Status**: PROPOSED（2026-10-02 提案；未实施）
- **Date**: 2026-10-02
- **Owner**: architecture-governance
- **Related**: ADR-0455（allow receipt 的可满足性，方案 A 已 ACCEPTED 且已实现）、
  ADR-0459（问题三④「发布栅栏不可诊断」，验收 5 已于 #4596 完成）

## 问题

claims authority 处于 `shadow-active` 时，`integrate` **强制**进入 legacy publish fence
（`bin/gac/clone-lifecycle.py:1594`）。该 fence 的第一行是：

```python
context = _legacy_fence_context(verification)   # 读 verification["claims_authority_fence_context"]
```

而该键**全仓只有这一个读取方，没有任何写入方**，于是必然抛
`LEGACY_FENCE_CONTEXT_UNAVAILABLE`。本机 `integrate --apply` 100% 停在这里。

## 关键澄清: 这不是"缺少授权", 是"缺少绑定"

`enter_legacy_publish_fence` 的流程是**先索要 context、再签发 fence**（同函数第 1386 行
调 `issue-legacy-fence`）。这看似鸡生蛋，但把 `issue_req` 的字段拆开看，
`context` 提供的 7 项在 integrate 之前**全部已知**：

| 字段 | 来源 |
|---|---|
| `claim_id` / `claim_version` / `lease_epoch` | claim |
| `v1_allow_receipt_digest` | ADR-0455 方案 A 的 publication-scoped allow 回执 |
| `v1_snapshot_digest` | snapshot 回执 |
| `changeset_digest` | changeset 自身 |
| `path_digest` | changeset 的 `changed_paths` |

**因此 context 不是授权，是绑定引用。** 真正的授权判定始终在 authority 侧：
`issue-legacy-fence` 会拿 `v1_allow_receipt_digest` 去核对真实 allow 回执
（ADR-0455 的 `_validate_publication_scoped_allow`），签不出就
`LEGACY_FENCE_ISSUANCE_CLOSED`。

**这推翻了"必须让 observation 投影承载授权"的说法。**
`build_claims_authority_shadow_projection()` 的契约
（*"never authority and never publication grant"*）**不需要被推翻** —— 本 ADR 不让投影
变成授权载体，只让 changeset 携带 claim 绑定。

## 备选

| 方案 | 描述 | 成本 | 风险 |
|---|---|---|---|
| **A. changeset 携带绑定（本 ADR 倾向）** | `verify-changeset` 在 `claim_verification` 已通过时，向 authority 查询并写入 `claims_authority_fence_binding`（claim 三元组 + 4 摘要 + `expected_remote_oid`） | 低-中 | 绑定摘要必须与 changeset 内容强绑定，防 scope 膨胀 |
| B. `enter_legacy_publish_fence` 自行向 authority 查询绑定 | 去掉对 verification 的依赖，函数内按 `agent_id` + changeset digest 反查 | 低 | 削弱"先有绑定再动"的可审计性；且需在函数内重跑 claim 校验 |
| C. 另立 `publisher` receipt 类 | fence 接受新回执类型 | 中高 | 与 ADR-0455 已否决的方案 B 同形，不重提 |
| D. authority 退回 `unactivated` | 使 fence seam 变 inert | 低 | **放弃整道防护**；且 `activation_state` 存于 SQLite `activation` 表，ADR-0455 forbidden 列表含 `no historical receipt mutation` |

## 倾向（供评审）

**方案 A**，理由：

- 不改任何 fail-closed 语义，只补管道缺失的那一环；
- 不让 observation 投影承担授权语义，ADR-0455 已建立的边界原样保留；
- authority 仍是唯一授权点，方案 B 把查询权下放给 integrate，与 ADR-0455
  "authority 独占判定" 的方向相反。

## 待定的两个设计点（评审必须先答）

1. **`expected_remote_oid` 的新鲜度**。fence 签发时会做双读并要求
   `observed_remote_oid == expected_remote_oid`，否则 `REMOTE_OID_DRIFT`。
   changeset 生成时读到的 OID 到 integrate 时可能已变。三个候选：
   (a) changeset 不带 OID，fence 现场读；(b) 带 OID 并接受"过期即要求重生成 changeset"；
   (c) 带 OID 但允许在 drift 时以新 OID 重新签发一次（**需明确防重放**）。
2. **绑定摘要的算子**。`path_digest` 必须覆盖 `changed_paths` 全集且有序规范化，
   否则同一 claim 可被复用于扩大后的变更集。需规定序列化形式与排序规则。

## 非目标

- 不改 ADR-0455 已实现的 publication-scoped allow 语义
- 不放宽 fail-closed：fence 仍必须签发成功才允许推送
- 不启用 instruction capability / 不把 v2 提升到 shadow 之上（ADR-0455 明列为非目标）
- 不改任何历史 receipt

## 执行门

1. 本 ADR → ACCEPTED（独立 human review），且第「待定的两个设计点」有明确结论
2. 实现 + focused tests：
   - RED：`claim_verification.all_covered` 为假时，**不得**写入绑定
   - RED：`path_digest` 不覆盖 `changed_paths` 全集时拒绝
   - GREEN：绑定齐备时 `issue-legacy-fence` 可签发并完成一次 canonical push
3. 在**有效**的授权窗口内重跑 `legacy-publication-regression`
   （前次 `DEC-20260923-CLAIMS-LIFECYCLE-R0-01` 已于 `2026-09-25T01:47:16Z` 到期）
4. 不得 force / `--no-verify` / 改历史 receipt / 改 authority 激活态

## 证据

- 消费方：`bin/gac/clone-lifecycle.py:1296`（`_legacy_fence_context`，唯一出现处）
- 签发方：同文件 `enter_legacy_publish_fence` 的 `issue-legacy-fence` 调用
- 投影契约：`bin/gac/agent-clone.py:3536`
  `build_claims_authority_shadow_projection` —— *"never authority and never publication grant"*
- 授权判定：`projects/omo/src/omo/workflow/claims_authority.py:440`
  `_validate_publication_scoped_allow`（ADR-0455 方案 A，已实现）
- 本机状态：`activation-witness.json` 存在、`activation` 表 `shadow-active`、
  authority 回执 `publishable: false` / `R0_COOPERATIVE`
- 管道说明：`docs/architecture/clone-lifecycle-pipeline-gates.md` 第 4 节

## 决策记录

- **2026-10-02**: 提案。核实过程中修正了先前判断——原以为需推翻 observation 投影的
  "never publication grant" 契约，实测 `issue_req` 的 7 项绑定在 integrate 前全部已知，
  context 是绑定引用而非授权，故 projection 契约无需改动。
