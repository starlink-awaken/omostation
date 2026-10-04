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

- **Status**: PROPOSED（2026-10-02 提案；2026-10-03 实施前发现 authority 无读动词，方案 A 前提不成立，待裁定；未实施）
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

## 2026-10-02 溯源结论：两个设计点均已有答案，无需新发明

实施前对两个设计点各做一轮溯源（查 ADR / pitfalls / 已合并代码），结论是
**两者都已有既定契约，本 ADR 只需复用，不需新设计**。

### 设计点 1：`expected_remote_oid` —— **不由 changeset 携带**

fence 在签发时**已经做现场新鲜双读**：`build_remote_observation_pair()` 取两次独立观测，
任一字段不一致即 `REMOTE_OID_DRIFT`（`clone-lifecycle.py:1278-1290`），并校验
`second.monotonic_ns >= first.monotonic_ns`。这已经是该机制自己的抗漂移手段。

`expected_remote_oid` 是第三道**跨检**，而它来自调用方（若由 changeset 携带则必然
可能陈旧）。换言之，`_legacy_fence_context` 要求调用方提供 callee 随后自己重算的量 ——
**这本身就是契约设计问题，而非缺失能力**。

> **2026-10-03 更正**：本条早前结论「fence context **不带** `expected_remote_oid`」**有误**。
> 现场双读只保证**两次读之间**没动（`build_remote_observation_pair` 内部两观测逐字段比对），
> **不保证 changeset 生成到 integrate 之间没动** —— 那是 TOCTOU 防护。去掉期望值后，
> fence 会接受一个在期间被别人创建的 remote ref，正是 `delivery_attempt_reused`
> （`clone-lifecycle.py:1686`）要防的场景。
>
> 且该字段**不是**「分支在哪」而是「推之前该 ref 应处于什么状态」：
> `build_remote_observation_pair` 在 ref 不存在时取哨兵 `_ABSENT_REMOTE_OID = "0"*40`，
> 而 validate 处 `re.fullmatch(r"[0-9a-f]{40}")` 接受它。integrate 首次推送 delivery
> 分支时远端该 ref 尚不存在，故 `expected_remote_oid` 正常取值就是哨兵 —— **不是陈旧值**。
>
> **更正结论**：`expected_remote_oid` 应当携带，由 changeset 阶段观察并写入。

> 顺带：`gh_json`（`#4596` 修）与本 ADR 的起因 `claims_authority_fence_context`
> 确属"契约已定义并强制、但生产侧无生产者"的形状，值得在实现时以 lint 形式确认
> authority 必填字段都有生产者。**但不要把这条推论套到 `requested_paths_digest`
> 上——它是有生产者的**，见下节更正。

### 设计点 2：`path_digest` 的算子 —— **复用 ADR-0455 已强制的公式**

`_validate_publication_scoped_allow()`（ADR-0455 方案 A，已在生产并被测试覆盖）已写死：

```python
# production uses canonical_digest({"paths": sorted, "surfaces": sorted})
if scope.get("paths_digest") != request.get("requested_paths_digest"):
    raise AuthorityError("CLAIM_SCOPE_VIOLATION", "publication_scope_bound")
```

配套约束同样已强制：`changed_paths` 非空、元素为非绝对路径字符串、无重复；
`canonical_digest(v) = "sha256:" + sha256(canonical_json(v))`。

**数据源与算子都已在生产中就位**（2026-10-02 更正）。claim 记录本身存 `paths` 与
`surfaces`，而 `projects/omo/src/omo/workflow/lifecycle.py:480` 在构造
`observe-claim` envelope 时**已经计算**了它：

```python
"requested_paths_digest": _authority_digest(
    {
        "paths": sorted(str(item) for item in claim.get("paths", [])),
        "surfaces": sorted(str(item) for item in claim.get("surfaces", [])),
    }
)
```

这正是 ADR-0455 注释所述的公式。且两个 digest 函数对该载荷产出**同一个值**（实测）：

```
lifecycle._authority_digest : sha256:afa31c8ee794a0cd4c91cea7a9e3a2368f413607ea924364ab9e109aded6a58f
claims.canonical_digest    : sha256:afa31c8ee794a0cd4c91cea7a9e3a2368f413607ea924364ab9e109aded6a58f
同值: True
```

因此 fence context 的 `path_digest` **不需要新算、不需要新规范化规则**：直接沿用
observe-claim 请求里已算好的 `requested_paths_digest`。实现时保证两者是**同一个值**
——authority 侧 `_validate_publication_scoped_allow` 会校验
`paths_digest == requested_paths_digest`，不一致即 `CLAIM_SCOPE_VIOLATION`。

> **更正**：本 ADR 早前版本称「`requested_paths_digest` 只出现在校验器、桥测试，
> 以及没有任何生产代码计算它」。**该判断有误** —— 是 grep 输出被 `head` 截断所致。
> 生产者一直存在于 `lifecycle.py:480`。此更正同时把设计点 2 从「需定算子」收窄为
> 「沿用既有值」。

### 2026-10-03 实施前发现：方案 A 的前提不成立

原写「`verify-changeset` 在 `claim_verification` 已通过时，**向 authority 查询**并写入
`claims_authority_fence_context`」。核实后：**authority 没有任何能返回该绑定的读动词。**

`issue-legacy-fence` 的校验要求（`claims_authority.py:2627-2643`）：

