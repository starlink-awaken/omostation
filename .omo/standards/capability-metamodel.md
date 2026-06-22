---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

# Capability metamodel

> Status: active
> Phase: 12
> Owner: Capability Ecosystem Layer

---

## Purpose

The capability metamodel defines the smallest durable record that lets OMO register, discover, bind, and audit workspace capabilities.

## Capability types

| Type | Meaning | Example |
|------|---------|---------|
| `capability` | A broad functional unit exposed by a project or component | `project.gbrain` |
| `skill` | A reusable agent workflow or instruction capability | `sharedbrain.skill-router` |
| `tool` | A callable local utility or MCP tool | `omo.task.validate` |
| `plugin` | A package that contributes tools or runtime behavior | browser plugin |
| `connector` | External integration or deferred ecosystem candidate | `sharedwork.gitnexus` |
| `cli` | Command-line entrypoint | `cli.omo` |
| `package` | Installable package or source package | `kairon.kronos` |

## Required fields

| Field | Type | Rule |
|-------|------|------|
| `id` | string | Globally unique, lowercase preferred |
| `type` | enum | `capability`, `skill`, `tool`, `plugin`, `connector`, `cli`, or `package` |
| `protocol` | enum | `cli`, `mcp`, `api`, `local`, `file`, or `doc` |
| `entrypoint` | string | File, command, module, URL, or documentation ref |
| `lifecycle` | enum | `active`, `experimental`, `deprecated`, or `external` |
| `metadata.description` | string | Human-readable summary |
| `metadata.tags` | list | Discovery tags |
| `metadata.scenario_tags` | list | Scenario binding tags |

## Governance rules

- A registry record is discovery evidence, not permission to install or mutate.
- External records default to `lifecycle: external` until an explicit admission review promotes them.
- Scenario binding must fail closed when a required capability is missing.
- Live SSOT promotion still requires human approval and a promotion envelope.
