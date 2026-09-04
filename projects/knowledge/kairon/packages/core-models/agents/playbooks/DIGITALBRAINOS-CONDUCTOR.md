---
title: DIGITALBRAINOS-CONDUCTOR
type: doc
---

# DigitalBrainOS Conductor Playbook

## Purpose

This playbook defines how the Conductor drives DigitalBrainOS planning and
execution across humans, local CLIs, and multiple AI agents.

## Conductor Loop

```text
Sense → Frame → Decompose → Dispatch → Monitor → Integrate → Evaluate → Record
```

## Step 1: Sense

Collect current state:

- active work packets
- changed files
- blocked dependencies
- available agents/tools
- relevant project state
- latest decisions

## Step 2: Frame

Turn the user's intent into:

- strategic objective
- success criteria
- constraints
- risk level
- required artifacts

## Step 3: Decompose

Create work packets with:

- disjoint write scopes
- clear owner role
- acceptance criteria
- validation method
- dependency order

## Step 4: Dispatch

Choose execution path:

| Path | Use |
|---|---|
| local execution | simple file/doc/script work |
| Codex | codebase implementation and review |
| Claude | narrative design, review, reasoning |
| Gemini/Qwen/Ollama | alternate analysis or private summarization |
| AgentMesh | agent execution routing |
| Agora/MCP | tool and service execution |

## Step 5: Monitor

Track:

- packet status
- artifact paths
- elapsed time
- conflicts
- risk events
- validation failures

## Step 6: Integrate

Merge outputs into:

- blueprint docs
- schemas
- adapters
- backlog
- ADRs
- reflection records

## Step 7: Evaluate

Check:

- acceptance criteria
- consistency with object model
- governance risk
- validation evidence
- downstream impact

## Step 8: Record

Update:

- work packet status
- decision records
- roadmap
- failure or reflection notes
- asset map if boundaries changed

## Anti-Patterns

- dispatching agents before work packets exist
- overlapping write scopes
- accepting outputs without validation
- letting a CLI output become durable truth without review
- bypassing approval for high-risk operations

