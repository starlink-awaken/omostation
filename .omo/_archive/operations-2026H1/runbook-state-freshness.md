---
title: "runbook-state-freshness"
type: runbook
owner: governance-team
lifecycle: contract
last_updated: 2026-08-23
---
# Runbook: State Freshness Expired

## Symptom
- `bin/gac/state-freshness-check.py` (or `make state-freshness` strict
  gate) returns expired files
- BRIEF.md / health.yaml show `freshness_score: 0/100` or "files_stale"
- `bin/compass_radar.py` flags "freshness_score: 0/100 (regenerated-when)"
- Logs show `.omo/_truth/registry/...` or `.omo/state/...` hasn't been
  refreshed in > 7d

## 5-state-file freshness contract

These 5 files must stay fresh (≤ 24h old):
| Path | Owner | Writer |
|---|---|---|
| `.omo/state/health.yaml` | governance-team | `bin/compass_radar.py` |
| `.omo/state/system.yaml` | runtime-team | `omo state sync` |
| `.omo/state/system_health.yaml` | resident | `bin/ssot/system-health-check.py` |
| `.omo/_control/governance-data.json` | governance-team | `omo state sync` |
| `.omo/_control/debt-dashboard/current.yaml` | debt-team | `omo debt refresh` |

`bin/gac/state-freshness-check.py` is the canonical verifier.

## 排查 (Diagnostic)

```bash
# 1. Identify which file is stale
bin/gac/state-freshness-check.py --json | python3 -c "
import sys, json
d = json.load(sys.stdin)
for r in d['results']:
    if not r['ok']:
        print(f\"STALE: {r['path']} age={r['age_hours']:.1f}h\")
"

# 2. Check the writer cron / launchd job is alive
launchctl list | grep -E "omo|cockpit|aetherforge"

# 3. Manual refresh
make state-sync  # canonical refresh command
```

## 修复 (Resolution)

### Option A: one-shot manual refresh

```bash
make state-sync
uv run --project projects/omo omo state refresh --json
uv run --project projects/omo omo debt refresh --now "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

### Option B: install missing cron / launchd job

```bash
# state writer (omo state sync) — runs every 6h on cron
uv run --project projects/omo omo cron install

# debt dashboard refresh — runs daily
uv run --project projects/omo omo debt install-cron

# Verify
launchctl list | grep omo
```

### Option C: file is genuinely orphaned (rare)

If a file hasn't been refreshed in > 7d AND no cron job exists for it,
the writer has been deprecated. Check `git log -- bin/...` for the
file's producer. Either:
- Restore the writer (`git revert` the deprecation)
- Archive the SSOT (`(archive-ssot.py is a planned future tool; use git revert for now)`)

## Prevention

- Add cron check: `make gac-local-gate` includes freshness check (PR
  #1989 wired `state-freshness-check` as ci_only gate)
- Monitor: `bin/gac/health-trend-chart.py` shows freshness in trend
- Alert: `bin/gac/governance-alert-dispatch.py` emits observability
  event when freshness drops below 80

## Related

- [`runbook-agent-silent.md`](runbook-agent-silent.md) — agent daemon down
- [`cleanup-rounds-2026-08-22.md`](cleanup-rounds-2026-08-22.md) — round 3 (debt mirror fix)
- PR #1936 — original debt dashboard mirror fix
