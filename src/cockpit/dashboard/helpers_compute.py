"""cockpit.dashboard.helpers_compute — load_compute 拆分 (P110-E).

TASK-F7114ABA (omo lint god-module 800L 硬规则).
cockpit/dashboard/helpers.py 1116L 拆分: load_compute (~530L) 独立到本模块,
helpers.py 降至 381L (<800L 阈值).

业务: 加载 compute topology 数据 (LLM quota summary + provider plane +
m0 snapshot + http fetch + circuit breaker + cost estimation).

模式: load_compute 内部 import 共享 helper (lazy import 避免循环).
调用方 `from cockpit.dashboard.helpers import load_compute` 不破.
"""

from __future__ import annotations

# 注: load_compute 函数体内使用了 helpers.py 的 6 个共享 helper
# (read_json_file, parse_timestamp, fetch_http, read_m0_snapshot,
# estimate_cost, infer_node) + cockpit.dashboard.constants 中的常量 +
# yaml 库. 都在 load_compute 函数体内惰性 import (避免本模块 import 时
# 触发 cockpit.dashboard.helpers 与本模块的循环).


def load_compute() -> dict:
    # 惰性 import (避免 helpers_compute 顶层 import helpers 时的循环)
    import json

    import yaml

    from cockpit.dashboard.constants import (
        DEFAULT_COMPUTE_TOPOLOGY,
        LLM_COST_LOG_PATH,
        LLM_QUOTA_SUMMARY_PATH,
        PROVIDER_PLANE_PATH,
    )
    from cockpit.dashboard.helpers import (
        estimate_cost,
        infer_node,
        parse_timestamp,
        read_json_file,
    )

    quota_summary = read_json_file(LLM_QUOTA_SUMMARY_PATH)
    provider_plane = {}
    if PROVIDER_PLANE_PATH.exists():
        provider_plane = yaml.safe_load(PROVIDER_PLANE_PATH.read_text(encoding="utf-8")) or {}

    selected_provider = provider_plane.get("selected_provider") or {}
    provider_name = selected_provider.get("name")
    selected_cloud_model = selected_provider.get("model") or "gpt-4o"
    circuit_broken = bool(provider_plane.get("circuit_broken", False))
    daily_budget = float(provider_plane.get("daily_budget", 100.0))

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

    # 计算 CPU 负载率
    try:
        import psutil

        local_cpu = int(psutil.cpu_percent(interval=0.05))
    except ImportError:
        try:
            import multiprocessing
            import os

            load = os.getloadavg()[0]
            cores = multiprocessing.cpu_count()
            local_cpu = int(min(100.0, (load / cores) * 100.0))
        except Exception:  # defensive fallback
            local_cpu = 0

    # Map to frontend expected nodes structure (ComputeView topology)
    frontend_nodes = []
    for node in topology:
        # local-mac is always online since it hosts the cockpit console server
        is_online = True if node["id"] == "local-mac" else node["active"]

        if node["id"] == "local-mac":
            cpu_val = local_cpu
            gpu_val = 0
        else:
            if is_online:
                # 远端节点只有路由活动证据，不能把调用量冒充硬件负载。
                cpu_val = None
                gpu_val = None
            else:
                cpu_val = 0
                gpu_val = 0

        frontend_nodes.append(
            {
                "id": node["id"],
                "name": node["label"],
                "model": node["role"],
                "status": "online" if is_online else "offline",
                "type": node["kind"].upper() if node["kind"] else "UNKNOWN",
                "cpu_usage": cpu_val,
                "gpu_usage": gpu_val,
            }
        )

    # Map to frontend expected quota structure (ComputeView LLM quota)
    frontend_quotas = []
    for q in quota_providers:
        provider_id = q["provider_id"]
        details = (provider_plane.get("quota_summary", {}).get("providers", {}) or {}).get(provider_id, {})
        usage = {}
        total_used = details.get("total_used")
        total_granted = details.get("total_granted")
        if total_used is not None and total_granted is not None:
            usage = {"total_used": total_used, "total_granted": total_granted}
        frontend_quotas.append(
            {
                "provider": provider_id,
                "available": q["available"],
                "error": None if q["available"] else {"message": q.get("summary") or "API Key 校验未通过"},
                "balance_usd": q.get("balance"),
                "used_percent": q.get("used_percent"),
                "usage": usage,
            }
        )

    # Available Models extraction (from litellm_health or fallbacks)
    litellm_health = provider_plane.get("litellm_health", {})
    healthy_models = litellm_health.get("healthy_models", []) or []
    unhealthy_models = litellm_health.get("unhealthy_models", []) or []

    available_models_list = []
    for m in healthy_models:
        model_name = m.get("model_name") if isinstance(m, dict) else str(m)
        provider = model_name.split("/")[0] if "/" in model_name else "unknown"
        available_models_list.append(
            {
                "model_name": model_name,
                "status": "healthy",
                "provider": provider,
                "latency_p50": m.get("latency_p50") if isinstance(m, dict) else None,
                "tokens_per_second": m.get("tokens_per_second") if isinstance(m, dict) else None,
                "calls_today": m.get("calls_today") if isinstance(m, dict) else None,
            }
        )
    for m in unhealthy_models:
        model_name = m.get("model_name") if isinstance(m, dict) else str(m)
        provider = model_name.split("/")[0] if "/" in model_name else "unknown"
        available_models_list.append(
            {
                "model_name": model_name,
                "status": "unhealthy",
                "provider": provider,
                "latency_p50": m.get("latency_p50") if isinstance(m, dict) else None,
                "tokens_per_second": m.get("tokens_per_second") if isinstance(m, dict) else None,
                "calls_today": m.get("calls_today") if isinstance(m, dict) else None,
            }
        )
    scheduled_tasks = provider_plane.get("scheduled_tasks") or []

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
        "nodes": frontend_nodes,
        "quota": {"quota": frontend_quotas},
        "available_models": available_models_list,
        "circuit_broken": circuit_broken,
        "daily_budget": daily_budget,
        "scheduled_tasks": scheduled_tasks,
    }


# ─── Debt ──────────────────────────────────────────────────────
