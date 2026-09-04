---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
title: T10-63 governance waiver frontmatter repair bootstrap waiver
type: doc
---

waiver: user-explicit
when: 2026-08-29T11:00:00Z
who: xiamingxing
scope:
  - .omo/_truth/governance-evidence/waiver-2026-08-29-t10-61-meta-doctor-bootstrap.md
  - docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-63
  - docs/superpowers/specs/2026-08-29-governance-waiver-frontmatter-repair-design.md
  - docs/reports/2026-08-29-governance-waiver-frontmatter-repair.md
  - .omo/_knowledge/retros/BET-Y1Q3-T10-63.md
  - this waiver
reason: User-authorized continuation of the Documents capability-downshift work; a missing frontmatter seam in a newly added waiver blocks the clean governance interface and requires a bounded document-only repair.
constraints:
  - Preserve the T10-61 waiver body and authorization semantics byte-for-byte after the new frontmatter delimiter.
  - No bulk migration, rule, budget, runtime, host, child, gitlink, Documents, or capability change.
  - Formal workflow must be started, all write surfaces claimed, and verification recorded before closeout.
expiry: 2026-08-30T11:00:00Z
