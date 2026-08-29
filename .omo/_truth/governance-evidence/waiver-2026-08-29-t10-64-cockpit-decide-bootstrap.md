---
schema: workflow-waiver/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-08-29
last-reviewed: 2026-08-29
title: T10-64 cockpit decide canonical inbox bootstrap waiver
type: doc
---

waiver: user-explicit
when: 2026-08-29T11:30:00Z
who: xiamingxing
scope:
  - projects/cockpit
  - docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-64
  - docs/superpowers/specs/2026-08-29-cockpit-decide-canonical-inbox-design.md
  - docs/reports/2026-08-29-cockpit-decide-canonical-inbox.md
  - .omo/_knowledge/retros/BET-Y1Q3-T10-64.md
  - this waiver
reason: User-authorized continuation of the Workspace capability convergence; the root cockpit gitlink is behind child main's sanctioned atomic-helper repair and the legacy decide writer blocks the root interface.
constraints:
  - Preserve the public cockpit decide actions and use the existing OMO atomic-helper boundary.
  - Do not migrate the legacy JSON data model to scenario inbox in this bounded slice.
  - No new storage, broker, dispatcher, schema, capability, authority, Documents, host, runtime, or unrelated child/root pointer change.
  - Formal workflow must be started, all write surfaces claimed, and child/root verification recorded before closeout.
expiry: 2026-08-30T11:30:00Z
