---
schema_version: governance-waiver-evidence/v1
owner: human-principal
lifecycle: history
created: 2026-08-31
last_updated: 2026-08-31
value_indicator_policy: false
title: T1-12 PR 2819 truth recovery and Agora clean-stdio scope waiver
type: doc
---

# T1-12 PR #2819 Truth Recovery and Agora Clean-stdio Scope Waiver

## Principal response

```text
全面批准
```

The response approves Section 8 of
`/Users/xiamingxing/Documents/学习进化/基建架构/2026-08-31-t1-12-agora-stdio-clean-boot-scope-amendment-proposal.md`
in full. The proposal SHA-256 is
`3b52f8fe3669f2c26810c30610e86b663d673089fae605acb9eecd7d21d6756b`.

## Human authorization — proposal Section 8, verbatim

```text
本次 #2819 BET-Y1Q3-T1-12 premature completion truth recovery 与 Agora clean-stdio child scope amendment 自举跳过 workflow start，允许使用 `AGCP_REQUIREMENT_ITERATION_GATE=0`；fixed refs 为 root remote main `b8a3b2456c66ab44221a1c5238be50f64e42bb58`（已证明其 T1-12 对象与独立审计的 `82c71cfe90463cc83a2351d0fabf111904f91970` 相同）、#2819 merge `763ce75646424d6d46cd3c8071d3e47f9d257f07`、其 merge parent `41ed24fe999a6acf1cfd41505ac74974acd3ce54`、保留在独立 clone 且 canary blocked 的 reviewed root implementation range `99d9086a092c5e9644ef9c54ad42d5f5c826f268..5dd180cea742ec46caf1dcbf9005440692d32607`、root Agora gitlink `0f188fa3cf697bd18c0da08c46089731ffe030f8`、Agora child main `c5c665e29f9146d0e52e91bd8aea91250653f630`、accepted Spec 1.1.2 digest `sha256:41b7175076f14129b5e62989042f2f97d5f2b6ffb60cdd3a0ac9d60c27c0267a`、stdio diagnostic artifact `/Users/xiamingxing/Documents/学习进化/基建架构/evidence/2026-08-31-t1-12-agora-stdio-diagnostic.json` digest `sha256:82998951522912dde77133525cb4a9b6522a1d7522380740fcfbcad15a3a9cc0`；bootstrap 仅限 `docs/plans/3y-bet-ledger.yaml` 将 BET-Y1Q3-T1-12 完整条目恢复为 #2819 merge parent 真值并仅追加 `projects/agora/src/agora/server/mcp.py` 与 `projects/agora/tests/test_mcp_stdio_inventory_probe.py` 两个顶层 write surfaces（85→87），以及 `.omo/_truth/governance-evidence/waiver-2026-08-31-pr2819-t1-12-agora-clean-boot-scope-recovery.md` 记录本句与 fixed-ref/canary 证据；不得修改其他 BET、Spec、capability requirements、既有 historical evidence、实现代码、测试、registry、gitlink、CI、branch protection、运行态或用户配置，结果必须为 T1 candidate、无 done_at、engineering IN_PROGRESS、operational/value NOT_PROVEN、overall evaluating。bootstrap 唯一 PR 合并且 exact-SHA post-merge Governance Check 全绿后，授权 child-first 实现仅修改 Agora 子仓 `src/agora/server/mcp.py` 与 `tests/test_mcp_stdio_inventory_probe.py`，以固定私有 `AGORA_MCP_INVENTORY_PROBE=1` 在 Agora subsystem import 前收敛 stdlib logging/structlog，正常模式不得改变，并以 exact `python -m agora.server.mcp` 完整验证 `initialize -> notifications/initialized -> tools/list` 的全程 JSON-only stdout、ID 1/2、4 秒总预算、64 KiB stderr cap、temp-only 写入与零进程残留；child commit/tag/唯一 PR/CI/merge/post-merge 全绿后，才允许 fresh root workflow 在首先证明上述 retained commit range 可解析、祖先链/commit list/diff/路径与既有 review 一致后重放十路径实现，仅在 `lib/capability_mcp_server_load.py`/`tests/test_capability_sync.py` 增加固定内部 FastMCP/Agora probe 环境，并仅推进 `projects/agora` gitlink 到 merged child-main 后继。不得放宽 deadline、stderr cap、invalid JSON fail-closed、persisted verification-before-spawn、cleanup/no-residue、无 caller override/alternate argv/fallback/第二 registry-dispatcher 边界，不得发送 `tools/call` 或调用任何 MCP tool；真实 native canary 必须证明 JSON-only stdout、digest-only receipt、`~/.agora` 不变、零进程残留后方可提交最终 root PR，但仍不得写 completion/value evidence 或将 T1 标 done。若 child 已合并但 root canary 失败，保留正常模式不变的 child merge并禁止 root gitlink/PR 前进；若 root PR 合并后 exact-SHA post-merge 失败，停止 closeout并以新 PR revert root implementation/gitlink，不得 revert truth recovery 或删除 waiver/blocked-run evidence；执行时若 root/child main 非上述 ref 或逐路径证明的等价后继，必须先重审，不得静默吸收并发变更。
```

