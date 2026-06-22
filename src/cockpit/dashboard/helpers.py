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
    DEFAULT_COMPUTE_TOPOLOGY,
    LLM_COST_LOG_PATH,
    LLM_QUOTA_SUMMARY_PATH,
    M0_SNAPSHOT_PATH,
    OMO_ROOT,
    PROJECT_ROOT,
    PROVIDER_PLANE_PATH,
)
from cockpit.web.auth import get_subservice_token

# ─── File I/O ──────────────────────────────────────────────────


def read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
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
    except Exception as e:
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
    except Exception as e:
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
            from omo.omo_dashboard import _load_json as _omo_load

            omo_dir = Path(os.environ.get("OMO_DIR", str(Path.home() / "Workspace" / ".omo")))
            system = _omo_load(omo_dir / "state" / "system.yaml")
            return {
                "layer": "L2",
                "name": "omo",
                "status": "ok",
                "data": {"system": system, "source": "direct_import"},
            }
        except Exception:
            return fetch_http(source)

    # L1 runtime — try direct import
    if source["layer"] == "L1":
        try:
            from runtime.i0 import i0_status

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
        except Exception:
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
    return round(
        (input_tokens / 1000) * rates["input"] + (output_tokens / 1000) * rates["output"], 6
    )


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


def load_compute() -> dict:
    quota_summary = read_json_file(LLM_QUOTA_SUMMARY_PATH)
    provider_plane = {}
    if PROVIDER_PLANE_PATH.exists():
        provider_plane = yaml.safe_load(PROVIDER_PLANE_PATH.read_text(encoding="utf-8")) or {}

    selected_provider = provider_plane.get("selected_provider") or {}
    provider_name = selected_provider.get("name")
    selected_cloud_model = selected_provider.get("model") or "gpt-4o"

    records = []
    if LLM_COST_LOG_PATH.exists():
        for line in LLM_COST_LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            model = entry.get("model", "unknown")
            input_tokens = int(entry.get("input_tokens", 0) or 0)
            output_tokens = int(entry.get("output_tokens", 0) or 0)
            raw_ts = entry.get("timestamp") or entry.get("ts")
            ts = parse_timestamp(raw_ts)
            provider_hint = entry.get("provider") or provider_name or "unknown"
            inferred_node = infer_node(model, provider_hint)
            latency_ms = entry.get("latency_ms")
            tokens_per_second = entry.get("tokens_per_second")
            estimated_cost = float(
                entry.get("estimated_cost_usd")
                or entry.get("cost")
                or estimate_cost(model, input_tokens, output_tokens)
            )
            total_tokens = input_tokens + output_tokens
            route_type = entry.get("route_type") or inferred_node["route_type"]
            equivalent_cloud_cost = estimate_cost(selected_cloud_model, input_tokens, output_tokens)
            records.append(
                {
                    "timestamp": ts.isoformat() if ts else raw_ts,
                    "model": model,
                    "provider_hint": provider_hint,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "estimated_cost_usd": round(estimated_cost, 6),
                    "equivalent_cloud_cost_usd": round(equivalent_cloud_cost, 6),
                    "saved_vs_cloud_usd": round(max(equivalent_cloud_cost - estimated_cost, 0.0), 6),
                    "latency_ms": float(latency_ms) if latency_ms is not None else None,
                    "tokens_per_second": float(tokens_per_second) if tokens_per_second is not None else None,
                    "node_id": entry.get("node_id") or inferred_node["node_id"],
                    "node_label": entry.get("node_label") or inferred_node["node_label"],
                    "route_type": route_type,
                }
            )

    records.sort(key=lambda item: item.get("timestamp") or "", reverse=True)

    latest_request_at = records[0].get("timestamp") if records else None
    earliest_request_at = records[-1].get("timestamp") if records else None
    latest_dt = parse_timestamp(latest_request_at)
    earliest_dt = parse_timestamp(earliest_request_at)
    span_hours = None
    if latest_dt and earliest_dt:
        span_hours = round((latest_dt - earliest_dt).total_seconds() / 3600, 2)

    traffic_by_node: dict[str, dict] = {}
    for record in records:
        bucket = traffic_by_node.setdefault(
            record["node_id"],
            {
                "node_id": record["node_id"],
                "node_label": record["node_label"],
                "route_type": record["route_type"],
                "calls": 0,
                "tokens": 0,
                "estimated_cost_usd": 0.0,
                "equivalent_cloud_cost_usd": 0.0,
                "saved_vs_cloud_usd": 0.0,
                "latency_samples": 0,
                "latency_ms_avg": None,
                "tokens_per_second_avg": None,
                "_latency_total": 0.0,
                "_throughput_total": 0.0,
                "_throughput_samples": 0,
            },
        )
        bucket["calls"] += 1
        bucket["tokens"] += record["total_tokens"]
        bucket["estimated_cost_usd"] = round(bucket["estimated_cost_usd"] + record["estimated_cost_usd"], 6)
        bucket["equivalent_cloud_cost_usd"] = round(
            bucket["equivalent_cloud_cost_usd"] + record["equivalent_cloud_cost_usd"], 6
        )
        bucket["saved_vs_cloud_usd"] = round(bucket["saved_vs_cloud_usd"] + record["saved_vs_cloud_usd"], 6)
        if record["latency_ms"] is not None:
            bucket["latency_samples"] += 1
            bucket["_latency_total"] += record["latency_ms"]
        if record["tokens_per_second"] is not None:
            bucket["_throughput_samples"] += 1
            bucket["_throughput_total"] += record["tokens_per_second"]

    for bucket in traffic_by_node.values():
        if bucket["latency_samples"]:
            bucket["latency_ms_avg"] = round(bucket["_latency_total"] / bucket["latency_samples"], 3)
        if bucket["_throughput_samples"]:
            bucket["tokens_per_second_avg"] = round(bucket["_throughput_total"] / bucket["_throughput_samples"], 3)
        del bucket["_latency_total"]
        del bucket["_throughput_total"]
        del bucket["_throughput_samples"]

    topology = []
    active_node_ids = set(traffic_by_node)
    selected_node_id = infer_node(selected_provider.get("model", ""), provider_name).get("node_id")
    for node in DEFAULT_COMPUTE_TOPOLOGY:
        topology.append(
            {
                **node,
                "active": node["id"] in active_node_ids,
                "selected_provider_route": node["id"] == selected_node_id,
            }
        )

    quota_providers = []
    for provider_id, details in (provider_plane.get("quota_summary", {}).get("providers", {}) or {}).items():
        quota_providers.append(
            {
                "provider_id": provider_id,
                "available": bool(details.get("available", False)),
                "summary": details.get("summary"),
                "balance": details.get("balance"),
                "remaining": details.get("remaining"),
                "used_percent": details.get("used_percent"),
            }
        )

    latency_values = [item["latency_ms"] for item in records if item["latency_ms"] is not None]
    throughput_values = [item["tokens_per_second"] for item in records if item["tokens_per_second"] is not None]
    total_calls = len(records)
    local_records = [item for item in records if item["route_type"] != "cloud"]
    cloud_records = [item for item in records if item["route_type"] == "cloud"]
    intercepted_calls = len(local_records)
    intercepted_tokens = sum(item["total_tokens"] for item in local_records)
    actual_local_cost = round(sum(item["estimated_cost_usd"] for item in local_records), 6)
    actual_cloud_cost = round(sum(item["estimated_cost_usd"] for item in cloud_records), 6)
    cloud_equivalent_cost = round(sum(item["equivalent_cloud_cost_usd"] for item in records), 6)
    intercepted_equivalent_cloud_cost = round(sum(item["equivalent_cloud_cost_usd"] for item in local_records), 6)
    saved_vs_cloud = round(sum(item["saved_vs_cloud_usd"] for item in local_records), 6)
    codex_provider = (provider_plane.get("quota_summary", {}).get("providers", {}) or {}).get("codex", {})

    return {
        "summary": {
            "generated_at": quota_summary.get("generated_at"),
            "entry_count": quota_summary.get("entry_count", len(records)),
            "total_calls": total_calls,
            "recent_calls": len(records[:10]),
            "total_input_tokens": sum(item["input_tokens"] for item in records),
            "total_output_tokens": sum(item["output_tokens"] for item in records),
            "total_estimated_cost_usd": round(
                quota_summary.get("total_estimated_cost_usd", sum(item["estimated_cost_usd"] for item in records)),
                6,
            ),
            "remaining_ratio": quota_summary.get("remaining_ratio"),
            "remaining_budget_usd": quota_summary.get("remaining_budget_usd"),
            "effective_remaining_budget_usd": quota_summary.get("effective_remaining_budget_usd"),
            "quota_low": bool(quota_summary.get("quota_low", False)),
            "latest_request_at": latest_request_at,
            "earliest_request_at": earliest_request_at,
            "time_span_hours": span_hours,
            "avg_latency_ms": round(sum(latency_values) / len(latency_values), 3) if latency_values else None,
            "avg_tokens_per_second": round(sum(throughput_values) / len(throughput_values), 3)
            if throughput_values
            else None,
        },
        "provider": {
            "name": selected_provider.get("name"),
            "model": selected_provider.get("model"),
            "base_url": selected_provider.get("base_url"),
            "source": selected_provider.get("source"),
            "is_healthy": selected_provider.get("is_healthy"),
            "quota_provider_count": provider_plane.get("quota_summary", {}).get("provider_count", 0),
            "quota_providers": quota_providers,
        },
        "topology": topology,
        "traffic_by_node": sorted(traffic_by_node.values(), key=lambda item: item["calls"], reverse=True),
        "recent_traffic": records[:10],
        "cost_board": {
            "selected_cloud_model": selected_cloud_model,
            "intercepted_calls": intercepted_calls,
            "intercepted_tokens": intercepted_tokens,
            "interception_rate": round(intercepted_calls / total_calls, 4) if total_calls else 0.0,
            "actual_cloud_cost_usd": actual_cloud_cost,
            "actual_local_cost_usd": actual_local_cost,
            "actual_total_cost_usd": round(actual_cloud_cost + actual_local_cost, 6),
            "cloud_equivalent_cost_usd": cloud_equivalent_cost,
            "intercepted_equivalent_cloud_cost_usd": intercepted_equivalent_cloud_cost,
            "saved_vs_cloud_usd": saved_vs_cloud,
            "codex_remaining_credits": codex_provider.get("remaining"),
            "codex_secondary_used_percent": codex_provider.get("used_percent"),
            "codex_available": bool(codex_provider.get("available", False)),
            "codex_summary": codex_provider.get("summary"),
        },
        "observations": {
            "cross_day": bool(latest_dt and earliest_dt and latest_dt.date() != earliest_dt.date()),
            "cross_week": bool(
                latest_dt and earliest_dt and latest_dt.isocalendar()[:2] != earliest_dt.isocalendar()[:2]
            ),
            "cross_model": len({item["model"] for item in records}) > 1,
            "latency_available": bool(latency_values),
            "throughput_mode": "trace" if throughput_values else "token-aggregate",
        },
    }


# ─── Debt ──────────────────────────────────────────────────────


def load_debt() -> dict:
    """Load OMO debt ledger from the filesystem and return a JSON-safe dict."""
    try:
        from omo.omo_debt_registry import load_debt_ledger

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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
        return {"error": str(e), "summary": "Error"}


# ─── BOS Metrics ─────────────────────────────────────────────


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
        domain_list.append({
            "domain": domain,
            "total": agg["total"],
            "success": agg["success"],
            "error": agg["error"],
            "avg_latency": round(agg["latency_total"] / agg["total"], 2) if agg["total"] else 0,
        })

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
