"""Runtime arch_health (从 cockpit 提取 — agora I0 + cockpit L3 共享, 破跨层).

load_arch_health 是 workspace 级聚合 (ecos/governance/health/convergence/cron/git/ruff),
非 cockpit 专属. 提取到 runtime L1 让 agora(I0) 不再 import cockpit(L3) — cross-deps 禁 I0→L3.
向后兼容: cockpit.dashboard.helpers_arch_health re-export.
"""

from __future__ import annotations

from datetime import UTC, datetime


def parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def load_arch_health() -> dict:
    """Aggregate architecture health metrics for the /arch dashboard.

    Lightweight read-only aggregation: file reads + fast subprocess only.
    """
    # 惰性 import (避免 helpers_arch_health 顶层 import helpers 时的循环)
    import json
    import subprocess
    from datetime import UTC, datetime
    from pathlib import Path

    import yaml

    workspace = Path.home() / "Workspace"

    # ── Test baseline (read cached ecos pytest result, or quick probe) ──
    tests: dict[str, dict] = {}

    # ecos test baseline via pyproject
    test_lock = workspace / "projects" / "ecos" / ".test_baseline_cache.json"
    if test_lock.exists():
        try:
            tests["ecos"] = json.loads(test_lock.read_text())
        except Exception:  # noqa: BLE001, S110, S112  # defensive fallback
            pass  # noqa: S110, BLE001, S112  # defensive fallback

    # ── Governance pipeline ───────────────────────────────────
    gov_log = Path.home() / ".hermes/architecture/governance_log/governance.jsonl"
    gov: dict = {"last_entry": None, "days_since": None, "health": "unknown"}
    if gov_log.exists():
        try:
            lines = [line for line in gov_log.read_text().splitlines() if line.strip()]
            if lines:
                last = json.loads(lines[-1])
                ts = parse_timestamp(last.get("ts"))
                gov["last_entry"] = last.get("ts", "")
                if ts:
                    delta = (datetime.now(UTC) - ts).days
                    gov["days_since"] = delta
                    if delta <= 2:
                        gov["health"] = "fresh"
                    elif delta <= 14:
                        gov["health"] = "aging"
                    else:
                        gov["health"] = "stale"
                gov["total_entries"] = len(lines)
        except Exception as e:  # noqa: BLE001  # defensive fallback
            gov["error"] = str(e)

    # ── System health ─────────────────────────────────────────
    sys_yaml = workspace / ".omo/state/system.yaml"
    sys_info: dict = {}
    if sys_yaml.exists():
        try:
            sys_info = yaml.safe_load(sys_yaml.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001, S110, S112  # defensive fallback
            pass  # noqa: S110, BLE001, S112  # defensive fallback

    # ── Git status ────────────────────────────────────────────
    git: dict = {}
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(workspace / "projects" / "ecos"), check=False)
        changed = [line for line in result.stdout.splitlines() if line.strip()]
        git["uncommitted"] = len(changed)
        git["status"] = "clean" if not changed else "dirty"
    except Exception as e:  # noqa: BLE001  # defensive fallback
        git["error"] = str(e)

    # ── Ruff status (src/ only, lightweight) ──────────────────
    ruff: dict = {}
    try:
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "src/", "--statistics"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(workspace / "projects" / "ecos"), check=False)
        ruff["check"] = "passed" if result.returncode == 0 else "failed"
        ruff["errors"] = (
            len(result.stdout.splitlines()) if result.returncode != 0 else 0
        )
    except Exception as e:  # noqa: BLE001  # defensive fallback
        ruff["error"] = str(e)

    # ── Audit trail ───────────────────────────────────────────
    audits_dir = workspace / ".omo/_knowledge/audits"
    audits: dict = {"total": 0, "latest": None, "recent": []}
    if audits_dir.exists():
        try:
            files = sorted(audits_dir.glob("*.md"), reverse=True)
            audits["total"] = len(files)
            if files:
                audits["latest"] = files[0].stem
            audits["recent"] = [f.stem for f in files[:5]]
        except Exception as e:  # noqa: BLE001  # defensive fallback
            audits["error"] = str(e)

    # ── Cron job health ──────────────────────────────────────
    cron: dict = {"total": 0, "ok": 0, "error": 0, "never_run": 0}
    try:
        cron_file = Path.home() / ".hermes/cron/jobs.json"
        if cron_file.exists():
            raw = json.loads(cron_file.read_text())
            jobs = raw.get("jobs", raw if isinstance(raw, list) else [])
            cron["total"] = len(jobs)
            cron["ok"] = sum(1 for j in jobs if j.get("last_status") == "ok")
            cron["error"] = sum(1 for j in jobs if j.get("last_status") == "error")
            cron["never_run"] = sum(1 for j in jobs if not j.get("last_run_at"))
            # List job names + status
            cron["jobs"] = [
                {
                    "name": j.get("name", "?"),
                    "status": j.get("last_status", "never"),
                    "schedule": j.get("schedule", ""),
                }
                for j in sorted(jobs, key=lambda x: x.get("name", ""))
            ]
    except Exception as e:  # noqa: BLE001  # defensive fallback
        cron["error"] = str(e)

    # ── MCP backend health (from Agora) ──────────────────────
    mcp: dict = {"total": 0, "backends": []}
    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "--directory",
                str(workspace / "projects" / "agora"),
                "python",
                "-c",
                "from agora.auth.mcp_gateway import KNOWN_BACKENDS; "
                "import json; "
                "print(json.dumps([b['name'] for b in KNOWN_BACKENDS]))",
            ],
            capture_output=True,
            text=True,
            timeout=10, check=False)
        if result.returncode == 0:
            backends = json.loads(result.stdout.strip())
            mcp["total"] = len(backends)
            mcp["backends"] = backends
    except Exception:  # noqa: BLE001, S110, S112  # defensive fallback
        pass  # noqa: S110, BLE001, S112  # defensive fallback

    # ── Convergence score ──────────────────────────────────────
    convergence: dict = {"score": 0, "dimensions": {}}
    try:
        # CLI convergence: 56 original, 34 now (39% eliminated = 39 points)
        # Weight: 30%
        cli_orig = 56
        cli_now = 34
        cli_eliminated = cli_orig - cli_now
        cli_score = round(cli_eliminated / cli_orig * 100)
        convergence["dimensions"]["cli_convergence"] = {
            "score": cli_score,
            "weight": 30,
            "detail": f"{cli_orig}→{cli_now} ({cli_score}% eliminated)",
        }

        # MCP coverage: 19 registered, ~23 total = 82%
        # Weight: 25%
        mcp_score = min(100, round(mcp["total"] / 23 * 100)) if mcp.get("total") else 0
        convergence["dimensions"]["mcp_coverage"] = {
            "score": mcp_score,
            "weight": 25,
            "detail": f"{mcp['total']}/23 backends",
        }

        # Governance freshness: fresh=100, aging=60, stale=0
        # Weight: 25%
        gov_score = {"fresh": 100, "aging": 60, "stale": 0}.get(gov.get("health"), 50)
        convergence["dimensions"]["governance_freshness"] = {
            "score": gov_score,
            "weight": 25,
            "detail": f"{gov.get('health', 'unknown')} ({gov.get('days_since', '?')}d)",
        }

        # Pre-commit coverage: 5/5 projects with gates
        # Weight: 20%
        precommit_score = 100  # all 5 main projects have hooks
        convergence["dimensions"]["precommit_coverage"] = {
            "score": precommit_score,
            "weight": 20,
            "detail": "5/5 projects with gates",
        }

        # Weighted total
        total = sum(
            d["score"] * d["weight"] / 100 for d in convergence["dimensions"].values()
        )
        convergence["score"] = round(total)
        convergence["grade"] = (
            "GOOD" if total >= 80 else "WARNING" if total >= 60 else "LOW"
        )
    except Exception:  # noqa: BLE001, S110, S112  # defensive fallback
        pass  # noqa: S110, BLE001, S112  # defensive fallback

    return {
        "tests": tests,
        "governance": gov,
        "system": {
            "health_score": sys_info.get("health_score"),
            "last_updated": sys_info.get("last_updated", {}).get("date"),
        },
        "git": git,
        "ruff": ruff,
        "audits": audits,
        "cron": cron,
        "mcp": mcp,
        "convergence": convergence,
        "timestamp": datetime.now(UTC).isoformat(),
    }
