---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-31
last_updated: 2026-08-31
title: BET-Y1Q3-T1-12 MCP-load current-main scope convergence waiver
type: doc
value_indicator_policy: false
---

# BET-Y1Q3-T1-12 MCP-load current-main scope convergence waiver

waiver: user-explicit
when: 2026-08-31
who: xiamingxing
quote: "给你全部授权"
approved_package: /Users/xiamingxing/Documents/学习进化/基建架构/2026-08-31-post2796-concurrency-drift-recovery-authorization-package.md
approved_package_sha256: 196807240f6e5b5835f258e64451b968592b20f2a2ed33d8ff8c5237f58678b3
approved_section: 4
gate_bypass: 1
no-run-id: true
value_indicator_policy: false

## Exact authorization

> 本次 BET-Y1Q3-T1-12 current-main prerequisite recovery 与 MCP-load scope convergence 按两个串行唯一 PR 执行，均允许使用 `AGCP_REQUIREMENT_ITERATION_GATE=0` 且不得新建平行 verifier/dispatcher/registry。第一 PR 只允许两条 root path：`projects/omo` 从 root current pointer `ee2d697898837170d8d63fca4bddf315c37c5473` 前进到 authoritative child main `bf8e34c23439dfb65b2c34bbac9e0b8178786282` 或其包含 `95e7b28beeb62b3c94d8151095ef4194304f7044`、child CI 全绿且经逐路径审计的 main 后继，以及 `.omo/_truth/governance-evidence/waiver-2026-08-31-t1-12-omo-pointer-recovery.md` 记录本句、#124 admission、root regression、child ancestry、child CI run `33334462006`（`https://github.com/starlink-awaken/omostation-omo/actions/runs/33334462006`）与 14/14 require-main 证据；第一 PR 不得修改 child repository 内容、其他 root 文件、其他 gitlink、BET、Spec、代码、测试、registry、CI、运行态或用户配置，full recursive checkout、required CI、exact-SHA post-merge Governance Check 全绿后退役 pointer clone。第一 PR 完成 post-merge readback 后，第二 PR 只允许 `docs/plans/3y-bet-ledger.yaml` 在 BET-Y1Q3-T1-12 顶层 `write_surfaces` 追加 `tests/test_capability_mcp_server_load.py` 与 `lib/capability_sync_verification_helpers.py`（83→85），以及 `.omo/_truth/governance-evidence/waiver-2026-08-31-t1-12-mcp-load-current-main-scope-convergence.md` 记录本句、root main、#2794 merge `94448a8c6755f625ec2673c8aaa1e2cb410a9608`、T1 object、recovered OMO gitlink 与十路径 blob audit；十路径固定为 `bin/capability-sync.py`、`bin/ssot/gen-capability-registry.py`、`docs/generated/capability-registry.yaml`、`lib/capability_native_execution_model.py`、`lib/capability_native_execution_receipt.py`、`lib/capability_mcp_server_load.py`、`tests/test_capability_sync.py`、`tests/test_capability_native_execution_receipt.py`、`tests/test_capability_mcp_server_load.py`、`lib/capability_sync_verification_helpers.py`，current blob-map SHA-256 必须为 `9d15d2e59ec28b682452ae4e33f1e609355f1f72cb468f70a64a64dc23014459` 或经逐路径证明的授权后继；其中九路径与 approved ref byte-equal，唯一变化是 `lib/capability_native_execution_model.py` 从 blob `6f2c6a3fe029e0a043849a76c1868d0d5fc3706f` 前进到 #2794 blob `61bf15ae64368a0995f6d9b0a7c2d2d92be08081`，#2794 同时修改 `lib/capability_native_inspection.py`；这些 `mcp_server` model/inspection 变更作为 pre-existing partial implementation 保留，fresh implementation 必须重放测试并复用，不得回退、复制或用其冒充 bounded stdio canary。其余原 T1 第8节禁止项、真实 canary、永不 `tools/call`、candidate/evaluating、operational/value NOT_PROVEN 边界保持不变；若第一 PR 未合并并完成 post-merge readback，第二 PR 不得建立；若 authoritative child main 不再包含 `95e7b28`、child CI 不再成功或十路径出现新的 scope drift，立即停止并重新审议。

