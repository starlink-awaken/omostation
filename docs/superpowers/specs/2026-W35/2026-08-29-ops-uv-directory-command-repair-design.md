---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-49
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Service Gateway uv directory command repair

## Objective

Make the canonical Workspace Service Gateway compile runnable commands for
services whose program interpreter is `uv` and whose entrypoint is a project
directory, including the registered `mcp.agora` service.

## Contract

- A directory entrypoint compiles to `uv run --directory <entrypoint> <args>`.
- A file/module entrypoint keeps the existing `uv run <entrypoint> <args>` form.
- `services.yaml` remains the sole service declaration; no second command
  registry or service-specific hardcode is allowed.
- The change is code/test only. It must not write, load, unload, or mutate host
  plist files, launchd state, runtime data, or service processes.

## Acceptance

- A regression test proves directory and non-directory uv entrypoints compile
  to their respective canonical argv forms.
- `ops up mcp.agora --dry-run` prints a runnable command using the registered
  `projects/agora` directory and `agora-mcp --sse` arguments.
- Focused tests, Python syntax, and the default GaC gate pass.
- Host runtime remains untouched; actual service startup is a separate
  operational activity and is not evidence for this BET.
