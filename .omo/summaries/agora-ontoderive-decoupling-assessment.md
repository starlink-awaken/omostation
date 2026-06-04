# Phase 11 Wave 1 — Agora → OntoDerive decoupling assessment (T1.9)

> Scope: `projects/kairon/packages/agora/`
> Method: `ontoderive|OntoDerive` reference scan + file-role review

## Executive summary

Agora is coupled to OntoDerive primarily via **protocol/CLI + registry configuration**, not via direct Python imports:

- `ontoderive` string references:
  - **46** matches under production code/config: `projects/kairon/packages/agora/src/agora/**`
  - **153** matches across the full package (including tests)
- **0** direct Python imports were found (`import ontoderive` / `from ontoderive ...`) in the repository scan.

The coupling concentrates in a small set of files that encode:

- **CLI delegation** (`commands_pallas.py`, `commands.json` + `cli/parser.py`)
- **service registry / discovery metadata** (`registry.yaml`, `market.py`, `discovery.py`, `tenant.py`)
- **pipeline + e2e tests** (`tests/test_pipeline.py`, `tests/e2e/test_cross_project.py`) and pipeline config (`pipelines/builtin.json`)

Crucially, the coupling is **mostly command/protocol oriented**, not a dense web of direct Python imports. That is a good starting point for decoupling: the system already behaves more like a **service adapter** than a shared-library embedding.

## Where the coupling lives

| File | Ref count | Coupling type | Notes |
|---|---:|---|---|
| `src/agora/cli/commands_pallas.py` | 31 | CLI/process coupling | discovers `ontoderive` binary, runs `toolforge`, `derive`, `check`, `init` |
| `src/agora/registry.yaml` | 11 | registry/config coupling | service entry uses `mcp_url: "stdio://ontoderive"` + `health_url: "cli://ontoderive check"` |
| `src/agora/pipelines/builtin.json` | 6 | pipeline config coupling | pipeline steps reference `ontoderive.derive` / `ontoderive.check` |
| `tests/e2e/test_cross_project.py` | 7 | end-to-end coupling | cross-project expectations include OntoDerive CLI/project layout |
| `tests/test_pipeline.py` | 4 | pipeline expectation coupling | asserts `ontoderive.*` tool names |
| `src/agora/market.py` | 3 | registry/metadata coupling | hardcodes OntoDerive market metadata (`repo`, `entry`) |
| `src/agora/discovery.py` | 2 | runtime endpoint coupling | known-project metadata includes `mcp_endpoint: "stdio://ontoderive"` |
| `src/agora/commands.json` | 2 | CLI module coupling | routes `derive`/`reason` to `python -m ontoderive.cli derive` |
| `src/agora/tenant.py` | 1 | tenant/service roster coupling | example config includes `services: [minerva, ontoderive, sophia]` |

## Coupling classification

### 1. CLI/process coupling — **highest concentration**

Agora’s `pallas` commands discover the `ontoderive` executable and shell out to it. This is operationally convenient, but it means:

- Agora owns part of OntoDerive invocation UX
- environment/path issues surface as Agora problems
- contract drift is currently protected mostly by command behavior and tests

### 2. Discovery/registry coupling — **moderate**

Agora encodes OntoDerive as a known service:

- service name in tenant/market metadata
- stdio endpoint in discovery config

This is a cleaner seam than importing OntoDerive internals, but it still hardcodes routing assumptions in Agora.

### 3. Test coupling — **healthy but sticky**

The strongest cross-project assertions sit in tests. That is useful because decoupling work can preserve behavior if the tests are kept green, but it also means any contract change needs a deliberate migration path.

## Decoupling options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A. Keep CLI boundary, centralize adapter | Leave OntoDerive as an external tool, but move all invocation/discovery logic behind one Agora adapter | Low-risk, minimal behavior change | Still tied to CLI/runtime environment |
| B. MCP-first service contract (**recommended**) | Treat OntoDerive as a service endpoint (`derive`, `check`, etc.) and keep CLI only as a compatibility transport | Aligns with existing `stdio://ontoderive` discovery seam; easier to route via broader orchestration | Requires explicit contract definition and migration of CLI assumptions |
| C. Shared-library embedding | Import OntoDerive internals directly as Python APIs | Potentially richer typing and fewer subprocess hops | Tightest coupling, highest blast radius, least aligned with current architecture |

## Recommendation

Choose **Option B: MCP-first service contract**.

Why:

1. The current evidence already shows Agora treating OntoDerive like a discoverable external capability (`stdio://ontoderive`).
2. Most of the coupling pain is in command launching and environment assumptions, not in deep shared code.
3. Moving toward a protocol contract preserves today’s behavior while reducing direct CLI/process knowledge inside Agora.

## Minimal Wave 2 follow-up

If this decoupling is promoted beyond Wave 1 assessment, the smallest safe next step is:

1. define one explicit Agora↔OntoDerive contract surface (`derive`, `check`, `toolforge`)
2. wrap current CLI launching behind a single adapter
3. keep existing pipeline/e2e assertions as compatibility tests while swapping implementation behind the adapter
