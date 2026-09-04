---
title: acp-strategy
type: doc
---

# ACP Strategy

ACP is the preferred external Agent driving layer for DigitalBrainOS when a
tool supports it. Managed CLI remains the fallback.

## Goals

- support long-running agent tasks
- preserve work packet identity
- pass structured context
- collect artifacts
- keep audit trail

## Minimal Contract

```text
submit(packet)
status(run_id)
artifacts(run_id)
cancel(run_id)
```

## Current Priority

| Agent | ACP status | Decision |
|---|---|---|
| Copilot | `copilot --acp` detected | run `WP-2026-038` spike before more critical-path work |
| OpenCode | `opencode acp` detected | second ACP candidate after Copilot |
| Gemini | ACP advertised locally in registry/config candidates | verify after Copilot/OpenCode |
| Claude/Codex | candidate via ecosystem adapters | evaluate later |

## Required Metadata

```text
agent_id
role
work_packet_id
write_scope
risk_level
started_at
ended_at
status
artifact_paths
audit_trace
```

## Near-Term Fallback

Use managed CLI adapters only when ACP is unavailable or fails readiness. Raw
prompt mode is allowed only for exploratory, non-critical work.