## Bootstrap execution identity and fixed refs

- Workflow run: none; the principal explicitly approved skipping workflow
  start for this exact bootstrap.
- Requirement gate: `AGCP_REQUIREMENT_ITERATION_GATE=0` is authorized only
  for this bounded bootstrap.
- Latest equivalent execution base and clone `HEAD`:
  `bdfa420f7286d54a0c086a57420a45befe2769ad`.
- Proposal-observed root main:
  `b8a3b2456c66ab44221a1c5238be50f64e42bb58`.
- Independently audited predecessor:
  `82c71cfe90463cc83a2351d0fabf111904f91970`.
- PR #2819 merge:
  `763ce75646424d6d46cd3c8071d3e47f9d257f07`.
- Immutable PR #2819 merge parent and truth source:
  `41ed24fe999a6acf1cfd41505ac74974acd3ce54`.
- Reviewed blocked root implementation range:
  `99d9086a092c5e9644ef9c54ad42d5f5c826f268..5dd180cea742ec46caf1dcbf9005440692d32607`.
- Root Agora gitlink:
  `0f188fa3cf697bd18c0da08c46089731ffe030f8`.
- Agora child main:
  `c5c665e29f9146d0e52e91bd8aea91250653f630`.
- Accepted Spec 1.1.2 digest:
  `sha256:41b7175076f14129b5e62989042f2f97d5f2b6ffb60cdd3a0ac9d60c27c0267a`.
- Durable diagnostic artifact:
  `/Users/xiamingxing/Documents/学习进化/基建架构/evidence/2026-08-31-t1-12-agora-stdio-diagnostic.json`.
- Independently read diagnostic SHA-256:
  `82998951522912dde77133525cb4a9b6522a1d7522380740fcfbcad15a3a9cc0`.

The T1-12 object at the latest equivalent execution base is semantically
identical to the object at `b8a3b245...`, `82c71cfe...`, and the #2819 merge.
Therefore `bdfa420f...` is an equivalent successor for this exact bootstrap;
the immutable parent remains the restoration source.

## Truth rationale

PR #2819 promoted T1-12 from `candidate` to `done`, added `done_at`, changed
engineering from `IN_PROGRESS` to `VERIFIED`, changed operational from
`NOT_PROVEN` to `PROVEN`, and changed the overall state from `evaluating` to
`delivery_accepted`. Those promotions are contradicted by the retained
evidence: the earlier canary report says the positive gateway run was pending,
the later binding canary targeted `bos-service:bos://system/omo/debt` rather
than `mcp-server:agora/load/read_only`, and the retrospective preserves the
principal ruling that tests are not operational proof.

The durable 2026-08-31 diagnostic reached the real Agora child after persisted
admission, but the exact root load failed closed with `mcp_initialize_failed`.
The exact child command answered initialize and tools/list while emitting 22
non-JSON stdout lines and 126,734 stderr bytes; the no-write alternate-argv
diagnostic emitted zero non-JSON stdout lines and 385 stderr bytes while
preserving the same 104-tool inventory digest
`sha256:69d6598c5de6d6fdcb9639647df0c68326cd676b6090e2cdd410a59490461533`.
That alternate argv is diagnostic only and is not delivery evidence. The
failure proves that current native MCP load remains incomplete, so the
pre-#2819 parent object is the authoritative ledger truth.

## Exact bootstrap scope and resulting truth

This bootstrap changes exactly:

- `docs/plans/3y-bet-ledger.yaml`, restoring the complete T1-12 object from
  `41ed24fe...` and appending only
  `projects/agora/src/agora/server/mcp.py` and
  `projects/agora/tests/test_mcp_stdio_inventory_probe.py` to the top-level
  `write_surfaces` list;
- this waiver evidence file.

The restored parent object had 85 unique top-level write surfaces; the two
authorized additions yield exactly 87 unique surfaces. The resulting state is
`candidate`, has no `done_at`, records engineering `IN_PROGRESS`, operational
and value `NOT_PROVEN`, and overall `evaluating`. All other T1-12 semantics are
the immutable parent semantics.

No other BET, top-level ledger key, Spec, capability requirement, historical
evidence, implementation, test, registry, gitlink, CI, branch protection,
runtime state, or user configuration is authorized to change. This waiver
does not prove operational delivery or value and does not authorize a status
promotion, an MCP tool call, `tools/call`, alternate argv, fallback execution,
or a second registry/dispatcher.
