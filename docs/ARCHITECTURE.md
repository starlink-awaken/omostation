# Agora Architecture

> Architecture overview for **Agora**. For the full workspace architecture, see [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md).

## Responsibilities

Agora is part of the eCOS v6 workspace. See [`../README.md`](../README.md) for a one-line description and [`../CAPABILITY-MAP.md`](../CAPABILITY-MAP.md) for capability mapping.

## Key Surfaces

- `src/agora/mcp/resolver/` — BOS URI resolver
- `src/agora/auth/` — authentication
- `src/agora/bus/` — message bus
- `etc/bos-services.yaml` — BOS service registry

## Design Notes

- Runtime facts (counts, ports, health) are intentionally not maintained here. Use the workspace registries and project source as the truth.
- For boundaries and call chains, read [`../BOUNDARY.md`](../BOUNDARY.md) and [`../CALLCHAIN.md`](../CALLCHAIN.md).
- For developer rules, read [`../AGENTS.md`](../AGENTS.md).

## Component Overview

```mermaid
graph TD
    User([User / Agent])
    N0[BOS Registry]
    N1[Resolver]
    N2[Auth]
    Core[Bus]
    N0 --> N1
    N1 --> N2
    N2 --> Core
    User --> Core
```

- Arrows show typical interaction flow, not strict call direction.
- See [`../CALLCHAIN.md`](../CALLCHAIN.md) for detailed call chains.
