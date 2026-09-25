---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: OMLXC fabric inference-readiness evidence repair
bet_id: BET-Y2Q2-T10-161
---


# T10-161 — OMLXC fabric inference-readiness evidence repair

## Context

The three-node OMLXC fabric is operating in AetherForge shadow mode and each
declared production placement has passed a direct inference canary. Two code
paths still weaken the repeatability of that evidence:

- `omlxc routes test` is present in the public CLI but always returns an
  unsupported error instead of exercising the daemon's OpenAI-compatible
  inference route.
- `scripts/compute-mesh-pulse.py` hard-codes `/tmp/omlxc.sock`, while the
  daemon's canonical default is the configured `omlxcd.sock` under the user
  configuration directory.

The LM Studio adapter was also inspected because a catalog-only health signal
would be unsafe. The current implementation already merges HTTP inventory
with `lms ps`, distinguishes available from loaded models, and requires a
successful short chat probe before setting `generation_ready`; that surface
therefore needs verification, not another behavior change.

## Goal

Make inference readiness reproducible from supported OMLXC interfaces by
implementing a bounded `routes test` canary and making the compute-mesh pulse
resolve the same configured Unix socket as the daemon client.

## Non-goals

- Do not add another dispatcher, gateway, model alias authority, or health
  registry; OMO remains the only dispatcher and AetherForge remains the only
  public inference facade.
- Do not implement route pinning, config apply/rollback, or change placement
  selection policy in this tranche.
- Do not change model files, machine credentials, remote runtimes, launchd
  state, or AetherForge active/shadow mode.
- Do not change LM Studio discovery semantics unless a failing regression test
  disproves the existing loaded-plus-generation-ready contract.

## Done when

- `omlxc routes test <model>` sends one non-streaming, low-token chat request
  through the private daemon socket and reports the selected public model,
  completion status, visible response presence, and token usage without
  printing prompt or response content.
- The command preserves daemon identity validation, timeout/error mapping, and
  JSON envelope conventions used by the rest of the CLI.
- `compute-mesh-pulse.py` resolves the daemon socket from an explicit CLI
  override, then user configuration, then the package default; it no longer
  silently falls back to `/tmp/omlxc.sock`.
- Unit tests cover success, malformed response, daemon error, socket override,
  configured socket, and default socket behavior.
- A real local canary is observed against the running daemon after unit tests
  pass.

## Verification

```bash
uv run pytest tests/unit/test_daemon_client.py tests/unit/test_cli_daemon.py -q
uv run pytest tests/unit/test_lmstudio_adapter.py tests/contract/test_lmstudio_contract.py -q
uv run pytest tests/unit/test_compute_mesh_pulse.py -q
uv run ruff check src/omlxc tests scripts/compute-mesh-pulse.py
uv run pyright src/omlxc
```

The root closeout additionally runs `make gac-local-gate` from the isolated
workspace.

## Bootstrap authorization

The accepted specification and its single new ledger entry are bootstrapped
under the principal's explicit one-shot authorization recorded at
`repo://.omo/_truth/governance-evidence/waiver-2026-09-24-omlxc-fabric-readiness-bootstrap.md`.
That authorization permits `AGCP_REQUIREMENT_ITERATION_GATE=0` only to break
the requirement-to-BET self-bootstrap cycle. It does not authorize a gitlink,
retrospective, implementation-code, model, service, or runtime-state change.

## Rollback

Revert the OMLXC child-repository patch and restore the prior root gitlink. No
runtime configuration or model state is changed by this delivery.
