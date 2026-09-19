---
schema_version: specification/v1
spec_version: 1.0.0
title: Scene and Journey admission validator convergence
bet_id: BET-Y1Q4-T7-08
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-17
last-reviewed: 2026-09-17
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
type: ssot
---

# Scene and Journey admission validator convergence

## Background and problem

The repository has two different validation paths for the same scene-card
fleet. `scene-card-lifecycle.py` validates the current `scene-card/v2`
contract (`bet`, `falsifier`, and the five-tier lifecycle), while
`scene-card-registry.py` still requires the removed `domain` and
`promotion_evidence` fields. The result is a false-negative registry report:
cards pass lifecycle validation but all fail registration validation.

The Scene → Journey connector also resolves every path from the developer's
shared main workspace. In an isolated worktree, `--list` can therefore inspect
the wrong scene cards and `--create` can write state outside the worktree.

## Scope

- Make `scene-card-lifecycle.py` the canonical scene-card contract validator.
- Make `scene-card-registry.py` delegate schema/lifecycle validation to that
  canonical implementation and report legacy schema warnings explicitly.
- Add a repository-root parameter to `scene-journey-connector.py`, defaulting
  to the repository containing the script.
- Resolve scene cards, Journey specs, and connector state below the selected
  root; keep `--list` read-only and keep state writes limited to explicit
  create commands.
- Add focused tests proving validator parity and root isolation.
- Update the two script registry descriptions and the specification index.

## Non-goals

- Do not migrate or rewrite the 70 existing scene-card YAML files.
- Do not change lifecycle readiness, trial evidence, Journey state-machine
  semantics, or runtime projections.
- Do not add a second scene-card schema or a second connector state store.
- Do not make `--list` or validation mutate `.omo` state.
- Do not fix unrelated Journey warnings or the existing `journey-validate`
  failure in this packet.

## Acceptance criteria

1. `scene-card-registry.py --validate --all` uses the same canonical
   `scene-card/v2` field rules as lifecycle validation and no longer requires
   `domain` or `promotion_evidence`.
2. A legacy `scene-card/v1` card with the canonical `bet` and `falsifier`
   fields remains visible as a warning rather than being silently accepted or
   rejected solely for its schema version.
3. The connector has no user-specific absolute repository path. With
   `--root <temporary-root>`, list/create operations read and write only below
   that root.
4. Connector listing and validator operations do not create or modify the
   connector state file.
5. Focused tests cover current v2 parity, legacy warning behavior, root
   isolation, and explicit state mutation.
6. The targeted validator commands, focused tests, SSOT checks, workflow
   verification, and local governance gate pass; unrelated pre-existing
   Journey warnings remain documented as non-goals.

## Verification commands

```text
python3 bin/ssot/scene-card-lifecycle.py --root . validate --all
python3 bin/ssot/scene-card-registry.py --root . --validate --all
python3 bin/gac/scene-journey-connector.py --root . --list
python3 -m pytest tests/scene_v2/test_scene_card_registry_connector.py -q
python3 bin/ssot/check-cross-refs.py
make gac-local-gate
```

## Decision Log

| # | Fork | Decision | Reason |
|---|---|---|---|
| 1 | Which validator owns the schema? | `scene-card-lifecycle.py` remains canonical; registry delegates to it. | The lifecycle tool already validates the live v2 fleet and owns the five-tier contract. |
| 2 | What happens to the one v1 card? | Emit an explicit legacy warning while validating its shared required fields. | This packet must remove false negatives without silently performing a bulk migration. |
| 3 | How is repository context selected? | Add `--root`; default to the repository root derived from the connector script path. | Tests and worktrees need deterministic isolation; user-specific paths are not portable. |
| 4 | When may connector state change? | Only `--create` and `--auto-create` may write state. | Listing and validation must remain safe read-only probes. |
