---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-04
last-reviewed: 2026-09-04
bet_id: BET-Y1Q4-T8-17
risk_level: L1
human_gate: false
value_indicator_policy: false
implementation_authorized: true
type: ssot
---

# W0 Unified Surface Protocol (USP v1) & Universal Card Primitives Specification

## 1. Decision & Background

Following the Tier-1 standardization of the CLI command system in Project Sovereign Command (PSC v1), all commands conform to strict ExitCode semantics, 8 orthogonal domains, and pure JSON output. However, the surface presentation layers (TUI, Web UI, MCP/A2A) currently construct bespoke representations of data, leading to presentation silos and duplicated state logic.

This specification formalizes the **Unified Surface Protocol (USP v1)** and **Universal Component & Card Primitives (UCS v1)**. Any backend service, BOS URI endpoint, or data broker exposing state to the presentation surface envelopes its payload into a standardized `SurfaceEnvelope`.

No heavy compilation runtime or external binary dependency is introduced. The reference protocol model is implemented as typed Python classes with full JSON Schema serialization, deserialization, and fail-closed validation.

## 2. Goal and Non-Goals

- **Goal:**
  - Define a strict `usp/v1` protocol schema and envelope structure.
  - Enforce the 8 orthogonal domains (`governance`, `workflow`, `memory`, `compute`, `bus`, `scene`, `system`, `user`).
  - Implement 5 universal interactive card primitives: `MetricGrid`, `DataTable`, `LogStream`, `DagGraph`, `ActionPanel`.
  - Provide typed validation, serialization, and round-trip parsing with zero side effects.
  - Keep deserialization overhead <1ms for standard card payloads.

- **Non-Goals:**
  - Does not replace low-level transport protocols (BOS URI, Agora SSE, HTTP remain transports).
  - Does not enforce specific frontend CSS frameworks or terminal rendering widgets (each renderer maps primitives to native widgets).
  - Does not mutate backend persistent business stores.

## 3. Data Contract & Envelope Schema

Every surface payload conforms to the `SurfaceEnvelope` schema:

```json
{
  "protocol": "usp/v1",
  "domain": "governance | workflow | memory | compute | bus | scene | system | user",
  "id": "surface::<domain>::<identifier>",
  "title": "<Human Readable Title>",
  "refresh_mode": "static | poll | stream",
  "stream_topic": "<optional bus topic or None>",
  "card_type": "metric_grid | data_table | log_stream | dag_graph | action_panel",
  "payload": {},
  "actions": []
}
```

### 3.1 Card Primitives

1. **`MetricGridCard`**:
   - `items`: List of `MetricItem(id, label, value, unit, status, delta, trend)`
   - `columns`: Layout hint (1..4)
2. **`DataTableCard`**:
   - `columns`: List of `TableColumn(key, title, align, format, sortable)`
   - `rows`: List of row objects (dict)
   - `primary_key`: String identifying the row key
   - `total_count`: Integer count
3. **`LogStreamCard`**:
   - `topic`: Streaming topic identifier
   - `max_buffer`: In-memory window size
   - `auto_scroll`: Boolean flag
   - `entries`: Initial log lines `LogEntry(timestamp, level, message, trace_id, metadata)`
4. **`DagGraphCard`**:
   - `nodes`: List of `GraphNode(id, label, status, kind, metadata)`
   - `edges`: List of `GraphEdge(source, target, label, kind)`
   - `layout`: Layout hint (`lr` | `tb`)
5. **`ActionPanelCard`**:
   - `actions`: List of `SurfaceAction(id, label, style, cli_command, bos_uri, confirm, params_schema)`

## 4. Verification Surface

- Pure unit tests covering protocol envelopes, primitive instantiations, JSON serialization, and edge-case validation errors.
- Target: `projects/cockpit/tests/test_surface_protocol.py` (100% pass, exit 0).
