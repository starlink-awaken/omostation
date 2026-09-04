---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-102
---

# Documents consumer-audit path tokenization — implementation evidence

## Result

The canonical consumer audit now separates Documents executable paths from
trailing command arguments and treats forbidden executors as a blocking
violation. It keeps quoted HOME/absolute path spaces, exact Workspace owner
exemptions, and the existing `documents.consumer-audit.v1` receipt shape.

## Root cause

The HOME and absolute-root scanners consumed whitespace-delimited argv as part
of the path. The live command
`bash ~/Documents/@学习进化/_control/l4-kernel.sh all` therefore became the
non-executable string `@学习进化/_control/l4-kernel.sh all` and disappeared from
the candidate set. A duplicated execution predicate also omitted extensionless
`_control/executors` and `.githooks` surfaces.

The audit additionally counted unmatched domain-gateway content references as
hard errors even though its own contract classifies those declarations as
`content-reference`. Unmatched fail-closed behavior is now restricted to real
`documents-executor` surfaces.

## Verification

- TDD RED: command-token tests failed with zero consumers; the
  content-reference boundary test failed with unmatched=1.
- GREEN: 10 focused tests pass, including quoted HOME and absolute paths with spaces.
- Ruff passes for implementation and tests.
- Both files parse with Python `feature_version=(3, 9)`.
- The live audit writes evidence only under Workspace:
  `.omo/evidence/20260830T092519Z-bet-execution-ea3b141d/live-consumer-audit.json`.
- T10-23 and T10-36 completion matrices are re-attested to the current focused
  test-file digest after the behavior-preserving regression additions; their
  status and value verdicts are unchanged.

## Live host truth

After the fix, the actual host audit returns:

- status: `violations`
- active observations: 199
- forbidden executors: 1
- unmatched executors: 0
- Workspace owner reads: 4
- content references: 194

The sole forbidden executor is:

```text
source: /Users/xiamingxing/Documents/Claude/Scheduled/vault-daily-health/SKILL.md
kind: scheduled-skill
family: learning-runtime
path: @学习进化/_control/l4-kernel.sh
command: bash ~/Documents/@学习进化/_control/l4-kernel.sh all
```

## Boundary and next wave

This BET does not modify Claude Scheduled, Documents, crontab, LaunchAgents, or
migration-family status. The active Scheduled command now fails the hard gate
truthfully and must be cut over to
`bin/gac/documents-domain-owner-job.py learning-control-plane all` in a separate
host transaction with backup and rollback evidence.

## Mainline closure

Root PR #2726 was squash-merged as
`51b4f4c92e3dab225717e923a8deb0b0d9961772`. All required checks completed
without failure, including tests, GaC, interface, evidence, and
governance-verify. A fresh mainline host replay preserves the exact result:
`forbidden_executors=1`, `unmatched=0`, and only `vault-daily-health` is red.
The replay receipt is
`.omo/evidence/20260830T094416Z-bet-execution-45064ddb/mainline-live-consumer-audit.json`.
