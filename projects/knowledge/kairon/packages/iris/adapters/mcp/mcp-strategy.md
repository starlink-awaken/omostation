---
title: mcp-strategy
type: doc
---

# MCP Strategy

MCP is the preferred tool and service exposure layer for DigitalBrainOS. It does
not replace ACP; ACP drives Agent sessions, while MCP exposes capabilities to
Agents and the Conductor.

## Role of MCP

- expose KOS search
- expose Minerva research
- expose Sophia paradigm compilation
- expose SharedBrain runtime APIs
- expose Agora routing
- expose controlled local tools
- expose shared dashboard, timeline, run lookup, and artifact lookup

## Registry

MCP servers should be registered through the Connection and Extension Fabric.
Agora is the likely first implementation of the MCP hub.

## Guardrails

- no secret leakage into tool descriptions
- high-risk tools disabled by default
- every tool declares schema and risk level
- tool calls produce audit events
- external write tools require approval

## Integration With ACP

ACP adapters may give external Agents access to a curated MCP tool set, but the
tool set must be selected by the Conductor per work packet. High-risk MCP tools
remain disabled unless explicitly approved.

## First Tool Plane

| Tool | Risk | Output Policy |
|---|---|---|
| `dbos.dashboard.get_snapshot` | low | full JSON snapshot |
| `dbos.timeline.list_events` | low | paginated filtered events |
| `dbos.timeline.get_event` | low | one event |
| `dbos.run.list` | low-medium | metadata only by default |
| `dbos.run.lookup` | low-medium | metadata plus artifact refs |
| `dbos.artifact.lookup` | medium | metadata/hash/summary, no full body by default |
| `dbos.work_packet.list` | low | metadata |
| `dbos.work_packet.get` | low | scoped work packet body |
| `dbos.schema.list` | low | schema index |
| `dbos.schema.get` | low | schema body |
| `kos.search.readonly` | medium | summary and refs |
| `sharedbrain.query.readonly` | medium | summary and refs |

Every MCP tool schema must declare stable id, version, input schema, output
schema, risk level, permission scope, audit policy, redaction policy,
approval requirement, and trace fields.
