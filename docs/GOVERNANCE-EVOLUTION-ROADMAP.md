# Governance Evolution Roadmap

> Human-readable navigation for the systemic governance evolution plan.
> Machine-readable SSOT: [`.omo/_truth/registry/governance-evolution-roadmap.yaml`](../.omo/_truth/registry/governance-evolution-roadmap.yaml).

## Purpose

The next governance phase is not another documentation pass. It makes governance visible,
traceable, and executable across Cockpit, BOS, AGCP, OMO, C2G, and MOF.

Use the registry and CLI for current state:

```bash
uv run --with pyyaml python bin/governance-evolution.py status --json
uv run --with pyyaml python bin/governance-evolution.py traces --json
uv run --with pyyaml python bin/governance-evolution.py golden-paths --json
uv run --with pyyaml python bin/governance-evolution.py packages --json
```

Human entry:

```bash
uv run --project projects/cockpit cockpit governance evolution status --json
```

Agent/BOS entries:

- `bos://governance/evolution/status`
- `bos://governance/evolution/validate`
- `bos://governance/evolution/traces`
- `bos://governance/evolution/golden-paths`
- `bos://governance/evolution/packages`
- `bos://governance/evolution/loop`

## Iteration Themes

| Theme | System Lever | Runtime Proof |
|-------|--------------|---------------|
| Worktree/release convergence | Information flow | `agent-workflow status`, `make gac-local-gate` |
| Cockpit governance status plane | Information flow | `cockpit governance evolution status --json` |
| Claim policy tiering | Rules | required/advisory tiers in `agent-workflow status` claim coverage |
| BOS governance evolution routes | Information flow | Agora BOS registry tests |
| Capability traceability | Information flow | `governance-evolution traces --json` |
| OMO/C2G/MOF operating rhythm | Feedback delays | `mof-state-bridge`, C2G/OMO help gates |
| Golden Path E2E | Rules | `governance-evolution golden-paths --json` |
| Entry point convergence | Rules | Cockpit/AGCP/GaC entry contracts |
| Runtime projection convergence | Feedback delays | `uv run --project projects/omo omo state sync --dry-run --json` |

## Golden Paths

The canonical paths are registry-owned:

1. Agent change: `bootstrap -> start -> claim -> verify -> closeout -> compliance`.
2. Strategy ingress: `cockpit compass bet -> c2g bet -> OMO planned task -> AGCP run -> evidence`.
3. BOS invocation: `bos://governance/evolution/status -> traces -> verifier`.
4. Release package review: `packages -> unknown_count -> runtime/data exclusions -> AGCP closeout`.
5. Runtime projection sync: `state_stale event -> state-sync workflow -> omo state sync -> mutation ledger`.

Do not duplicate the full steps here. Update the registry, then run:

```bash
uv run --with pyyaml python bin/governance-evolution.py validate --json
```

## Closeout Rule

Any change to this roadmap must update the registry first. Markdown should explain and point;
the registry owns current initiatives, owners, entrypoints, verifiers, and operating rhythm.
