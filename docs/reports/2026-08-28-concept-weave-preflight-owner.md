# Concept weave preflight owner evidence — 2026-08-28

The monthly LaunchAgent currently executes a Documents shell writer that
mutates concept notes, logs/history, and sometimes inbox todo files. This wave
adds a Workspace-only read-only preflight; write-capable mesh/bridge operations
remain explicitly deferred.

## Live smoke

- Schema: `documents.concept-weave-preflight.v1`.
- Result: `findings`, exit `1`.
- Concept files: `78`; link edges: `3`; orphan files: `76`; decay candidates: `0`.
- Deferred operations: `mesh`, `bridge`, `exec-bridge`, `inbox-todo`.
- Evidence was written to an isolated Workspace path; no Documents writes or
  legacy script execution occurred.

## LaunchAgent candidate

The existing label/calendar semantics will be preserved, while ProgramArguments
will point to the accepted Workspace release's
`lib/documents_concept_weave_preflight.py` with explicit Documents input and
Workspace evidence output. A separate governed plist cutover must record the
before/after plist SHA, `plutil -lint`, `launchctl print`, and rollback copy.