| 字段 | 实际来源 |
|---|---|
| `claim_id` / `claim_version` / `lease_epoch` / `v1_snapshot_digest` | authority 库 `claims` 表（`observe-claim` 写入） |
| `v1_allow_receipt_digest` | authority 库 `receipts` 表中 observe-claim 回执的摘要 |
| `path_digest` | 该回执的 `publication_scope.paths_digest` |

而：
- claim 记录（`runs/<run>.yaml`）只存 `actor` / `claimed_at` / `paths`，**不含**上述任一项；
- `_DISPATCH_METHODS` 的全部动词为 `status` / `observe-claim` / `begin|settle-claim-mutation`
  / `activate-shadow` / `issue|enter|settle-legacy-*` / `evaluate-graduation`，
  **没有任何只读动词**能取出 claim 绑定。

因此方案 A 实际需要一个**新增的 authority 读动词**（如 `describe-claim`）。这不是管道
接线，而是**给安全边界加一个新能力**，且自带待决问题：谁能读绑定？读取是否需要 operator
授权？是否泄漏 claim 存在性？它一旦可读，任何能触达 authority 的调用方就具备了满足
fence 所需的全部材料。

**故本 ADR 的实现门必须先回答这一条**，否则方案 A/B 都无法落地。

### 由此收窄的执行门

原执行门第 1 条要求"上述两点有明确结论"——**该条件现已满足**，可进入第 2 条
（实现 + focused tests）。

## 非目标

- 不改 ADR-0455 已实现的 publication-scoped allow 语义
- 不放宽 fail-closed：fence 仍必须签发成功才允许推送
- 不启用 instruction capability / 不把 v2 提升到 shadow 之上（ADR-0455 明列为非目标）
- 不改任何历史 receipt

## 实施计划（2026-10-04 增补，PROPOSED，未实施）

读动词 `describe-claim` 已交付（`omostation-omo#206` / `c909bd6fc`，父仓指针
`#4615` / `0a63b4969`）。但它**只是让绑定可被读出**——要真正让
`integrate --apply` 跑通，还差一条从 claim 到 changeset 的传导链。

实测：`bin/gac/agent-clone.py` 中 `claim_id` 出现 **0 次**。changeset 当前只带
`claim_verification`（`all_covered` / `enabled` / `claimed_paths` /
`authority_binding`），**不携带任何 claim 身份**；而 claim 记录
（`runs/<run>.yaml`）也只存 `actor` / `claimed_at` / `paths` / `scopes` /
`locks` / `affected_graph`。

故剩余工作不是一步，而是**四处有严格先后依赖的改动，跨两个仓，全部在安全边界上**：

| # | 改动 | 位置 | 前置 |
|---|---|---|---|
| 1 | `lifecycle.py` 建 claim 时把 `claim_id`（连同 `claim_version` / `lease_epoch`）持久化进 claim 记录 | `projects/omo` | — |
| 2 | `changeset` 从 claim 记录读取并记录 `claim_id` | `bin/gac/agent-clone.py` | 1 |
| 3 | `verify-changeset` 用 `claim_id` 调 `describe-claim`，把绑定写进 `claims_authority_fence_context` | `bin/gac/agent-clone.py` | 2 |
| 4 | changeset 阶段观察远端 delivery ref，得出 `expected_remote_oid` | `bin/gac/agent-clone.py` | 3 |

### 每步的验证契约

- **1**：`claim` 记录出现 `claim_id` 且与 `describe-claim` 返回的一致；既有读者
  （`bin/agent-workflow.py`、`swarm_discipline`、`panorama-collect` 等）不受影响
  —— 均为加法式字段
- **2**：`change_id` 的计算输入**不得**包含 `claim_id`，否则同内容 changeset 的
  标识会随 claim 漂移（既有注释已声明 `claims_authority_shadow` 不得进 `change_id`
  权威，同理适用）
- **3**：RED —— `claim_verification.all_covered` 为假时**不得**写入绑定；
  GREEN —— 绑定齐备时 `issue-legacy-fence` 可签发并完成一次 canonical push
- **4**：RED —— ref 状态在两次观察间变化时拒发；GREEN —— 稳定时带哨兵
  `_ABSENT_REMOTE_OID` 正常发

### 排期理由

四步有严格拓扑序，任一步未验证就推进会把"看起来对、实际必然失败"的中间态
写进主线。建议作为**一个实施批次**推进，每步独立 RED/GREEN，而不是零散提交。

### 前置条件（不因实施而改变）

即便 1–4 全部完成，**端到端 `integrate --apply` 仍需 principal 签发新的授权窗口**
（前次 `DEC-20260923-CLAIMS-LIFECYCLE-R0-01` 已于 `2026-09-25T01:47:16Z` 到期）。
实施只能解除"绑定不可得"这一结构性阻塞，不能替代授权。

## 执行门

1. 本 ADR → ACCEPTED（独立 human review），且**「是否新增 authority 读动词」有明确结论**（见「实施前发现」）
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
- **2026-10-02（第二次）**: 对两个设计点做溯源，结论均复用既有契约 ——
  `expected_remote_oid` 不由 changeset 携带（fence 已有现场双读抗漂移），
  `path_digest` 沿用 `lifecycle.py:480` 已算好的 `requested_paths_digest`。
  未决项收窄为「绑定由 changeset 计算还是由 fence 反查」。
- **2026-10-02（第三次, 更正）**: 撤回「`requested_paths_digest` 无生产者」的错误
  判断(grep 被 `head` 截断所致), 并补实测: `lifecycle._authority_digest` 与
  `canonical_digest` 对该载荷同值, 故 fence 可直接沿用。
