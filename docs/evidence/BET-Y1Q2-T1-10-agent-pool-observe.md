---
lifecycle: entry
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# BET-Y1Q2-T1-10 Agent Pool Observation Evidence

> Scope: trusted single-user local observation and admission preflight. This is
> not a dispatch receipt, model-call receipt, quota ledger, or proof of task
> completion.

## Contract

- Static declarations: `capability-providers.yaml` + `workers.yaml`
- Quota observation: CodexBar JSON, sanitized before projection
- Compute health: `omlxc status --json`
- Local compute route: `bos://compute/aetherforge/infer`
- Execution boundary: `dispatch=forbidden`; no selection, retry, fallback, model
  call, account switch, or user-configuration write
- Integrity boundary: embedded checksum detects accidental corruption; the
  independently recorded expected checksum detects payload replacement and is
  not a signature

## Real Read-only Probe

Observed at `2026-08-12T23:29:09Z`:

| Worker | CLI | Quota | Admission |
|---|---|---|---|
| codebuddy | observed | unknown / not configured | admitted (existing) |
| reasonix | observed | unknown / not configured | admitted (existing) |
| pi | observed | unknown / not configured | declared, disabled |
| oh-my-pi | observed | unknown / not configured | declared, disabled |
| opencode | observed | unknown / adapter nonzero | declared, disabled |
| claude-code | observed | unknown / confidence unknown | declared, disabled |
| crush | observed | unknown / not configured | declared, disabled |
| grok | observed | unknown / adapter nonzero | declared, disabled |
| mimo | observed | unknown / adapter nonzero | declared, disabled |
| agy | observed | unknown / not configured | declared, disabled |
| codex | observed | observed / exact | declared, disabled |
| kilo | unavailable / command missing | unknown | declared, disabled |

Compute observation was `error / probe_nonzero`. The current PATH resolves an
older `omlxc` CLI whose `status` command does not support the required JSON
contract; no text parsing or user-specific absolute-path fallback was used.
This does not invalidate the static AetherForge route, but it forbids claiming
local compute health.

Expected manifest checksum:

```text
3681d0792012fcd99da812819cdd2f501c18621867a3e5622a97910952417f92
```

The manifest was independently verified with `--expected-digest`; identity
fields were absent. The OpenCode configuration SHA-256 was identical before
and after the probe:

```text
3be330bb94b02c4b29599c1d5e06932b17a33d70c108de27d60e27c6866d9f9b
```

## Verification

- Root observer behavior: `17 passed`
- OMO worker admission and dispatch regressions: `27 passed`
- Root and OMO targeted Ruff: PASS
- Root and OMO `git diff --check`: PASS
- M4 MOF self-reflection checks: `5/5` PASS
- Write-owner audit: PASS
- Independent red-team review: APPROVE / CLEAR after remediation

The red team found and closed one real execution gap: an explicitly selected
disabled/declared worker could previously reach dispatch preparation before a
missing transport failed. OMO now rejects any worker that is not enabled and
admitted before deriving a dispatch ID or writing task, run, envelope, or
Workflow Mesh state. Default worker selection also ignores non-admitted
workers.

## Residuals

- Kilo remains declared but unavailable until a real executable is installed.
- cc-switch remains catalog-observation-only until a safe non-secret CLI
  contract exists.
- Most cloud quotas remain unknown; no proxy values are substituted.
- Repairing the PATH-level omlxc CLI contract is a separate runtime task. This
  BET intentionally does not modify machine configuration.
