---
schema_version: specification/v1
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last-reviewed: 2026-08-29
bet_id: BET-Y1Q3-T10-63
spec_version: 1.0.0
title: Governance waiver frontmatter repair
type: ssot
last_updated: 2026-09-03
---

# T10-63: Governance waiver frontmatter repair

## Context

The root governance document lifecycle checker reports one newly added
governance waiver without Markdown frontmatter:
`.omo/_truth/governance-evidence/waiver-2026-08-29-t10-61-meta-doctor-bootstrap.md`.
Its YAML body is valid evidence, but the missing document metadata makes it
consume the warning budget and blocks the interface gate. The T10-60 waiver
already has frontmatter; this slice repairs only the T10-61 waiver and adds
its own correctly formed evidence documents.

## Decision

Prepend the repository's existing governance-waiver frontmatter shape to the
T10-61 waiver. Do not change its authorization body, scope, expiry, or waiver
semantics. Verify that the document lifecycle checker no longer counts this
file as missing frontmatter.

## Non-goals

- No change to any governance rule, warning budget, workflow, BET verdict, or
  runtime state.
- No implementation, child repository, gitlink, Documents content, schedule,
  capability, or dispatcher change.
- No bulk frontmatter migration of historical files.

## Acceptance

1. The T10-61 waiver has valid frontmatter and preserves its existing body.
2. The focused document lifecycle check passes for the repaired waiver and
   the T10-63 evidence files.
3. The root interface check no longer fails because of this newly added
   waiver.

## Rollback

Restore the original T10-61 waiver bytes. No runtime or host rollback is
needed.
