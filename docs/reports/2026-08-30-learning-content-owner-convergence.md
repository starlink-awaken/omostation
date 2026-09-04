---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-100
---

# Learning content owner convergence — implementation evidence

## Scope

This delivery moves the two remaining learning-domain executors out of
Documents:

- `@学习进化/_control/scripts/knowledge-decay.sh`
- `@学习进化/_inbox/inbox-router.sh`

The learning concept corpus, inbox content, control Markdown, contracts, and
all other learning runtime surfaces remain in place. `l4-kernel.sh`,
`vault-healthcheck.sh`, daemon/executor wrappers, and `.githooks` are a later
control-plane wave.

## Workspace owner

`lib/documents_learning_control.py` implements one deterministic owner behind
the existing `bin/gac/documents-domain-owner-job.py` entry:

```text
python3 bin/gac/documents-domain-owner-job.py learning-control decay mark-stale --dry-run --json
python3 bin/gac/documents-domain-owner-job.py learning-control inbox route --dry-run --json
```

Apply is never implicit. It requires the exact fingerprint returned by a
prior plan. Decay updates only eligible frontmatter atomically; inbox routing
moves only internal targets and explicitly defers cross-domain targets. Both
operations create a Workspace rollback manifest and reverse already-applied
changes on failure. System Python 3.9 dry-runs work because the old L4 import
is now lazy for this owner route.

## Preflight and transaction

- Concept owner dry-run: 74 inventory files, 43 draft/orphan candidates,
  fingerprint `sha256:d98abd243e1e3fd7c4d7254a27c912a4ad27277eeb4c8ce527a9fb41a262c07f`.
- Inbox owner dry-run: 4 inventory files, 4 plans, 0 deferred external
  targets, fingerprint
  `sha256:bfaada01c92e67b16dd0bdf49b709c6df960b2dcd6f8a7ab299264ea247a2c87`.
- Fresh consumer receipt: status `ok`, active=188, content_references=176,
  workspace_read_owners=12, forbidden_executors=0, unmatched=0.
- L4 preflight selected exactly one regular runtime file per target. A
  read-only Virtualization process held temporary source handles before the
  move; it was not killed. A postflight `lsof` returned no source handles.
- Final canonical targets are under the actual Workspace, not the delivery
  clone:
  `~/Workspace/runtime/quarantine/documents-learning-knowledge-decay-20260830/`
  and
  `~/Workspace/runtime/quarantine/documents-learning-inbox-router-20260830/`.
- An initial isolated-clone rehearsal was restored through explicit moves and
  replayed at the canonical target. Final manifests are the two canonical
  Workspace manifests; no source bytes were changed.

## Postflight

- Both Documents source paths are absent.
- `knowledge-decay.sh`: 10037 bytes, mode 0711, SHA-256
  `fd4fda9d333b7de955414dfdf6c129c542a45650072749b7a8958473bf9cb5be`;
  source/target fingerprint
  `sha256:06e8541ec3de3ecd7258a57565baef78e3849a62ef4a2d578b1f0e3bbf3e4093`;
  manifest SHA-256
  `02bec508894192c288969959ffe1a7ebc733661fa179c1b1cfdbe3d31e41480e`.
- `inbox-router.sh`: 3671 bytes, mode 0711, SHA-256
  `924b499860ea69e4b7c9c258eb23b35e26cd6982f444ba3eb05aede4314bfbef`;
  source/target fingerprint
  `sha256:15f37f3e79347f4a896a15c7fb54b6fa57e9267582c455f1830fbe211e9ba09`;
  manifest SHA-256
  `6cd17eb01a0d24a53b975333518285affaf522bd543d84d190254e1cabc38902`.
- L4 postflight: `_control/scripts` content=2, runtime=0; `_inbox`
  content=5, contract=1, runtime=0.
- Consumer postflight remained status `ok`, forbidden=0, unmatched=0.
- Quarantine manifests are protected by the root `runtime/quarantine/*/`
  ignore rule and permanent deletion is false.

## Mainline closure

Root PR #2695 merged to root `origin/main` as
`81e1f1cba3ec1f7661013059ad435f31687a1bf8`. The merged tree retains the
Workspace owner, active Documents pointers, migration registry, and this
report. The completion matrix is recorded in the T10-100 ledger entry after
this report and retrospective were finalized.

During closeout lint, root main also exposed an inherited ledger regression:
the already-done T1-12 entry had lost its canonical `workflow` and
`write_surfaces` fields in an earlier evidence-restore merge. The closeout
restored those fields from the prior mainline contract without changing its
completion or value evidence, leaving the full ledger valid before T10-100
transition.

The same mainline audit found T4-07's engineering diff/rollback references
stale relative to its current retro file. Those two evidence digests were
refreshed to the actual tracked SHA; its value verdict and overall state were
left unchanged.

## Boundary

The migration family remains `learning-runtime: in_progress` and
`owner_parity: partial`. Read-only and guarded mutation ownership is now
available; the L4 control plane and remaining daemon/executor surfaces still
need independent owner contracts and physical evidence.
