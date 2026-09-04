---
type: ephemeral
created: 2026-09-03
---

# T10-64 Cockpit decide write-boundary recovery — Delivery Report

Date: 2026-08-29 · Bet: `BET-Y1Q3-T10-64` · Spec:
`docs/superpowers/specs/2026-08-29-cockpit-decide-canonical-inbox-design.md`

## Finding

The root `projects/cockpit` gitlink pointed to `37bf989`, whose legacy
`cockpit decide` command directly mutated `.omo/state/decision-inbox.json`.
Cockpit child main already had an intermediate atomic-helper repair, but the
root gate requires callers outside OMO core to use the canonical scenario
inbox boundary.

## Change

- Child PR #94 changed `cockpit.commands.decide` into a compatibility adapter
  over the existing `scenario inbox` helpers.
- `list`, `add`, `approve`, `reject`, and `status` remain available.
- The adapter creates/reuses a canonical default scene and journey for `add`
  and updates canonical intent status for approvals/rejections.
- The legacy `.omo/state/decision-inbox.json` loader/writer was removed from
  the command module.
- Root `projects/cockpit` is prepared at child-main merge commit
  `058163fb38a14a273021fcb3cdbaf7be55766af1`.
- No new storage, broker, dispatcher, schema, capability, Documents content,
  host schedule, or runtime state was added.

## Verification

| Check | Result | Evidence |
|---|---|---|
| TDD RED | PASS | Canonical scene-intent test failed before the adapter hook existed. |
| T10-64 targeted adapter test | PASS | `test_decide_list_reads_canonical_scene_intents`. |
| Decide module gatekeeper | PASS | Direct contract gate reports no mutation in `decide.py`. |
| Root OMO direct-io gate | PASS | Composite workspace gate reports no direct mutation. |
| Child PR #94 | PASS | Cockpit lint and test checks passed before merge. |
| Full Cockpit suite | PARTIAL | 1307 passed; 25 pre-existing personal-episode/authority failures remain, all outside decide. |
| Root mainline | PENDING | Root gitlink PR is not merged yet. |

## Boundary note

This slice removes the duplicate writer and makes the public entry use the
canonical scenario-inbox engine. It does not claim principal-bound business
value; `value` remains `NOT_PROVEN`.

## Rollback

Restore the root `projects/cockpit` gitlink to `37bf989` and revert child PR
#94. No runtime or host rollback is needed.
