# NextGen Edge-Cloud Compute & Autonomous Governance Architecture

> **Version**: 2.0.0 (Solidified in P1 & P2)  
> **SSOT References**: `etc/bos-services.yaml`, `projects/aetherforge/src/aetherforge/route/scheduler.py`, `projects/agora/src/agora/server/tools_bos.py`

## 1. Overview

OmoStation introduces an adaptive, hardware-aware edge-cloud hybrid compute layer (`AetherForge`) seamlessly integrated with a 4-corner consensus and physical evidence governance engine (`@B.D.S.K` Virtual Board in `Agora`).

```
+-------------------------------------------------------------------------+
|                  Layer 3: Autonomous Governance Layer                    |
|        @B.D.S.K Virtual Board (Mode-A Red-Blue Deliberation)            |
|       bos://persona/bdsk/evaluate (persist_adr=True -> ADR.md)         |
+-------------------------------------------------------------------------+
                                    ^ (Audit & Deliberation)
                                    |
+-------------------------------------------------------------------------+
|                   Layer 2: Adaptive Compute Layer                       |
|          AetherForge RouteScheduler (score_candidates pipeline)         |
|      - Apple Silicon HW Probe (hw_probe.py): sysctl / memory_pressure    |
|      - Dynamic affinity scoring -> oMLXC Edge vs Cloud Fallback         |
+-------------------------------------------------------------------------+
                                    ^ (Physical Hardware Telemetry)
                                    |
+-------------------------------------------------------------------------+
|                    Layer 1: Physical Edge Hardware                      |
|                  Mac Apple Silicon / Local Inference Node               |
+-------------------------------------------------------------------------+
```

---

## 2. P1: Hardware-Aware Edge Routing (`AetherForge`)

### 2.1 Apple Silicon Probing
`projects/aetherforge/src/aetherforge/hw_probe.py` exposes `get_apple_silicon_status()` which inspects:
- `sysctl -n hw.memsize`: Total physical RAM.
- `memory_pressure -Q`: Real-time macOS memory pressure (`normal`, `warn`, `critical`).

### 2.2 Dynamic Affinity Scheduling
In `RouteScheduler.score_candidates()`, candidate providers are scored across cost, speed, quota, and affinity.
- When `can_run_local_omlxc` is `True`, edge nodes receive an affinity score of `1.0`.
- When physical memory pressure enters `warn` or `critical`, edge affinity drops to `0.0`, routing compute automatically to cloud endpoints.

---

## 3. P2: B.D.S.K Virtual Board ADR Persistence (`Agora`)

### 3.1 4-Corner Deliberation & Debate Log
When calling `bos://persona/bdsk/evaluate` with `mode="deep"`, the engine generates a structured deliberation log across `@Builder` (MVP), `@Devil` (Anti-Fragile/Risk), `@Sage` (First-Principles), and `@Keeper` (SSOT/Compliance), including challenge/defense rounds (`debate_log`).

### 3.2 Automated Physical ADR Evidentiality
When `persist_adr=True` is provided:
1. The engine computes a standardized slug: `03xx-adr-<topic-slug>.md`.
2. It writes a Markdown document with complete YAML frontmatter (`title`, `status`, `date`, `decision-makers`) into `docs/decisions/` (or custom `adr_dir`).
3. The generated physical file path is returned in the response dictionary as `"saved_adr_path"`.

---

## 4. Governance & Verification Contract

All modifications and extensions to this architecture must obey:
1. **ADR-0203**: Requirement iterations MUST execute within an agent workflow run (`start -> claim -> verify -> closeout`).
2. **GaC Gate**: Pre-commit verification must pass `make gac-local-gate` and Swarm-D3 check (`0 violations`).
