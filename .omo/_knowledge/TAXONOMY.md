---
status: ACTIVE
lifecycle: reference
owner: governance-team
last-reviewed: 2026-07-09
related:
  - TELOS.md
  - zones.yaml
  - ../CLAUDE.md
  - ../../../AGENTS.md
  - ../../../BRIEF.md
---

# Knowledge Taxonomy — omostation Concepts in PAI Frame

This document maps every existing omostation concept to its PAI/LifeOS
analog. Use it to:
1. Find what already exists (don't reinvent)
2. Identify gaps where PAI concepts would add value
3. Pick the right term when introducing a new idea

> See also: `TELOS.md` (the 6-section North Star), `zones.yaml`
> (containment zones), `ISA/` (cross-cutting task artifacts).

## 1. Decision Records & Ideas

| omostation | PAI analog | Notes |
|---|---|---|
| `.omo/_knowledge/decisions/ADR-NNNN-*.md` | MENTAL_MODELS.md | Same role: durable principles. ADR has stricter frontmatter (P7X). |
| `.omo/_knowledge/standards/` | WISDOM.md | Practices, conventions, "always do X". |
| `.omo/_knowledge/patterns/` | (PAI has no direct analog) | Concrete code patterns, copied as templates. |
| `.omo/_knowledge/designs/` | (architecture sketches) | Pre-ADR brainstorms. |
| `.omo/_knowledge/drafts/` | (PAI has no direct analog) | In-progress ADRs / specs. |

## 2. Work & State

| omostation | PAI analog | Notes |
|---|---|---|
| `.omo/_delivery/agent-workflows/runs/{run-id}.yaml` | MEMORY/WORK/{slug}/TASK.md | A workflow run record. Both track a single task instance. |
| `.omo/_delivery/audit-rollout/` | MEMORY/LEARNING/{pattern}/ | Per-cycle / per-pattern outcomes. |
| `.omo/_delivery/evidence-smoke/` | OBSERVABILITY/*.jsonl | Tool execution logs (CI smoke runs). |
| `.omo/_delivery/scenarios/` | (no direct analog) | Replayable test scenarios. |
| `.omo/state/system.yaml` + `health.yaml` | MEMORY/STATE/work.json | Live system state snapshot. |
| `.omo/_control/governance-overlay/` | (governance catalog) | Live state of the governance machinery itself. |

## 3. Governance & Process

| omostation | PAI analog | Notes |
|---|---|---|
| `.omo/_control/agent-workflows/` | settings.json (hooks) | Agent workflow definitions — like PAI hook specs. |
| `bin/gac/gac-local-gate.py` | Inspector / Hook | CI gate. PAI calls these "Inspectors" (5 of them). |
| `bin/verify-omo.sh` | (no direct analog) | PAI's `bin/validate-protected.ts` is closest. |
| `bin/ssot/adr-coverage.py` | (no direct analog) | PAI does not have an ADR-coverage check explicitly. |
| `bin/gac/governance-evolution.py` | (release pipeline) | Maps to PAI's "Shadow Release Pipeline". |
| `bin/gac/governance-semantic-gate.py` | RulesInspector | Validates actions against PAI_SYSTEM_PROMPT + CLAUDE.md (P7X). |

## 4. Knowledge & Memory

| omostation | PAI analog | Notes |
|---|---|---|
| `.omo/_knowledge/analysis/` | (no direct analog) | One-off research/analysis outputs. |
| `.omo/_knowledge/architecture/` | ArchitectContext.md | Architectural context. |
| `.omo/_knowledge/audits/` | (one-shot audits) | Like PAI's "RedTeam" output. |
| `.omo/_knowledge/convergence.yaml` | (no direct analog) | Convergence state across multiple sources. |
| `.omo/_knowledge/governance-history.jsonl` | MEMORY/OBSERVABILITY/*.jsonl | Long-term event log. |
| `.omo/_knowledge/process/` | (no direct analog) | Process documentation. |
| `.omo/_knowledge/retrospectives/` | LEARN phase output | Post-mortems / lessons. |
| `.omo/_knowledge/reviews/` | (no direct analog) | Periodic reviews. |
| `.omo/_knowledge/summaries/` | (no direct analog) | Periodic summary outputs. |
| `.omo/_knowledge/superpowers/` | (no direct analog) | Custom superpowers / skills the agent has. |
| `.omo/_knowledge/task-prompts/` | (no direct analog) | Per-task prompt templates. |
| `.omo/_knowledge/vision-roadmap/` | STRATEGIES.md | Long-term strategic direction. |
| `.omo/_knowledge/usage/` | (no direct analog) | Usage telemetry. |

## 5. Reference & Standards

| omostation | PAI analog | Notes |
|---|---|---|
| `.omo/_knowledge/reference/` | (no direct analog) | API/format references. |
| `.omo/_knowledge/standards/` | WISDOM.md | Conventions, "always do X". |
| `.omo/_knowledge/management/` | (no direct analog) | Project management artifacts. |
| `.omo/_knowledge/governance/` | (rules catalog) | Governance rule definitions. |
| `.omo/_knowledge/vision-roadmap/` | MISSION.md | North Star. |

## 6. Living State (transient, not in releases)

| omostation | PAI analog | Notes |
|---|---|---|
| `.omo/state/system.yaml` | MEMORY/STATE/work.json | Current health snapshot. **Containment zone: memory.** |
| `.omo/state/health.yaml` | (live observability) | Per-cron-freshness health. **Containment zone: memory.** |
| `.omo/state/budget_overrides.jsonl` | (no direct analog) | Daily runtime state. **Containment zone: memory.** |
| `.omo/_delivery/agent-workflows/runs/` | MEMORY/WORK/{slug}/ | Live workflow runs. **Containment zone: memory.** |
| `.omo/events/` (e.g. omo-events.jsonl) | OBSERVABILITY/*.jsonl | Event log. **Containment zone: memory.** |

## 7. Tools (the agent's hands)

| omostation | PAI analog | Notes |
|---|---|---|
| `bin/` (40+ scripts) | Packs/{Name}/src/Tools/ | Same role. **PAI has stricter Pack structure** (SKILL.md+INSTALL.md+VERIFY.md). |
| `bin/omo` | PAI SKILL.md routing | Omo CLI itself. |
| `projects/{name}/src/` | (PAI has no analog — flat workspace) | Real project source. |
| `projects/{name}/tests/` | VERIFY.md bash checks | Test files. |

## 8. Containment Zones (see `zones.yaml`)

| Zone | Path pattern | Enforcement |
|---|---|---|
| `internal` | `^.omo/_control/`, `^.omo/_knowledge/decisions/draft/`, `^.omc/` | block |
| `lifecycle` | `^.omo/_knowledge/decisions/archived/`, `^.omo/_deprecated/` | warn |
| `memory` | `^.omo/state/`, `^.omo/_knowledge/STATE/` | warn (release snapshots only) |
| `release_evidence` | `^.omo/_delivery/`, `^.omo/_knowledge/decisions/ACTIVE/`, `^CHANGELOG.md$` | block |

## 9. Skills (agent capabilities)

| omostation | PAI analog | Notes |
|---|---|---|
| `.omo/_knowledge/superpowers/` | Packs/{Name}/src/SKILL.md | Omostation has skills but **not PAI Pack structured**. |
| `.omo/_knowledge/task-prompts/` | (no direct analog) | Per-task prompt templates. |
| `bin/ssot/PACKS/` | Packs/{Name}/ | PAI Pack structured. |

## 10. The 4 Concepts We Add in This Rollout

1. **TELOS** (`.omo/_knowledge/TELOS.md`) — 6 sections, single source of North Star
2. **PACK** (`.omo/_knowledge/PACKS/`) — SKILL.md+INSTALL.md+VERIFY.md+src/ structure for tools
3. **Containment zones** (`.omo/_knowledge/zones.yaml`) — path-based DLP
4. **ISA** (`.omo/_knowledge/ISA/`) — 12-section artifact for cross-cutting changes

## 11. Concepts We Do NOT Adopt (and why)

| PAI concept | Why not |
|---|---|
| 7-phase Algorithm (Observe→Learn) | omo_daemon already has 3 implicit steps (audit→history→sync). Adding 7 phases is ceremony. |
| Pulse daemon (always-on) | We have agent-workflows + cron + CI. Single-user, no need for always-on process. |
| 5 Inspectors (Pattern/Egress/Rules/Injection/Prompt) | We have 1 (omo cli lint) + 5 git hooks. The Inspectors are about multi-agent coordination we don't need. |
| Effort Tiers E1-E5 | Multi-agent planning aid. Single agent doesn't need formal effort tiering. |
| Voice server (ElevenLabs) | macOS-specific, single-user affordance, not relevant. |
| TELOS-driven LLM filtering at runtime | We have brief/AGENTS that the LLM already reads. A second "TELOS filter" would be redundant. |

## 12. Cross-References

- `TELOS.md` — the 6-section North Star this taxonomy serves
- `zones.yaml` — the containment zones mentioned in section 8
- `../CLAUDE.md` — operational instructions
- `../../../AGENTS.md` — agent operating guide
- `../../../BRIEF.md` — project brief
- `../INDEX.md` — knowledge index
