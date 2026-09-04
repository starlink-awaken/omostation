---
lifecycle: plan
owner: governance-team
last_updated: 2026-07-31
review-state: content-reviewed
metadata-migrated-at: 2026-07-31
content-reviewed-at: 2026-07-31
type: ssot
last_updated: 2026-09-03
---

# Governance Evolution Roadmap

> Human-readable navigation for the systemic governance evolution plan.
> Machine-readable SSOT: [`.omo/_truth/registry/governance-evolution-roadmap.yaml`](../.omo/_truth/registry/governance-evolution-roadmap.yaml).

## Purpose

The next governance phase is not another documentation pass. It makes governance visible,
traceable, and executable across Cockpit, BOS, AGCP, OMO, C2G, and MOF.

Use the registry and CLI for current state:

```bash
uv run --with pyyaml python bin/gac/governance-evolution.py status --json
uv run --with pyyaml python bin/gac/governance-evolution.py traces --json
uv run --with pyyaml python bin/gac/governance-evolution.py golden-paths --json
uv run --with pyyaml python bin/gac/governance-evolution.py packages --json
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
| Adaptive Digital 副官操作系统 (ADR-0300) | Information flow / Rules | `bos://memory/inbox/triage`, `bos://memory/inbox/draft`, `bos://persona/bdsk/evaluate` |

## Golden Paths

The canonical paths are registry-owned:

1. Agent change: `bootstrap -> start -> claim -> verify -> closeout -> compliance`.
2. Strategy ingress: `cockpit compass bet -> c2g bet -> OMO planned task -> AGCP run -> evidence`.
3. BOS invocation: `bos://governance/evolution/status -> traces -> verifier`.
4. Release package review: `packages -> unknown_count -> runtime/data exclusions -> AGCP closeout`.
5. Runtime projection sync: `state_stale event -> state-sync workflow -> omo state sync -> mutation ledger`.
6. Digital 副官/B.D.S.K. Decision Loop: `bos://memory/inbox/triage -> draft -> bos://persona/bdsk/evaluate -> sign-off`.

Do not duplicate the full steps here. Update the registry, then run:

```bash
uv run --with pyyaml python bin/gac/governance-evolution.py validate --json
```

## Closeout Rule

Any change to this roadmap must update the registry first. Markdown should explain and point;
the registry owns current initiatives, owners, entrypoints, verifiers, and operating rhythm.

## 成熟度口径对齐 (G10, 2026-08-24)

**maturity-scorecard (0-10, target 9.0) 是成熟度唯一 SSOT**。三方口径映射：

| 口径 | 工具 | 语义 | 映射 |
|------|------|------|------|
| 成熟度主口径 | `bin/gac/maturity-scorecard.py --json` | 六维 (evolvable/iterable/observable/traceable/troubleshootable/optimizable) 0-10 | target 9.0, gap 可算 |
| 运行时健康子视图 | `bin/compass_radar.py` → `health_score` (0-100) | 治理健康复合分 (governance/runtime/freshness) | health 70+ ≈ scorecard 8+, health 85+ ≈ scorecard 9+ |
| bet 交付验证态 | `docs/plans/3y-bet-ledger.yaml` → `bet-ledger.py status` | bet 交付状态 (candidate/active/done) | scorecard ≥9.0 ↔ T10-MATURITY bets 全 done |

报告"系统多成熟"一律引用 scorecard (唯一 SSOT)；health 是运行时健康子视图（可短时波动，
不代表成熟度回退）；台账验证态是 bet 交付进度（单个 bet 的 done 不等于整体 9.0）。

校验命令：

```bash
python3 bin/gac/maturity-scorecard.py --json   # 主口径
uv run --with pyyaml python bin/compass_radar.py --dry-run  # health 子视图
uv run --with pyyaml python bin/plan/bet-ledger.py status    # 台账验证态
```
