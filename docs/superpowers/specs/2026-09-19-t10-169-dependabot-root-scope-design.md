---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: Dependabot root checkout scope repair
bet_id: BET-Y1Q4-T10-169
created: 2026-09-19
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
---


# Dependabot root checkout scope repair

## Background and problem

The repository's Dependabot Updates run targets three paths that are root
gitlinks, not directories materialized in a normal root checkout:
`/projects/aetherforge`, `/projects/knowledge/kairon`, and `/projects/omo`.
Every update run therefore aborts with `dependency_file_not_found`. The root
repository itself has a valid zero-dependency `pyproject.toml` and `uv.lock`.

## Scope

- Add a root-only `uv` Dependabot update entry for directory `/`.
- Record the boundary that root gitlinks own their own dependency manifests and
  must not be scanned as root-checkout directories.
- Register the accepted specification and close the small repository-health BET.

## Non-goals

- Do not modify submodule contents or root gitlinks.
- Do not add child-repository Dependabot configs from the root repository.
- Do not change branch protection, CI workflows, runtime state, or Ledger
  completion/value semantics beyond this bounded repair.

## Acceptance criteria

1. The root Dependabot configuration is valid YAML and has exactly one update
   entry for `uv` at directory `/`.
2. The configuration states that `projects/**` manifests are not root-checkout
   targets.
3. Ledger lint accepts the completed BET with engineering verified,
   operational proven, value NOT_PROVEN, and overall `delivery_accepted`.
4. The five-question retro records the platform failure, evidence, and rollback.

## Verification commands

```text
python3 -c "import yaml; assert yaml.safe_load(open('.github/dependabot.yml'))['updates'][0]['directory'] == '/'"
uv run --with pyyaml python bin/plan/bet-ledger.py lint
git diff --check
```
