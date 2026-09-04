---
schema_version: specification/v1
spec_version: 1.0.0
title: L4 context-aware machine-log classification
bet_id: BET-Y1Q3-T10-109
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
type: ssot
last_updated: 2026-09-03
---

# L4 context-aware machine-log classification

## Context

Documents is the human content and declarative truth plane. Machine-generated
logs are mutable execution output and belong in a Workspace-owned runtime or a
recoverable quarantine, but the current L4 content-plane classifier treats
`.log` as ordinary `content` unless another path rule happens to match first.
That blind spot means retired `_inbox/hourly_runner*.log` files can remain in
Documents without appearing as violations.

A read-only 2026-08-31 snapshot also proves that a global `.log` rule would be
wrong. Documents contains both current operational logs and historical source
material, including old build and network-lab logs inside governed archive
roots. The snapshot is diagnostic evidence, not a durable count SSOT; every
live acceptance run must remeasure the current tree.

The full-tree audit remains non-green for independent, already registered
migration families and archive-contract drift. This BET closes one semantic
blind spot only. It does not reinterpret that wider debt or claim Documents
physical purity.

## Decision

Deepen the existing `l4_kernel.content_plane.classify_artifact` decision tree
with one context-aware machine-log predicate. A regular file or safe regular
file symlink with suffix `.log` becomes `cache` only when all earlier
classification authorities permit it and one of these contexts is true:

1. a path component is exactly `_generated`;
2. a path component is exactly `_runtime`;
3. adjacent path components are exactly `_control/logs`; or
4. the file is an immediate child of root `_inbox` and its stem ends in
   `_runner` or `_runner_err`.

The result uses the existing `cache` kind, reason, and `L4-CONTENT-009` issue
code. No new artifact kind, ontology, registry, CLI, or gate is introduced.

## Alternatives

1. **Context-aware classification — selected.** Detects current machine output
   while preserving human and historical logs. It is extensible through one
   narrow predicate and reuses the canonical classifier.
2. **Classify every `.log` as cache — rejected.** It would convert archived
   learning and career artifacts into operational debt and destroy the content
   versus execution distinction.
3. **Hard-code two complete paths — rejected.** It would clear the immediate
   symptom but leave the same blind spot for equivalent generated, runtime, and
   control-plane logs.

## Classification precedence

Existing filesystem and archive safety remains authoritative:

1. inspect the node with `lstat` and never follow an unsafe symlink;
2. preserve existing cache-directory and cache-suffix decisions;
3. detect an approved Workspace bridge;
4. resolve `CONTENT_ARCHIVE.yaml`; valid archives remain `content_archive` and
   invalid archives remain fail-closed `invalid_archive`;
5. apply the new machine-log predicate;
6. continue through existing runtime, projection, contract, and content rules.

Putting the predicate after archive resolution is binding. A `.log` covered by
a valid or invalid archive contract must not bypass that contract merely
because its path contains an operational-looking component.

The same predicate participates in regular-file and safe-symlink branches so
classification cannot be bypassed by replacing a machine log with a link. All
existing target-type and stability revalidation remains unchanged.

## Components and data flow

The child repository owns a private pure helper in
`src/l4_kernel/content_plane.py`. It accepts the already normalized relative
path and returns a boolean; it performs no file read, write, glob, process
inspection, or registry lookup.

`classify_artifact` computes the normalized path once, resolves filesystem and
archive authority as today, calls the helper at the defined precedence point,
and emits the existing `ArtifactClassification`. Existing report, summary,
harness, lifecycle, and CLI consumers receive the stronger result without any
interface change.

The root repository owns the accepted specification, BET contract, delivery
report, retrospective, child gitlink, and mainline replay evidence. The L4
child PR must merge before the root pointer PR.

## Error handling and invariants

- No host or Documents path is mutated by T10-109.
- Missing, unstable, non-regular, or unsafe symlink nodes retain existing
  fail-closed behavior and stable issue codes.
- Arbitrary `.log`, nested `_inbox` logs, and root `_inbox` logs without the
  runner stem remain governed by existing content/archive rules.
- Archive authority cannot be weakened or skipped.
- A live full-tree audit is evidence of classification behavior only; its
  unrelated violations do not make this BET fail unless the target
  classifications, stability, or preservation controls are wrong.
- T10-109 must not move, truncate, delete, rewrite, or open for writing either
  retired runner log. Their physical quarantine is T10-110.

## Testing

Implementation is test-first and must prove RED before production edits. Child
tests cover:

- `.log` under `_generated` and `_runtime` becomes `cache`;
- `.log` under adjacent `_control/logs` becomes `cache`;
- immediate `_inbox/hourly_runner.log` and
  `_inbox/hourly_runner_err.log` become `cache`;
- arbitrary `_inbox/meeting.log`, nested `_inbox` logs, and unrelated `.log`
  remain `content`;
- valid archive logs remain `content_archive` and invalid archive logs remain
  `invalid_archive`;
- safe symlink parity and existing unsafe-target rejection;
- CLI JSON and summary output preserve their schemas and expose
  `L4-CONTENT-009` for selected logs.

Verification broadens from focused classifier/CLI tests to the complete L4
suite, Ruff, root gitlink and BET checks, GaC, required child/root CI, and a
fresh read-only live canary against the actual Documents paths.

## Delivery topology

1. Merge this design/BET bootstrap PR and replay it from authoritative root
   main.
2. Start a BET-bound implementation workflow in a fresh independent clone and
   claim exact child/root surfaces.
3. Merge the L4 child PR after focused/full tests and required child CI.
4. Update only the root gitlink plus T10-109 evidence surfaces in a root PR;
   merge after required root CI.
5. Replay focused tests and live read-only canaries from root main, close the
   workflow, and keep user value `NOT_PROVEN`.
6. Register and execute T10-110 separately for reversible runner-log
   quarantine.

## Non-goals

- No global `.log` suffix classification.
- No Documents, LaunchAgent, cron, process, application, or host mutation.
- No runner-log movement, truncation, deletion, or permanent cleanup.
- No content-archive manifest repair or weakening.
- No migration-family status change and no claim that any large pending family
  is complete.
- No second dispatcher, classifier registry, artifact ontology, control plane,
  or human entry point.

## Acceptance

- The exact context predicate and precedence contract are implemented and
  covered by RED-to-GREEN tests in L4.
- Historical and arbitrary logs retain their prior content/archive semantics.
- The two retired root `_inbox` runner logs are read-only classified as
  `cache/L4-CONTENT-009` on a fresh live canary.
- Child and root PRs merge with required checks; authoritative child main,
  root gitlink, and root main ancestry align.
- Mainline replay, report, retro, completion matrix, and workflow closeout pass.
- Engineering may become `VERIFIED`; operational value and principal-bound
  user value remain `NOT_PROVEN` because T10-109 performs no physical cleanup.
