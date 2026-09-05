---
schema_version: report/v1
type: report
title: BET-Y1Q4-T8-13 P0 core commands contract closeout
bet_id: BET-Y1Q4-T8-13
status: final
lifecycle: evidence
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T8-13 Closeout Receipt

## Verify

```text
uv run --project projects/cockpit pytest projects/cockpit/tests/test_core_commands.py -q
.............                                                            [100%]
13 passed in 1.87s
```

## Assertions locked

| Command | Invocation | Key asserts |
|---------|------------|-------------|
| dashboard | `--dry-run --json` / `-o json ... --dry-run` | `dry_run`, `url`, `port`, `ready` |
| quickstart | `--dry-run --json` | check item list |
| journey | `--dry-run --json` | `dry_run`, `runner_exists` |
| capabilities | `--dry-run --json` + filter `--json` | `dry_run` / `total` |
| data | `--json` + `gc --dry-run --json` | `status=ok` / `dry_run` |
| iterate | `--fast-track --dry-run --json` | `ok`, `dry_run`, `FAST-*` |
| workflow | `--dry-run --json` | `status=ok`, `engines` |
| compass | `--dry-run --json` | `pipeline`, `dry_run` |
| brain | `context --dry-run --json` | `preferences`, `dry_run` |

## Artifacts

- Spec: `docs/superpowers/specs/2026-09-05-t8-13-p0-core-commands-contract-design.md`
- Child PR: https://github.com/starlink-awaken/omostation-cockpit/pull/134
- Delivery SHA (child, squash): `42c429fb4792cdce172fab10b4f5ec2c508a627e`
- Retro: `.omo/_knowledge/retros/BET-Y1Q4-T8-13.md`
- Run-id: `20260905T022431Z-project-code-change-38ccd5f4`
