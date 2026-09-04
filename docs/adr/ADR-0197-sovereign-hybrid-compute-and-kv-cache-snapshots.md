---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
type: ssot
---
# ADR-0197: Sovereign Hybrid Compute & KV Cache Binary Snapshots

## Status
Accepted

## Context
High-frequency agent interactions suffer from repeated cold-start prompt tokenization and redundant cloud API calls for trivial AST/syntax triage tasks. A local-first compute fabric is required to ensure 0-cost, privacy-safe execution for high-frequency operations while enabling 0ms TTFT pre-warmed system prompt states.

## Decision
1. Implement `KVCacheSnapshotStore` in `omlxc.dataplane.kv_snapshot` to persist binary KV Cache states for MOF SSOT constraints and global system prompts.
2. Implement `SpeculativeRouter` in `omlxc.dataplane.speculative` to triage tasks between local 14B Q4_K_M speculative execution and frontier cloud cascading.
3. Expose via CLI `omlxc fabric snapshot` and `omlxc fabric speculative-eval`.

## Consequences
- Reduces TTFT for governed agent sessions to effectively 0ms.
- 90% of routine AST triage and syntax validation runs entirely on local sovereign silicon.
