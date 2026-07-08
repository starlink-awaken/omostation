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
