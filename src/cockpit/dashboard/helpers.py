"""Data-fetching helpers for the Cockpit Dashboard."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from cockpit.dashboard.constants import (
    BOS_METRICS_PATH,
    M0_SNAPSHOT_PATH,
    OMO_ROOT,
    PROJECT_ROOT,
)
from cockpit.web.auth import get_subservice_token

from .helpers_arch_health import load_arch_health

# P110-E (TASK-F7114ABA 治本): load_compute / load_arch_health 拆分
from .helpers_compute import load_compute

# ─── File I/O ──────────────────────────────────────────────────


def read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # defensive fallback
        return {}


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


# ─── Layer status ──────────────────────────────────────────────


def fetch_http(source: dict) -> dict:
    """Fetch a layer's status via HTTP."""
    import urllib.request

    try:
        token = get_subservice_token()
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["X-Api-Key"] = token
        req = urllib.request.Request(source["url"], method="GET", headers=headers)  # noqa: S310
        with urllib.request.urlopen(req, timeout=3) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
        return {
            "layer": source["layer"],
            "name": source["name"],
            "status": data.get("status", "ok"),
            "data": data,
        }
    except Exception as e:  # defensive fallback
        return {
            "layer": source["layer"],
            "name": source["name"],
            "status": "down",
            "error": str(e),
        }


def read_m0_snapshot() -> dict:
    """Read the M0 runtime snapshot from the local YAML file."""
    try:
        m0_path = M0_SNAPSHOT_PATH
        if not m0_path.exists():
            return {
                "layer": "L0",
                "name": "ecos",
                "status": "down",
                "error": f"M0 snapshot not found at {m0_path}",
            }
        raw = yaml.safe_load(m0_path.read_text(encoding="utf-8"))
        return {
            "layer": "L0",
            "name": "ecos",
            "status": "ok",
            "data": {
                "source": "m0_snapshot",
                "snapshot": {
                    "version": raw.get("version"),
                    "generated_at": str(raw.get("generated_at", "")),
                    "daemon": raw.get("daemon", {}),
                    "m1_node_count": raw.get("m1_node_count", 0),
                    "protocols": raw.get("protocols", {}),
                },
            },
        }
    except Exception as e:  # defensive fallback
        return {
            "layer": "L0",
            "name": "ecos",
            "status": "down",
            "error": f"M0 snapshot read error: {e}",
        }


def fetch_layer_status(source: dict) -> dict:
    """Fetch a single layer's status — try direct import first, then HTTP."""

    # I0 Agora — always HTTP (separate process)
    if source["layer"] == "I0":
        return fetch_http(source)

    # L2 omo — try direct import
    if source["layer"] == "L2":
        try:
            from cockpit.adapters.omo import load_json as _omo_load

            omo_dir = Path(os.environ.get("OMO_DIR", str(Path.home() / "Workspace" / ".omo")))
            system = _omo_load(omo_dir / "state" / "system.yaml")
            return {
                "layer": "L2",
                "name": "omo",
                "status": "ok",
                "data": {"system": system, "source": "direct_import"},
            }
        except Exception:  # defensive fallback
            return fetch_http(source)

    # L1 runtime — try direct import
    if source["layer"] == "L1":
        try:
            from cockpit.adapters.runtime import i0_status

            status = i0_status() if i0_status else {}
            return {
                "layer": "L1",
                "name": "runtime",
                "status": "ok",
                "data": {
                    "summary": {"total_layers": 3, "healthy": 1},
                    "status": status,
                    "source": "direct_import",
                },
            }
        except Exception:  # defensive fallback
            return fetch_http(source)

    # L0 ecos — read from M0 snapshot file
    if source["layer"] == "L0":
        return read_m0_snapshot()
    return fetch_http(source)


