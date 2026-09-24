---
schema_version: governance-waiver/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: '2026-09-24'
created: '2026-09-24'
expires_at: '2026-09-25T00:00:00+08:00'
bet_id: BET-Y2Q2-T10-161
run_id: 20260924T021135Z-project-doc-change-db6d7446
scope: accepted-spec-and-single-candidate-bet-bootstrap
type: evidence
---

# OMLXC readiness BET bootstrap waiver

## Principal authorization

On 2026-09-24 the principal stated:

> 我授权 BET-Y2Q2-T10-161 使用 `AGCP_REQUIREMENT_ITERATION_GATE=0` 完成自举；范围仅限对应 spec、ledger 新条目和 waiver 证据，不包括 gitlink、retro、实现代码或运行态。

This is a one-shot authorization. It expires when the first bootstrap PR is
merged or at `2026-09-25T00:00:00+08:00`, whichever occurs first.

## Deadlock and decision

The requirement-iteration gate requires an existing BET before a normal run
can start, while this BET must itself be added through a governed edit. The
narrow decision is therefore:

- use `AGCP_REQUIREMENT_ITERATION_GATE=0` only for bootstrap run
  `20260924T021135Z-project-doc-change-db6d7446`;
- write exactly one accepted specification, this waiver, and exactly one new
  candidate BET entry;
- use `bin/gac/ledger-safe-insert.py` for the ledger transaction;
- keep workflow leases and claims as transient publication-control evidence,
  never as repository delivery surfaces;
- close the bootstrap run after publication or a fail-closed stop.

## Allowed repository surfaces

- `docs/superpowers/specs/2026-09-23-omlxc-fabric-readiness-evidence.md`
- `docs/plans/3y-bet-ledger.yaml`
- `.omo/_truth/governance-evidence/waiver-2026-09-24-omlxc-fabric-readiness-bootstrap.md`

No other repository path is authorized. In particular, this waiver does not
authorize a gitlink change, retrospective, implementation code, model or
machine configuration, service state, live runtime mutation, direct push,
force push, `--no-verify`, synthetic value evidence, or another writer's work.

## Concurrency and publication fence

The isolated worktree is the sole writer for these three paths. Publication
must use an admitted managed successor with canonical claims authority. Any
upstream OID change invalidates the candidate until the exact three-file diff
is replayed and reverified on an admissible base. A child gitlink that is not
reachable from its declared `origin/main` is a hard stop, not a waiver target.
