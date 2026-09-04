---
schema_version: governance-waiver/v1
lifecycle: history
type: requirement-iteration-waiver
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-77
---

# T10-77 work-runtime host mutation authorization

The user explicitly authorized full progression of the Documents execution-plane
convergence. This waiver records permission for the bounded host mutation that
moves only the 17 stable L4 regular runtime files under
`@工作文档/卫健委/_runtime` into the Workspace quarantine.

The transaction remains fail-closed: no symlink target is followed, no content
or cache is moved, no permanent deletion occurs, and any hash/consumer/manifest
failure must restore the source set.
