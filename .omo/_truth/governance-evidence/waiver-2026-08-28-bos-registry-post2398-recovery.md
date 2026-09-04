---
lifecycle: history
owner: governance-team
last_updated: 2026-08-28
title: Post-#2398 BOS registry mirror recovery waiver
type: doc
---

# Post-#2398 BOS registry mirror recovery waiver

- Actor: `codex`
- Delivery attempt: `bos-mirror-post2398-20260828`
- Root main: `9d0ede018698eec93699ff28d860242bdac4a5dc`
- Agora gitlink/check-out: `eed1583d0dbdf50002802b9b8a5757f359520e8c`
- Workflow bypass: `AGCP_REQUIREMENT_ITERATION_GATE=0` was used only because
  this generated-mirror recovery has no claimable BET; both paths are claimed
  by local and canonical `governance-state-mutation` runs.

## Written authorization

> 我给你全面授权，推进解决目前存在的所有临时问题，建立好机制和规范，继续推进目标任务吧

> 有需要我授权的，我全权委托给你，按照最优解来决策

> 我给你完整授权，你继续推进吧。

## Scope

- Regenerate `.omo/_knowledge/bos-registry.json` only through
  `bin/ssot/sync-bos-registry.py --write` from the root-recorded Agora gitlink.
- Record this waiver evidence.

## Direct evidence

- Pre-write: `live=157`, `file=155`, `drift=YES`, `raw_yaml=262`.
- Post-write: `live=157`, `file=157`, `drift=no`, `raw_yaml=262`.
- The fresh clone's Agora checkout exactly matched the root gitlink before
  generation.

## Forbidden scope

Do not modify Agora, any gitlink, BOS service declarations, capabilities,
governance rules, BET/completion/value evidence, runtime state, host services,
CI workflow, branch protection, or user configuration. This waiver is not
reusable after this two-file recovery.
