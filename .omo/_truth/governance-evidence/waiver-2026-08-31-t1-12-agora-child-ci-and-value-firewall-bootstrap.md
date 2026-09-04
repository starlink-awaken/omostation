---
schema_version: governance-waiver-evidence/v1
owner: human-principal
lifecycle: history
created: 2026-09-01
last_updated: 2026-09-01
value_indicator_policy: false
title: T1-12 Agora child CI and value-firewall bootstrap waiver
type: doc
---

# T1-12 Agora Child CI and Value-Firewall Bootstrap Waiver

## Principal response

```text
批准 v4 第11节原文。
```

The response approves Section 11 of
`/Users/xiamingxing/Documents/学习进化/基建架构/2026-08-31-蓝图目标回顾与执行规划修正版-v4.md`
in full. The approved document SHA-256 is
`843ced29099b3f66b963b6af4f4dad55de26a19328e224aa68f8086ca8825c96`.

## Human authorization — approved Section 11, verbatim

> 本次 BET-Y1Q3-T1-12 Agora child-native CI 与 value-firewall baseline bootstrap 跳过 workflow start，允许使用 `AGCP_REQUIREMENT_ITERATION_GATE=0`。不可变授权锚点为 #2846 merge `5869dc1cd97c73015b2b2b857c2d89f9ae11bfb6`、T1 normalized object SHA-256 `a08fcf6551f553543788fa8f9fe129692cb07ab9319eb7a66b9dbf1dc5eb7e4c`、Agora PR #54 historical base `c5c665e29f9146d0e52e91bd8aea91250653f630` 与 head `b1b3498a0f51e81891db8f203b586786ae8e1b1c`、accepted Spec 1.1.2 digest `sha256:41b7175076f14129b5e62989042f2f97d5f2b6ffb60cdd3a0ac9d60c27c0267a`；已验证 snapshot 为 root main/#2860 `4e4de1ffba8735d4aaa92b00ca2ae87b93397468`，其 Agora/bus-foundation/eCOS/family-hub gitlinks分别为 `f26038a35bed7a8be8ef57f1e875610d23417cb0`、`9968f05bff1d9c8e0e19b7841dae8f3d3dc881a2`、`cb42b985999285af798f1aecde2e61ff0e9536bd`、`ec96cd0602a101d126ddcc480f78c25838066111`。仅限 `docs/plans/3y-bet-ledger.yaml` 在 BET-Y1Q3-T1-12 恢复顶层 `value_indicator_policy: false` 并在既有 `write_surfaces` 仅追加 `projects/agora/.github/workflows/ci.yml`（87→88），以及 `.omo/_truth/governance-evidence/waiver-2026-08-31-t1-12-agora-child-ci-and-value-firewall-bootstrap.md` 记录本句、execution-time root snapshot、四项 gitlinks、语义差异与验证证据；bootstrap 阶段不得修改其他 T1 字段、其他 BET、Spec、completion/value evidence、实现代码、测试、registry、gitlink、CI、branch protection、workflow locks、运行态或用户配置，结果必须保持 T1 candidate、无 done_at、engineering IN_PROGRESS、operational/value NOT_PROVEN、overall evaluating。若执行时 root main 已前进，仅当 T1 object digest、87-surface shape、status/matrix、Spec digest、#54 head与bootstrap两路径仍精确匹配上述锚点时，才允许使用该 successor；从其 final tree读取四项 gitlinks作为 execution-time dependency snapshot，必须把三个 sibling SHA写成 child workflow literal refs并在该精确四仓组合上完成 isolated-HOME full gate，snapshot与结果写入 waiver/task report。任一 invariant或 gate失败即停止；child CI PR一旦创建，dependency snapshot冻结，后续 root pointer前进不静默改写该 PR，只在最终 root assembly或独立 dependency-bump PR重新验证。bootstrap root PR 合并且 exact-SHA post-merge Governance Check 全绿后，只有在 foreign T10-122 root-gate 不再被持有时才允许 fresh T1 workflow仅新增 Agora `.github/workflows/ci.yml`；本 waiver 不授权删除、heartbeat、closeout 或 takeover 其他 run/lock。child workflow 对 pull_request、main push 与 workflow_dispatch 触发，固定 `actions/checkout@11d5960a326750d5838078e36cf38b85af677262`、`actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065`、`astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e`，使用 Python 3.13、`uv sync --frozen --group dev --extra dev`、现有 `OMOSTATION_BOT_TOKEN` secret 名读取 execution-time pinned sibling refs，在 `workspace/projects/agora|bus-foundation|ecos|family-hub` 拓扑与 `${{ runner.temp }}/agora-ci-home` isolated parent HOME/XDG 下运行 full Ruff lint、changed-Python format check、5 个 exact bounded stdio probe 和完整 Agora pytest collection，仅允许 deselect 本文 §4.4 精确列明的 10 个 root-assembly node IDs；对 `f26038a + b1b3498` 与 family-hub `ec96cd06` 的 observed snapshot已安装 127 packages，默认 HOME 下唯一 focused失败已由无 probe 的 SSE-log变化直接证明为 live-host并发噪声，隔离 HOME后 focused 5/5且完整 gate得到 `1688 passed, 250 skipped, 10 deselected, 6 xfailed, 2 xpassed`，后续 recursive root assembly必须回放全部10个node IDs，不得整目录/整文件忽略或冒充全套通过。首个CI bootstrap PR因default branch尚无workflow，允许仅在 pinned actionlint、execution-time四仓 isolated-HOME复演与独立review通过后合并；其exact-SHA post-merge job `ci`必须成功，否则立即revert one-file CI PR。成功后仅允许执行 guarded required-status mutation：双读branch-protection无漂移、从唯一成功`ci` check读取实际Actions `app_id`、仅PATCH `required_status_checks`子资源为`strict=true`与app-bound `ci`、完整readback证明enforce_admins与其他保护不变，并保留DELETE同子资源的snapshot-A rollback；任何404、schema、app-id cardinality或readback异常均停止。随后只允许关闭并重开#54一次，使GitHub丢弃仍基于旧base的cached merge ref；新PR event必须证明base/head/synthetic-merge三元身份、第一父为执行时current Agora main、第二父为exact head `b1b3498a0f51e81891db8f203b586786ae8e1b1c`，CI条件步骤必须用merge-base/triple-dot证明exact两文件和no `tools/call`。#54仅在app-bound `ci`成功后squash merge；记录pre-merge child main `C0`与merge SHA `M54`，要求`M54^=C0`、`C0..M54`仅两路径、PR head与`M54`在两路径上内容等价，并要求`M54` exact-SHA post-merge `ci` success。不得修改#54文件、放宽4秒/64 KiB/invalid JSON/cleanup/零残留边界、伪造status、发送`tools/call`、调用任何MCP tool、写completion/value evidence或将T1标done；root后续的gitlink写入只能把`projects/agora`精确推进到`M54`，仅完整树零diff后继可替代；既有十路径root loader implementation不由本bootstrap waiver新增授权，必须复用accepted Spec 1.1.2、既有十路径WorkPacket write surfaces与fresh canonical workflow，从执行时current root main逐任务重建RED→GREEN，不得cherry-pick/replay历史`99d9086...5dd180c`range，path#9 RED/path#6 legacy façade retirement仍为强制项，任何第11个root implementation path都必须重新书面授权。
>
> 为避免持久化顺序歧义：上文的 waiver snapshot 仅指 Task1 root bootstrap 提交时已观察的 initial snapshot；若 Task2 捕获的 execution-time `R` 不同，replacement snapshot与full-gate结果只允许进入bounded Task2 report和CI PR evidence，不得修改或重开已合并的ledger、waiver或任何root file。除§4.7在replacement full gate通过后授权的三组 sibling literal `ref`及其匹配assertion替换外，one-file child workflow只允许actionlint/GitHub Actions schema要求的syntax-level调整。

