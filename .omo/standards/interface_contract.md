---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

# Interface Contract (架构版本见根 ARCHITECTURE.md)

This file is the **Single Source of Truth (SSOT)** for L0 and L3 communication models.
The `omo-parser` will dynamically parse these markdown tables to generate Pydantic models at runtime.

## Model: TaskObject
Used at the L3 Entry Bridge to standardize incoming tasks before they hit the L2 Kernel.

| Field | Type | Description |
|---|---|---|
| id | string | Unique identifier for the task |
| intent | string | The core user intent |
| context | string | Environmental or session context |
| target_domain | string | Which KOS domain this task targets |
| status | string | Task lifecycle state (pending, running, complete) |

## Model: AgentMessage
Used at the I0 Integration Fabric (Agora) for intra-layer and inter-agent communication.

| Field | Type | Description |
|---|---|---|
| source | string | Sender identifier |
| target | string | Recipient identifier |
| action | string | The operation to perform (e.g., read, write) |
| payload | dict | The arbitrary JSON payload |
| session_id | string | Tracing ID for X3 value tracking |
| metadata | dict | Ephemeral state (e.g. bypass_cost flag) |
