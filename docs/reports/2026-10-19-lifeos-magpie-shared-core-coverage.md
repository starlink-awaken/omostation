---
schema_version: report/v1
title: LifeOS 7.40.4 shared core and Magpie client coverage — interim evidence
date: 2026-10-19
owner: governance-team
status: in_progress
bet_id: BET-Y2Q4-T10-254
---

# LifeOS 7.40.4 shared core and Magpie client coverage

## Current verified state

- The pinned LifeOS core resolves to 7.40.4. The existing USER and MEMORY remain the canonical data locations; this work has not created per-client copies.
- The Magpie Library skill entry and the shared LifeOS skill resolve to the same file and SHA-256 (`cc21c178f48d0aac44c9638e5b9f1d22c9265ba93b0de9743df3ec0957af378e`).
- A fresh Magpie CLI readback at 2026-10-19 14:04 +08 confirms the same 43 client roots, 40 LifeOS skill targets, and 16 instruction targets as the prior snapshot. The dynamic matrix is 43 × 16 = 688 relationships.
- The successor crosswalk and fresh readback match on client roots, skill assignments, instruction targets, and all 43 per-client route-summary fingerprints. The independent validator returns `valid=true`.
- Runtime evidence remains 20 `PASS_SCOPED`, 20 `UNKNOWN_NOT_RUN`, and 3 `BLOCKED_AUTH`. The scoped passes apply only to their cited client sessions and do not establish universal capability or persistent memory behavior.
- Five current Magpie provider routes remain identified: Claude Desktop, Copilot (JetBrains), Raycast, WorkBuddy, and ZCode. Their desktop/session proof must be performed per client. VS Code currently has no Magpie route in `magpie ls`; its shared skill discovery path is a separate compatibility surface.
- Raycast's settings show GPT-6 Luna selected, and its custom-provider file contains the Magpie loopback endpoint on port 3425. This confirms route configuration only; no Raycast AI request was sent because first use requires a human to accept the service terms.

## Validation artifacts

- Live inventory and assignment readback: `/Users/xiamingxing/Documents/Codex/2026-10-07/new-chat/outputs/magpie-integration-snapshots/mp012-live-inventory-assignment-readback-20261019T140420+0800.json` (SHA-256 `17cd8a06babcc8123732761d36abbe9ea993aaa3200b993e38469c1b72b3a899`).
- Crosswalk: `/Users/xiamingxing/Documents/Codex/2026-10-07/new-chat/outputs/magpie-integration-snapshots/mp017-lifeos-magpie-client-crosswalk-20261019T140420+0800.json` (SHA-256 `bfcda83cec0f1e3f8d89e97b381db62c70b1ed6e2a6fcb0d69bec43dbe17aec7`).
- Validator tests: 16/16 pass; `py_compile` passes. The live run reports exact membership and digest matches.
- `/Users/xiamingxing/.local/share/lifeos/ACTIVATION.json` now points its current live coverage fields to the 14:04 readback and retains pinned version 7.40.4. The previous activation file is preserved as `ACTIVATION.json.before-live-readback-20261019T140420+0800.bak`.

## Remaining work

- Obtain fresh-session loaded/usable evidence and Magpie usage correlation for every active Magpie-routed client. Raycast AI currently presents its first-use terms screen; it has not been accepted by the agent. The user has been asked to accept it themselves or defer Raycast.
- Repeat a restricted client probe for desktop clients that can be opened without new authentication or legal acceptance, and record exact versions, read paths, and usage attribution.
- Keep the BET-254 task registration synchronized with the canonical ledger. The shared ledger path is currently claimed by an active BET-253 workflow, so the registration branch must not overwrite that path until the owner releases it.
- Publish a final migration/rollback record, rerun all gates, and close MP-012 only when its client-level evidence and remaining authorization gates are resolved.

## Scope limits

