---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-27
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-42
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Documents consumer tail retirement

## Decision

After the daily-health and KOS schedules moved to Workspace, the remaining
tail consists of Scheduled instructions and derived OMO evidence projections.
The Scheduled skill must call the accepted Workspace owner and may only read
Documents inputs. OMO state must be refreshed through its broker, never by
editing `.omo/state` directly.

## Scope and gates

- replace direct Documents script instructions in `weijian-daily-health` with
  the canonical Workspace owner command;
- redirect task evidence from Documents generated logs to Workspace runtime
  evidence and synchronize derived counters through `omo state sync-tasks`;
- verify the old instruction/evidence paths are absent from active consumers;
- preserve a byte/mtime snapshot of the referenced Documents content;
- no physical deletion or movement of Documents material in this BET.

The change fails closed if the Scheduled skill cannot be updated atomically,
the Workspace owner is unavailable, the OMO broker rejects the sync, or any
Documents content changes. Permanent runtime/cache retirement remains a later
human-gated wave.