# ─── Cost estimation ───────────────────────────────────────────


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    model_lower = (model or "unknown").lower()
    cost_map = {
        "gpt-4o-mini": {"input": 0.0015, "output": 0.006},
        "gpt-4o": {"input": 0.01, "output": 0.03},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        "deepseek-v4-flash": {"input": 0.0005, "output": 0.002},
        "deepseek-v4": {"input": 0.002, "output": 0.008},
        "gemini-1.5-pro": {"input": 0.0035, "output": 0.0105},
        "ollama": {"input": 0.0, "output": 0.0},
        "lmstudio": {"input": 0.0, "output": 0.0},
        "mock-model": {"input": 0.0, "output": 0.0},
    }
    rates = None
    for key in sorted(cost_map, key=len, reverse=True):
        if model_lower.startswith(key):
            rates = cost_map[key]
            break
    if rates is None:
        rates = {"input": 0.002, "output": 0.008}
    return round((input_tokens / 1000) * rates["input"] + (output_tokens / 1000) * rates["output"], 6)


def infer_node(model: str, provider_name: str | None) -> dict[str, str]:
    model_lower = (model or "").lower()
    provider_lower = (provider_name or "").lower()
    if "ollama" in model_lower:
        return {"node_id": "macmini-ollama", "node_label": "MacMini (Ollama)", "route_type": "local"}
    if "lmstudio" in model_lower:
        return {"node_id": "y7000p-lmstudio", "node_label": "Y7000P (LMStudio)", "route_type": "local"}
    if any(key in model_lower for key in ("gpt", "claude", "deepseek", "gemini")) or "deepseek" in provider_lower:
        return {"node_id": "cloud-cc-switch", "node_label": "Cloud (cc-switch)", "route_type": "cloud"}
    return {"node_id": "local-mac", "node_label": "Local-Mac", "route_type": "local"}


# ─── Compute ───────────────────────────────────────────────────


def load_debt() -> dict:
    """Load OMO debt ledger from the filesystem and return a JSON-safe dict."""
    try:
        from cockpit.adapters.omo import load_debt_ledger

        omo_dir = OMO_ROOT / ".omo"
        if not omo_dir.exists():
            return {"error": f"OMO directory not found at {omo_dir}", "items": []}

        ledger = load_debt_ledger(omo_dir)

        items = []
        for i in ledger.items:
            items.append(
                {
                    "id": i.id,
                    "title": i.title,
                    "dimension": i.dimension,
                    "subdimension": i.subdimension,
                    "domain": i.domain,
                    "scope": i.scope,
                    "severity": i.severity,
                    "weight": i.weight,
                    "entropy_class": i.entropy_class,
                    "lifecycle_state": i.lifecycle_state,
                    "owner": i.owner,
                    "affected_roots": list(i.affected_roots),
                    "evidence_refs": list(i.evidence_refs),
                    "mitigation_refs": list(i.mitigation_refs),
                    "opened_at": i.opened_at,
                    "last_reviewed_at": i.last_reviewed_at,
                    "next_review_at": i.next_review_at,
                    "gate_level": i.gate_level,
                    "history": list(i.history),
                    "x1_policy_refs": [i.x1_policy_ref] if i.x1_policy_ref else [],
                    "x1_policy_ref": i.x1_policy_ref,
                    "x1": [i.x1_policy_ref] if i.x1_policy_ref else [],
                    "x2_freshness": i.x2_freshness,
                    "x2": [],
                    "x3_tier": i.x3_tier,
                    "x3": i.x3_tier,
                }
            )

        return {
            "total": len(items),
            "open": sum(1 for i in ledger.items if i.lifecycle_state != "closed"),
            "closed": sum(1 for i in ledger.items if i.lifecycle_state == "closed"),
            "items": items,
        }
    except ImportError as e:
        return {"error": f"Import error: {e}", "items": []}
    except Exception as e:  # defensive fallback
        return {"error": str(e), "items": []}


# ─── E2E ───────────────────────────────────────────────────────


