---
schema_version: governance-waiver/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: '2026-09-23'
created: '2026-09-23'
expires_at: '2026-09-28T00:00:00+08:00'
bet_id: BET-Y2Q2-T4-01
run_id: 20260923T033006Z-project-doc-change-a155577a
scope: accepted-spec-and-single-candidate-bet-bootstrap
type: evidence
---

# North-star BET bootstrap waiver

## Principal delegation

At 2026-09-23 local time the principal stated:

> 目前并发不可避免，你需要考虑到这种情况，不能啥都等，考虑一下这个问题怎么解决，我给你授权，截止到本周日晚上12点之前，所有的封禁或者屏蔽，你来决策，不用等我。

This receipt interprets “本周日晚上12点之前” as ending at
`2026-09-28T00:00:00+08:00`, immediately after Sunday 2026-09-27.

## Deadlock and decision

The root workflow requires a BET before a requirement-iteration run can start,
while the single new BET must itself be added through a governed edit. The
already active Claims Authority would turn a normal workflow claim into a new
Claims lifecycle operation, which the Goal explicitly does not authorize.

The delegated decision is therefore the narrowest non-Claims bootstrap:

- use `AGCP_REQUIREMENT_ITERATION_GATE=0` only for unbound run
  `20260923T033006Z-project-doc-change-a155577a`;
- write exactly one accepted Spec, this waiver, and exactly one candidate BET;
- use `bin/gac/ledger-safe-insert.py` for the Ledger transaction;
- do not call workflow `claim`, Claims Authority, a legacy fence, publication,
  or instruction capability;
- do not edit the canonical Workspace;
- stop further implementation edits after the candidate is bootstrapped until
  the next governed binding is proven.

## Allowed repository surfaces

- `docs/superpowers/specs/2026-09-23-north-star-recovery-and-first-decision-episode-design.md`
- `.omo/_truth/governance-evidence/waiver-2026-09-23-north-star-bet-bootstrap.md`
- `docs/plans/3y-bet-ledger.yaml`

No other repository path is authorized by this waiver. It does not authorize a
new Claims receipt, runtime authority mutation, legacy publication, force push,
`--no-verify`, historical receipt mutation, Restricted-data egress, synthetic
value evidence, or direct modification of another writer's work.

## Concurrency fence

The isolated worktree is the sole writer for these surfaces. Remote
`refs/heads/main` is double-read before push and merge. Any remote OID change
invalidates the pending external effect until the exact three-file diff is
replayed and reverified on the new base.
