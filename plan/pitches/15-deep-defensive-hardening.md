# Pitch: Deep Defensive Hardening & Replay Protection

> **Upstream**: MS-SECURITY-DEFENSE
> **Appetite:** 3 days

## 🎯 The Why (Problem & Opportunity)
The eCOS v6 distributed architecture is now functionally complete, but its defensive "Micro-Moat" still has gaps:
1. **Replay Vulnerability:** A2A messages have signatures but no time-window validation or nonce tracking, allowing an attacker to replay valid signed messages.
2. **Concurrent Write Hazards:** Distributed nodes and local daemons (Cockpit, Evolution Loop, LLM Gateway) write to shared JSONL logs (`budget_overrides`, `quota_ledger`) without locking, risking interleaved data or corruption on high-concurrency.
3. **Sandbox Blind Spots:** `KeiSandbox` intercepts `open` but misses direct FS mutations like `os.remove` or `os.rename`, allowing agents to bypass write-protection by renaming files.
4. **Knowledge Redundancy:** The Memory Spine aggregates search results but does not deduplicate them, leading to wasted LLM context if KOS and Vault return the same snippets.

## 🚧 The What (Solution Overview)
Execute a high-fidelity defensive upgrade:

1. **A2A Nonce & TTL:** 
   - Receiver (`a2a.py`) must verify that the `timestamp` in the signed payload is within +/- 300 seconds of current time.
   - Implement a simple memory-based cache for seen signatures to prevent replay within the TTL window.
2. **Atomic SSOT Appends:** 
   - Refactor `record_llm_cost` and `_execute_mutation` to use `fcntl.flock` on file descriptors before writing to ensure atomic append-only behavior.
3. **Sandbox Expansion:** 
   - Add audit hooks for `os.remove`, `os.rename`, `os.mkdir`, and `os.rmdir` to the `KeiSandbox`.
4. **Memory Deduplication:** 
   - In `bos_resolver._memory_all_search`, compute a hash of the content snippets and filter duplicates before returning to the agent.

## 📏 Boundaries & Appetites
- **Appetite:** 3 Days (High precision, security-focused).
- **No-Gos:** Do not introduce a central database for nonces; keep it memory-resident per node for performance.

## ⚠️ Rabbit Holes & Risks
- **NFS/Network FS Locking:** `fcntl.flock` might behave differently on some network filesystems. We'll assume local Workspace storage for now.
- **Clock Drift:** Distributed nodes must have somewhat synchronized clocks (within 5 minutes) for A2A TTL to work.