## Bootstrap execution identity

- Workflow run: none; the principal explicitly authorized skipping workflow start for this exact bootstrap.
- Requirement gate override: `AGCP_REQUIREMENT_ITERATION_GATE=0`, limited to the exact two root files below.
- Agent: `blueprint-exact-capability-mcp-load`.
- Delivery attempt: `t1-12-agora-child-ci-value-firewall-bootstrap-20260901-09`.
- Initial observed root main / clone HEAD: `4e4de1ffba8735d4aaa92b00ca2ae87b93397468`.
- Admitted successor root main for the final bootstrap parent: `5b5cedf9a6fbfce70e3f888b1be04c41baf2e0e0`. Its T1 normalized object SHA-256, 87-surface shape, protected status/matrix, accepted Spec digest, PR #54 immutable head, bootstrap-path availability, and four gitlinks all match the approved anchors; the successor adds only the unrelated WP-P3 pass-through report relative to the initial snapshot.
- T1 normalized object SHA-256 before mutation: `a08fcf6551f553543788fa8f9fe129692cb07ab9319eb7a66b9dbf1dc5eb7e4c`.
- Accepted Spec 1.1.2 SHA-256: `41b7175076f14129b5e62989042f2f97d5f2b6ffb60cdd3a0ac9d60c27c0267a`.
- Agora PR #54 historical base / immutable head: `c5c665e29f9146d0e52e91bd8aea91250653f630` / `b1b3498a0f51e81891db8f203b586786ae8e1b1c`.
- Execution-time gitlinks:
  - `projects/agora`: `f26038a35bed7a8be8ef57f1e875610d23417cb0`
  - `projects/bus-foundation`: `9968f05bff1d9c8e0e19b7841dae8f3d3dc881a2`
  - `projects/ecos`: `cb42b985999285af798f1aecde2e61ff0e9536bd`
  - `projects/family-hub`: `ec96cd0602a101d126ddcc480f78c25838066111`