The Magpie route-summary digest covers only the CLI-displayed provider/model summary and configuration path. It does not inspect credential values or prove each client's internal settings, data handling, hooks, or feature availability. No personal USER/MEMORY content was sent in the inventory refresh.

## Independent review follow-up (2026-10-19)

The independent BET artifact review returned `BLOCK` for reproducibility: the accepted spec's `work/lifeos-audit` paths are not present in this BET worktree, and its validator invocation does not show the required inventory receipt argument. The validator and its 16 tests currently live in the active task workspace at `/Users/xiamingxing/Documents/Codex/2026-10-07/new-chat/work/lifeos-audit/`; they were run there successfully, but are not yet part of this BET branch's authorized `write_surfaces`. The exact validated invocation was:

```sh
python3.12 -m unittest discover -s work/lifeos-audit -p test_crosswalk_contract.py
python3.12 work/lifeos-audit/crosswalk_contract.py \
  outputs/magpie-integration-snapshots/mp017-lifeos-magpie-client-crosswalk-20261019T140420+0800.json \
  --inventory-readback \
  outputs/magpie-integration-snapshots/mp012-live-inventory-assignment-readback-20261019T140420+0800.json
```

This local evidence does not resolve the repository reproducibility finding. Adding the validator, tests, and fixtures requires extending the BET write scope and synchronizing its accepted-spec digest. The canonical ledger is currently held by active BET-253, so that scope change is deferred until the path lock is released. BET-254 remains `in_progress`; the review is not treated as passed.

## Fresh CLI canaries (2026-10-19 14:24 +08)

Two additional read-only CLI invocations now have exact Magpie usage attribution. Pi used `--no-session` (a fresh stateless invocation, not a persistent session) and reported LifeOS 7.40.4 and the two shared paths; two requests for session `01a152d1-e1f0-73f7-a8ac-5dff584989f2` returned HTTP 200 through OMLX `mythos-fast`. OpenCode 2.0.26 used its read tool on the same two paths, reported 7.40.4, and two requests for session `ses_ead2bb5eaffelUGHnZbnQjBNnx` returned HTTP 200 through MiniMax `MiniMax-M2.7-highspeed`. Both prompts explicitly avoided USER, MEMORY, and TELOS. Pi was limited to its read tool and its native tool trace was not retained; OpenCode read-tool output was captured. The evidence is scoped to these invocations and does not prove persistent sessions or hooks.

Receipt: `/Users/xiamingxing/Documents/Codex/2026-10-07/new-chat/outputs/magpie-integration-snapshots/mp012-lifeos-cli-canary-attribution-20261019T1424+0800.json` (SHA-256 `959662664340c6b1cad46a522d4e86d80c0a1f310a3309596a8f82a0741d1724`). The active activation file was backed up before each additive update (`ACTIVATION.json.before-cli-canary-20261019T1424+0800.bak` and `ACTIVATION.json.before-cli-canary-review-fix-20261019T1427+0800.bak`). Only the nested `clients.piLatest`, `clients.opencodeLatest`, and `updatedAt` values changed; the pinned core and USER/MEMORY authority fields were retained. These results strengthen scoped CLI evidence; they do not clear the locked desktop clients or imply native hooks/persistent memory.

The runtime-matrix successor `/Users/xiamingxing/Documents/Codex/2026-10-07/new-chat/outputs/magpie-integration-snapshots/mp017-lifeos-magpie-client-crosswalk-20261019T142700+0800.json` (SHA-256 `b68b13ac5fc45a084b4a441b816cdcc9c0f16a07e6b3a65ca353304705510979`) incorporates these two scoped results while retaining the 14:04 inventory readback as its membership source. The validator returns `valid=true` for 43 roots × 16 instruction targets = 688 pairs; status totals remain 20 scoped PASS, 20 unknown, and 3 blocked. `ACTIVATION.json` now points its latest runtime matrix to this successor and records the earlier inventory timestamp separately.