## Fixed evidence

- execution root main: `a6baeea07165f45dce977d0d898da678edfdac19`;
- approved current-main audit ref: `730f5871f474815343f57f5cf4d245b2d6a34a80`;
- original scope fixed ref: `743333a3d05425ee007df7e8abf53f30ad1ee158`;
- #2794 merge: `94448a8c6755f625ec2673c8aaa1e2cb410a9608`;
- first pointer PR disposition: no duplicate recovery PR was created because merged
  root PR #2790 (`d7ae725c07f9f973033eec4e77962396b45f5895`) had already advanced
  `projects/omo` to authoritative child main before this execution base;
- recovered root OMO gitlink: `bf8e34c23439dfb65b2c34bbac9e0b8178786282`;
- OMO admission ancestor: `95e7b28beeb62b3c94d8151095ef4194304f7044`;
- authoritative child CI: run `33334462006`, success,
  `https://github.com/starlink-awaken/omostation-omo/actions/runs/33334462006`;
- exact execution-base post-merge verification: root Governance Check run
  `33348392252`, success; Submodule Freshness Gatekeeper run `33348392242`,
  success;
- full recursive checkout completed; local require-main recheck passed all 14
  root gitlinks (`submodule-reachability: PASS (14 gitlinks, source=head)`);
- change-lane discipline: the two authorized paths classify as distinct
  `governance_state` and `docs_data` lanes, so delivery uses two single-lane
  commits in the same unique PR; no `AGENT_WORKFLOW_ALLOWED_LANES` override or
  registry change is used;
- normalized T1 object digest at the approved audit ref, original scope ref, and
  execution base: `0100ffda00efefe429f075690367d87c64facfb8052c794f2058bcb40b491b44`;
- pre-amendment T1 state: `candidate`, engineering `IN_PROGRESS`, operational
  and value `NOT_PROVEN`, overall `evaluating`, 83 write surfaces;
- accepted Spec 1.1.2 raw SHA-256:
  `41b7175076f14129b5e62989042f2f97d5f2b6ffb60cdd3a0ac9d60c27c0267a`;
- ten-path compact sorted JSON blob-map SHA-256:
  `9d15d2e59ec28b682452ae4e33f1e609355f1f72cb468f70a64a64dc23014459`.

## Ten-path blob map at execution base

- `bin/capability-sync.py`: `d102ac1e0b036b9df3a2ec9a0f7b337df275bbfa`;
- `bin/ssot/gen-capability-registry.py`: `e3e21185eac4e5cf7602e91cf5b90dc0cb84e44e`;
- `docs/generated/capability-registry.yaml`: `a8a1aa37d026a6ce55845d34852bfcdf7dd7f7cc`;
- `lib/capability_native_execution_model.py`: `61bf15ae64368a0995f6d9b0a7c2d2d92be08081`;
- `lib/capability_native_execution_receipt.py`: `d309a8efb10d556077537e33f0687341a24f37c0`;
- `lib/capability_mcp_server_load.py`: `8d75138d708f94ee05d7571464fc0f5612e07798`;
- `tests/test_capability_sync.py`: `40992f2124d75b834b7e0d8f43486838129a77f5`;
- `tests/test_capability_native_execution_receipt.py`: `38f514d297029afc46af7508b1c5a5b2f3a4db43`;
- `tests/test_capability_mcp_server_load.py`: `9f16b716d60b5b31a20882edc7b05b614da50fa2`;
- `lib/capability_sync_verification_helpers.py`: `f4ddf8ac64ca1331abd20388a0b11ccb45d01567`.

## Boundaries

This bootstrap only adds two existing implementation paths to the T1-12
WorkPacket write surface. It does not implement bounded stdio MCP load, invoke
an MCP tool, send `tools/call`, create a second verifier/dispatcher/registry,
write runtime or completion/value evidence, or promote T1-12 beyond
`candidate/evaluating` with operational and value `NOT_PROVEN`.