## Exact bootstrap scope and resulting truth

This bootstrap changes exactly:

- `docs/plans/3y-bet-ledger.yaml`: add top-level `value_indicator_policy: false` to BET-Y1Q3-T1-12 and append one unique write surface, `projects/agora/.github/workflows/ci.yml` (87 to 88);
- this waiver evidence file.

All non-T1 BET objects and all other T1 fields remain unchanged. T1 remains `candidate`, has no `done_at`, records engineering `IN_PROGRESS`, operational/value `NOT_PROVEN`, and overall `evaluating`.

## Bootstrap validation evidence

- RED: before either authorized mutation, the bounded semantic assertion exited `1` because BET-Y1Q3-T1-12 did not contain the required top-level `value_indicator_policy: false`; the baseline contained 87 unique write surfaces while the protected status and completion-matrix invariants already matched the approved anchors.
- GREEN: after the two authorized ledger mutations, the same bounded semantic comparison exited `0`; every non-T1 BET object is byte-semantically equal to the immutable base object, the T1 object differs only by `value_indicator_policy: false` and the single unique CI write surface (87 to 88), and its resulting normalized SHA-256 is `988852cceab7957ce8d53e3b65acb9bcb5309968e7cb7c70958f30f27670c538`.
- Ledger lint: `OK -- 274 bets, 11 tracks, no errors`.
- Accepted-Spec binding regression: `tests/test_spec_binding_lint.py` completed with `71 passed`.
- SSOT guardian: `PASS`.
- File-scoped GaC: both authorized paths returned `ok=true` with zero hard failures under Python 3.13 plus PyYAML and Pydantic; only the pre-existing soft warnings `ci-surfaces-check` and `command-discovery` remained.
- Full local GaC, with the principal-authorized requirement-gate override limited to this bootstrap, completed `PASS (56 checks executed, ALL GREEN)`; six checks reported by the harness as known unavailable were skipped rather than represented as executed.
- Git hygiene: `git diff --check` passed, the working-tree diff contains exactly the authorized ledger path plus this waiver, and no files were staged during validation.

## Prohibitions and residual work

This bootstrap does not modify implementation, tests, generated registries, gitlinks, CI, branch protection, workflow locks, runtime state, user configuration, completion evidence, or value evidence. It does not authorize deleting, heartbeating, closing, or taking over another run or lock; it does not send `tools/call` or invoke an MCP tool; and it does not mark T1 done.

Child CI implementation, dependency-snapshot replacement evidence, required-status mutation, PR #54 merge, root loader rebuild, native canary, and final closeout remain later governed tasks subject to the approved Section 11 stop conditions.