def run_e2e() -> dict:
    """Run the e2e check and return results."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "runtime.e2e"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )
        stdout = result.stdout
        m = re.search(r"Result:\s*(\d+)/(\d+)\s*checks\s*passed", stdout)
        if m:
            return {"result": f"{m.group(1)}/{m.group(2)} passed", "output": stdout}
        return {"result": "unparsed", "output": stdout}
    except subprocess.TimeoutExpired:
        return {"result": "timeout", "error": "E2E took >30s"}
    except Exception as e:  # defensive fallback
        return {"result": "error", "error": str(e)}


# ─── OMO Report ────────────────────────────────────────────────


def omo_report() -> dict:
    """Generate OMO summary report."""
    try:
        omo_dir = OMO_ROOT / ".omo"
        items_dir = omo_dir / "debt" / "items"
        files = sorted(items_dir.glob("*.yaml")) if items_dir.exists() else []
        items = []
        for f in files:
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            items.append(d)
        open_count = sum(1 for i in items if i.get("lifecycle_state") not in ("closed", "resolved"))
        closed_count = sum(1 for i in items if i.get("lifecycle_state") in ("closed", "resolved"))
        return {
            "summary": f"{len(items)} items, {open_count} open, {closed_count} closed",
            "total": len(items),
            "open": open_count,
            "closed": closed_count,
        }
    except Exception as e:  # defensive fallback
        return {"error": str(e), "summary": "Error"}


# ─── BOS Metrics ─────────────────────────────────────────────
# (existing load_bos_metrics function stays unchanged above)


# ─── Architecture Health ─────────────────────────────────────


def load_bos_metrics() -> dict:
    """Read BOS metrics from JSONL and aggregate by domain."""
    from collections import defaultdict

    records = []
    if BOS_METRICS_PATH.exists():
        for line in BOS_METRICS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # Aggregate by domain
    domains: dict[str, dict] = defaultdict(lambda: {"total": 0, "success": 0, "error": 0, "latency_total": 0.0})
    for rec in records:
        uri = rec.get("uri", "")
        domain = uri.split("/")[2] if uri.startswith("bos://") and "/" in uri[6:] else "unknown"
        status = rec.get("status", "")
        elapsed = rec.get("elapsed_ms", 0) or 0
        d = domains[domain]
        d["total"] += 1
        if status == "resolved":
            d["success"] += 1
        else:
            d["error"] += 1
        d["latency_total"] += elapsed

    domain_list = []
    for domain, agg in sorted(domains.items(), key=lambda x: x[1]["total"], reverse=True):
        domain_list.append(
            {
                "domain": domain,
                "total": agg["total"],
                "success": agg["success"],
                "error": agg["error"],
                "avg_latency": round(agg["latency_total"] / agg["total"], 2) if agg["total"] else 0,
            }
        )

    total_calls = len(records)
    success_count = sum(1 for r in records if r.get("status") == "resolved")
    error_count = total_calls - success_count
    total_latency = sum(r.get("elapsed_ms", 0) or 0 for r in records)

    recent = sorted(records, key=lambda r: r.get("recorded_at", ""), reverse=True)[:50]

    return {
        "summary": {
            "total_calls": total_calls,
            "success_count": success_count,
            "error_count": error_count,
            "avg_latency": round(total_latency / total_calls, 2) if total_calls else 0,
        },
        "domains": domain_list,
        "recent": recent,
    }


# ─── Cron Pipeline Summary ──────────────────────────────────────


CRON_OUTPUT_DIR = Path.home() / ".hermes" / "cron" / "output"


def load_cron_summary() -> dict:
    """Read cron pipeline outputs from ~/.hermes/cron/output/ and aggregate.

    Returns today's tasks with: timestamp, task name, status, duration, summary.
    """
    from collections import defaultdict

    tasks = []
    today_str = datetime.now(UTC).strftime("%Y-%m-%d")

    if not CRON_OUTPUT_DIR.exists():
        return {"total_tasks": 0, "today_tasks": [], "all_tasks": []}

    # 1) Directories = task IDs with .md result files
    for entry in sorted(CRON_OUTPUT_DIR.iterdir()):
        if entry.is_dir():
            task_id = entry.name
            md_files = sorted(entry.glob("*.md"))
            if not md_files:
                continue
            latest = md_files[-1]
            try:
                content = latest.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            lines = content.splitlines()
            name = task_id
            schedule = ""
            for line in lines:
                if line.startswith("# Cron Job:"):
                    name = line.replace("# Cron Job:", "").strip()
                elif line.startswith("**Schedule:**"):
                    schedule = line.replace("**Schedule:**", "").strip()

            is_today = today_str in latest.stem
            status = "ok"
            if "[SILENT]" in content:
                status = "silent"
            elif "error" in content.lower() or "traceback" in content.lower():
                status = "error"
            elif "fail" in content.lower():
                status = "degraded"

            summary_line = ""
            for line in lines:
                if line.startswith("## Response"):
                    continue
                s = line.strip()
                if s and not s.startswith("#") and not s.startswith("**") and len(s) > 20:
                    summary_line = s[:120]
                    break

            tasks.append(
                {
                    "task_id": task_id,
                    "name": name,
                    "schedule": schedule,
                    "latest_run": latest.stem,
                    "status": status,
                    "summary": summary_line or content[:120].strip(),
                    "is_today": is_today,
                }
            )

    # 2) governance.jsonl — individual cron event log
    gov_jsonl = CRON_OUTPUT_DIR / "governance.jsonl"
    if gov_jsonl.exists():
        for line in gov_jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            tasks.append(
                {
                    "task_id": rec.get("action", "changelog"),
                    "name": f"changelog: {rec.get('detail', '')[:60]}",
                    "schedule": "cron",
                    "latest_run": rec.get("timestamp", ""),
                    "status": "ok" if rec.get("layer3", "").startswith("improved") else "ok",
                    "summary": rec.get("detail", "")[:120],
                    "is_today": today_str in (rec.get("timestamp", "")),
                }
            )

    # 3) arc-conv-gate-verification-*.txt files
    for txt_file in sorted(CRON_OUTPUT_DIR.glob("arc-conv-gate-verification-*.txt")):
        is_today = today_str in txt_file.stem
        try:
            content = txt_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = content.splitlines()
        status = "ok"
        if "❌" in content or "FAIL" in content:
            status = "error"
        elif "⚠️" in content:
            status = "degraded"
        summary_line = ""
        for line in lines:
            if line.strip().startswith("#") and "收敛" in line:
                summary_line = line.strip().lstrip("# ")
                break
        if not summary_line:
            summary_line = "ARC convergence verification"

        tasks.append(
            {
                "task_id": txt_file.stem,
                "name": "arc-conv-gate-verification",
                "schedule": "daily",
                "latest_run": txt_file.stem.replace("arc-conv-gate-verification-", ""),
                "status": status,
                "summary": summary_line[:120],
                "is_today": is_today,
            }
        )

    today_tasks = [t for t in tasks if t["is_today"]]
    today_tasks.sort(key=lambda t: t["latest_run"], reverse=True)

    total = len(tasks)
    ok_count = sum(1 for t in tasks if t["status"] == "ok")
    error_count = sum(1 for t in tasks if t["status"] == "error")

    return {
        "total_tasks": total,
        "ok_count": ok_count,
        "error_count": error_count,
        "today_count": len(today_tasks),
        "today_tasks": today_tasks[:20],
        "all_tasks": sorted(tasks, key=lambda t: t["latest_run"], reverse=True)[:50],
    }


# ─── Governance Audit Summary ────────────────────────────────────


GOVERNANCE_DATA_PATH = Path.home() / "Workspace" / ".omo" / "_control" / "governance-data.json"


def load_governance_summary() -> dict:
    """Read governance audit data from .omo/_control/governance-data.json."""
    result: dict = {
        "health_score": 0,
        "total_debt": 0,
        "resolved": 0,
        "unresolved": 0,
        "resolution_rate": 0,
        "categories": {},
        "project_count": 0,
        "trend_entries": 0,
        "latest_audit": None,
        "findings": [],
    }

    if not GOVERNANCE_DATA_PATH.exists():
        return result

    try:
        raw = json.loads(GOVERNANCE_DATA_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return result

    gov = raw.get("governance", {})
    result["health_score"] = gov.get("health_score", 0) or gov.get("health_score_raw", 0)
    result["health_score_raw"] = gov.get("health_score_raw", 0)

    debt = raw.get("debt", {})
    result["total_debt"] = debt.get("total_count", 0)
    result["resolved"] = debt.get("resolved_count", 0)
    result["unresolved"] = debt.get("unresolved_count", 0)
    result["resolution_rate"] = debt.get("resolution_rate", 0)

    result["categories"] = raw.get("categories", {})
    result["trend_entries"] = len(raw.get("trend", []))
    result["latest_audit"] = raw.get("generated_at")
    result["project_count"] = len(raw.get("projects", {}))

    # Extract findings from trend
    findings = []
    for trend in raw.get("trend", []):
        note = trend.get("note", "")
        if note:
            findings.append(
                {
                    "date": trend.get("date", ""),
                    "note": note,
                    "score": trend.get("debt_health", 0),
                }
            )
    result["findings"] = findings[-10:]  # last 10

    return result


# ─── BOS Trends ──────────────────────────────────────────────────


def load_bos_trends() -> dict:
    """Read bos-metrics.jsonl and compute 24h/7d trends.

    Returns call volume, success rate, latency percentiles for two windows.
    """
    from collections import defaultdict

    records = []
    if BOS_METRICS_PATH.exists():
        for line in BOS_METRICS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    now = datetime.now(UTC)
    window_24h = now.timestamp() - 86400
    window_7d = now.timestamp() - 7 * 86400

    def _filter_since(ts_cutoff: float) -> list:
        result = []
        for r in records:
            ts_str = r.get("recorded_at", "")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError):
                continue
            if ts >= ts_cutoff:
                result.append(r)
        return result

    def _compute_stats(window_records: list) -> dict:
        total = len(window_records)
        if total == 0:
            return {"calls": 0, "success_rate": 0, "avg_latency": 0, "p50": 0, "p95": 0, "p99": 0}
        success = sum(1 for r in window_records if r.get("status") == "resolved")
        latencies = sorted(r.get("elapsed_ms", 0) or 0 for r in window_records)
        avg_lat = sum(latencies) / len(latencies) if latencies else 0

        def _percentile(sorted_list, pct):
            if not sorted_list:
                return 0
            idx = int(len(sorted_list) * pct / 100)
            return sorted_list[min(idx, len(sorted_list) - 1)]

        return {
            "calls": total,
            "success_count": success,
            "error_count": total - success,
            "success_rate": round(success / total * 100, 1) if total else 0,
            "avg_latency": round(avg_lat, 1),
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "p99": _percentile(latencies, 99),
        }

    return {
        "last_24h": _compute_stats(_filter_since(window_24h)),
        "last_7d": _compute_stats(_filter_since(window_7d)),
        "total_all_time": len(records),
        "latest_record": records[-1] if records else None,
    }


# ─── Entry Convergence Status ────────────────────────────────────


KNOWN_CLI_ENTRIES = [
    {"cli": "ecos", "role": "L0 Protocol", "converged": True, "redirect": "cockpit ssb, cockpit workflow"},
    {"cli": "mof", "role": "L0 SSOT Tools", "converged": False, "redirect": None},
    {"cli": "cockpit", "role": "L3 Unified CLI", "converged": True, "redirect": None},
    {"cli": "arcnode", "role": "L0 Governance", "converged": True, "redirect": "cockpit governance, cockpit audit"},
    {"cli": "omo", "role": "L2 Governance Kernel", "converged": True, "redirect": "cockpit governance"},
]


def load_convergence_status() -> dict:
    """Check which CLIs are still active vs. redirected to cockpit."""
    import shutil

    entries = []
    for entry in KNOWN_CLI_ENTRIES:
        exists = bool(shutil.which(entry["cli"]))
        entries.append(
            {
                "cli": entry["cli"],
                "role": entry["role"],
                "exists_on_path": exists,
                "converged": entry["converged"],
                "redirect": entry["redirect"],
            }
        )

    total = len(entries)
    converged = sum(1 for e in entries if e["converged"])
    remaining = [e["cli"] for e in entries if not e["converged"]]

    return {
        "total_entry_points": total,
        "converged_to_cockpit": converged,
        "convergence_pct": round(converged / total * 100, 0) if total else 0,
        "remaining": remaining,
        "entries": entries,
    }
