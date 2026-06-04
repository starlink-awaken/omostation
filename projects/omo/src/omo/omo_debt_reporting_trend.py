from __future__ import annotations

try:
    from .omo_debt_reporting_history import _validate_run_stamp
except ModuleNotFoundError:
    from .omo_debt_reporting_history import _validate_run_stamp


def _trend_run(entry: dict[str, object]) -> dict[str, object]:
    if not entry["reporting_exists"] or any(
        entry[field] is None
        for field in (
            "total_items",
            "executed_item_count",
            "approval_coverage_rate",
            "execution_completion_rate",
        )
    ):
        raise ValueError(f"missing reporting trend metadata for run: {entry['run_stamp']}")
    return {
        "run_stamp": entry["run_stamp"],
        "dispatch_run_ref": entry["dispatch_run_ref"],
        "reporting_ref": entry["reporting_ref"],
        "total_items": entry["total_items"],
        "executed_item_count": entry["executed_item_count"],
        "approval_coverage_rate": entry["approval_coverage_rate"],
        "execution_completion_rate": entry["execution_completion_rate"],
    }


def _interval(previous: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    return {
        "from_run_stamp": previous["run_stamp"],
        "to_run_stamp": current["run_stamp"],
        "total_items_delta": current["total_items"] - previous["total_items"],
        "executed_item_count_delta": current["executed_item_count"] - previous["executed_item_count"],
        "approval_coverage_rate_delta": current["approval_coverage_rate"] - previous["approval_coverage_rate"],
        "execution_completion_rate_delta": current["execution_completion_rate"] - previous["execution_completion_rate"],
    }


def _owner_trend_run(owner: str, run_stamp: str, entry: dict[str, object]) -> dict[str, object]:
    if any(
        entry[field] is None
        for field in (
            "item_count",
            "executed_item_count",
            "approval_coverage_rate",
            "execution_completion_rate",
        )
    ):
        raise ValueError(f"missing owner trend metadata for owner {owner} in run: {run_stamp}")
    return {
        "run_stamp": run_stamp,
        "item_count": entry["item_count"],
        "executed_item_count": entry["executed_item_count"],
        "approval_coverage_rate": entry["approval_coverage_rate"],
        "execution_completion_rate": entry["execution_completion_rate"],
    }


def _owner_interval(previous: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    return {
        "from_run_stamp": previous["run_stamp"],
        "to_run_stamp": current["run_stamp"],
        "item_count_delta": current["item_count"] - previous["item_count"],
        "executed_item_count_delta": current["executed_item_count"] - previous["executed_item_count"],
        "approval_coverage_rate_delta": current["approval_coverage_rate"] - previous["approval_coverage_rate"],
        "execution_completion_rate_delta": current["execution_completion_rate"] - previous["execution_completion_rate"],
    }


def _owners_by_run(
    ordered_runs: list[dict[str, object]],
    reporting_packets_by_run: dict[str, dict[str, object]] | None,
) -> list[dict[str, dict[str, object]]] | None:
    if len(ordered_runs) < 2 or reporting_packets_by_run is None:
        return None

    owners_by_run = []
    for run in ordered_runs:
        run_stamp = str(run["run_stamp"])
        reporting_packet = reporting_packets_by_run.get(run_stamp)
        if reporting_packet is None:
            raise ValueError(f"missing owner reporting packet for run: {run_stamp}")
        owners_by_run.append(
            {str(entry["owner"]): entry for entry in reporting_packet.get("owners", [])}
        )
    return owners_by_run


def _owner_trends(
    ordered_runs: list[dict[str, object]],
    owners_by_run: list[dict[str, dict[str, object]]] | None,
) -> dict[str, object] | None:
    if owners_by_run is None:
        return None

    union_names: set[str] = set()
    for owner_map in owners_by_run:
        union_names |= set(owner_map.keys())

    shared_names = sorted(set.intersection(*(set(owner_map.keys()) for owner_map in owners_by_run)))
    compared = []
    for owner_name in shared_names:
        owner_runs = [
            _owner_trend_run(owner_name, str(run["run_stamp"]), owner_map[owner_name])
            for run, owner_map in zip(ordered_runs, owners_by_run, strict=True)
        ]
        compared.append(
            {
                "owner": owner_name,
                "runs": owner_runs,
                "intervals": [
                    _owner_interval(owner_runs[index], owner_runs[index + 1])
                    for index in range(len(owner_runs) - 1)
                ],
            }
        )

    return {
        "owners_trend_status": "owners_trend_available" if shared_names else "no_shared_owners",
        "shared_owner_count": len(shared_names),
        "owners_excluded_count": len(union_names - set(shared_names)),
        "compared": compared,
    }


def _owner_presence(
    ordered_runs: list[dict[str, object]],
    owners_by_run: list[dict[str, dict[str, object]]] | None,
    shared_names: set[str] | None,
) -> dict[str, object] | None:
    if owners_by_run is None or shared_names is None:
        return None

    union_names = set().union(*(owner_map.keys() for owner_map in owners_by_run))
    excluded_names = sorted(union_names - shared_names)
    if not excluded_names:
        return {
            "presence_status": "no_excluded_owners",
            "window_run_count": len(ordered_runs),
            "entries": [],
        }

    entries = []
    oldest_run_stamp = str(ordered_runs[0]["run_stamp"])
    latest_run_stamp = str(ordered_runs[-1]["run_stamp"])
    for owner_name in excluded_names:
        present_stamps = [
            str(run["run_stamp"])
            for run, owner_map in zip(ordered_runs, owners_by_run, strict=True)
            if owner_name in owner_map
        ]
        entries.append(
            {
                "owner": owner_name,
                "run_count": len(present_stamps),
                "first_window_run": present_stamps[0],
                "last_window_run": present_stamps[-1],
                "in_first_window_run": present_stamps[0] == oldest_run_stamp,
                "in_last_window_run": present_stamps[-1] == latest_run_stamp,
            }
        )

    return {
        "presence_status": "presence_available",
        "window_run_count": len(ordered_runs),
        "entries": entries,
    }


def _execution_progress_run(
    run: dict[str, object],
    baseline_open_item_count: int,
) -> dict[str, object]:
    open_item_count = int(run["total_items"]) - int(run["executed_item_count"])
    return {
        "run_stamp": run["run_stamp"],
        "open_item_count": open_item_count,
        "open_item_delta_vs_baseline": open_item_count - baseline_open_item_count,
        "open_item_ratio_vs_baseline": (
            None
            if baseline_open_item_count == 0
            else open_item_count / baseline_open_item_count
        ),
    }


def _execution_progress(
    ordered_runs: list[dict[str, object]],
) -> dict[str, object] | None:
    if len(ordered_runs) < 2:
        return None

    anchor_run = ordered_runs[0]
    baseline_open_item_count = int(anchor_run["total_items"]) - int(anchor_run["executed_item_count"])
    progress_runs = [
        _execution_progress_run(run, baseline_open_item_count)
        for run in ordered_runs
    ]
    return {
        "progress_status": (
            "baseline_fully_executed"
            if baseline_open_item_count == 0
            else "progress_available"
        ),
        "anchor_run_stamp": anchor_run["run_stamp"],
        "baseline_open_item_count": baseline_open_item_count,
        "runs": progress_runs,
    }


def _state_progress_run(
    run: dict[str, object],
    reporting_packet: dict[str, object],
    baseline_pending_approval: int,
) -> dict[str, object]:
    state_counts = reporting_packet["summary"]["state_counts"]
    pending_approval = int(state_counts["pending_approval"])
    executed = int(run["executed_item_count"])
    ready_to_execute = int(run["total_items"]) - pending_approval - executed
    artifact_ready_to_execute = int(state_counts["ready_to_execute"])
    if artifact_ready_to_execute != ready_to_execute:
        raise ValueError(f"invalid state progress counts for run: {run['run_stamp']}")
    return {
        "run_stamp": run["run_stamp"],
        "pending_approval": pending_approval,
        "ready_to_execute": ready_to_execute,
        "executed": executed,
        "pending_approval_delta_vs_baseline": pending_approval - baseline_pending_approval,
    }


def _state_progress(
    ordered_runs: list[dict[str, object]],
    reporting_packets_by_run: dict[str, dict[str, object]] | None,
) -> dict[str, object] | None:
    if len(ordered_runs) < 2 or reporting_packets_by_run is None:
        return None

    anchor_run = ordered_runs[0]
    anchor_packet = reporting_packets_by_run[str(anchor_run["run_stamp"])]
    baseline_pending_approval = int(anchor_packet["summary"]["state_counts"]["pending_approval"])
    runs = [
        _state_progress_run(
            run,
            reporting_packets_by_run[str(run["run_stamp"])],
            baseline_pending_approval,
        )
        for run in ordered_runs
    ]
    return {
        "state_progress_status": "state_progress_available",
        "anchor_run_stamp": anchor_run["run_stamp"],
        "baseline_pending_approval": baseline_pending_approval,
        "runs": runs,
    }


def _run_index(runs: list[dict[str, object]], run_stamp: str, *, label: str) -> int:
    for index, entry in enumerate(runs):
        if entry["run_stamp"] == run_stamp:
            return index
    raise ValueError(f"{label} not in history: {run_stamp}")


def _select_runs(
    history_packet: dict[str, object],
    *,
    window_requested: int | None,
    from_run_stamp_requested: str | None,
    to_run_stamp_requested: str | None,
) -> list[dict[str, object]]:
    runs = history_packet["runs"]
    if from_run_stamp_requested is not None or to_run_stamp_requested is not None:
        if from_run_stamp_requested is None or to_run_stamp_requested is None:
            raise ValueError("range mode requires both from-run-stamp and to-run-stamp")
        try:
            _validate_run_stamp(from_run_stamp_requested)
        except ValueError as exc:
            raise ValueError(f"invalid from-run-stamp: {from_run_stamp_requested}") from exc
        try:
            _validate_run_stamp(to_run_stamp_requested)
        except ValueError as exc:
            raise ValueError(f"invalid to-run-stamp: {to_run_stamp_requested}") from exc
        to_index = _run_index(runs, to_run_stamp_requested, label="to-run-stamp")
        from_index = _run_index(runs, from_run_stamp_requested, label="from-run-stamp")
        if from_index < to_index:
            raise ValueError("from-run-stamp must not be newer than to-run-stamp")
        return runs[to_index : from_index + 1]
    if window_requested is not None:
        return runs[:window_requested]
    return runs


def build_reporting_trend_packet(
    *,
    generated_at: str,
    history_packet: dict[str, object],
    reporting_packets_by_run: dict[str, dict[str, object]] | None = None,
    window_requested: int | None = None,
    from_run_stamp_requested: str | None = None,
    to_run_stamp_requested: str | None = None,
) -> dict[str, object]:
    selected_runs = _select_runs(
        history_packet,
        window_requested=window_requested,
        from_run_stamp_requested=from_run_stamp_requested,
        to_run_stamp_requested=to_run_stamp_requested,
    )
    ordered_runs = [_trend_run(entry) for entry in reversed(selected_runs)]
    intervals = [
        _interval(ordered_runs[index], ordered_runs[index + 1])
        for index in range(len(ordered_runs) - 1)
    ]
    oldest_run_stamp = ordered_runs[0]["run_stamp"] if ordered_runs else None
    latest_run_stamp = ordered_runs[-1]["run_stamp"] if ordered_runs else None
    owners_by_run = _owners_by_run(ordered_runs, reporting_packets_by_run)
    owners = _owner_trends(ordered_runs, owners_by_run)
    owner_presence = _owner_presence(
        ordered_runs,
        owners_by_run,
        (
            {str(entry["owner"]) for entry in owners["compared"]}
            if owners is not None
            else None
        ),
    )
    execution_progress = _execution_progress(ordered_runs)
    state_progress = _state_progress(ordered_runs, reporting_packets_by_run)
    return {
        "generated_at": generated_at,
        "trend_status": "trend_available" if len(ordered_runs) >= 2 else "insufficient_history",
        "window_requested": window_requested,
        "from_run_stamp_requested": from_run_stamp_requested,
        "to_run_stamp_requested": to_run_stamp_requested,
        "window_run_count": len(ordered_runs),
        "oldest_run_stamp": oldest_run_stamp,
        "latest_run_stamp": latest_run_stamp,
        "runs": ordered_runs,
        "intervals": intervals,
        "owners": owners,
        "owner_presence": owner_presence,
        "execution_progress": execution_progress,
        "state_progress": state_progress,
    }


def render_reporting_trend_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Debt Reporting Trend",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Trend status: {packet['trend_status']}",
        f"Oldest run: {packet['oldest_run_stamp'] or 'none'}",
        f"Latest run: {packet['latest_run_stamp'] or 'none'}",
        "",
    ]
    if packet["trend_status"] == "insufficient_history":
        lines.extend(["Trend baseline not established yet.", ""])
    for run in packet["runs"]:
        lines.extend(
            [
                f"## Run: {run['run_stamp']}",
                "",
                f"total_items={run['total_items']}",
                f"executed_item_count={run['executed_item_count']}",
                f"approval_coverage_rate={run['approval_coverage_rate']}",
                f"execution_completion_rate={run['execution_completion_rate']}",
                "",
            ]
        )
    for interval in packet["intervals"]:
        lines.extend(
            [
                f"## Interval: {interval['from_run_stamp']} -> {interval['to_run_stamp']}",
                "",
                f"total_items_delta={interval['total_items_delta']}",
                f"executed_item_count_delta={interval['executed_item_count_delta']}",
                f"approval_coverage_rate_delta={interval['approval_coverage_rate_delta']}",
                f"execution_completion_rate_delta={interval['execution_completion_rate_delta']}",
                "",
            ]
        )
    owners = packet.get("owners")
    if owners is not None:
        lines.extend(
            [
                "## Owner Trend",
                "",
                f"owners_trend_status={owners['owners_trend_status']}",
                f"shared_owner_count={owners['shared_owner_count']}",
                f"owners_excluded_count={owners['owners_excluded_count']}",
                "",
            ]
        )
        for owner in owners["compared"]:
            lines.extend([f"### Owner: {owner['owner']}", ""])
            for run in owner["runs"]:
                lines.extend(
                    [
                        f"#### Run: {run['run_stamp']}",
                        "",
                        f"item_count={run['item_count']}",
                        f"executed_item_count={run['executed_item_count']}",
                        f"approval_coverage_rate={run['approval_coverage_rate']}",
                        f"execution_completion_rate={run['execution_completion_rate']}",
                        "",
                    ]
                )
            for interval in owner["intervals"]:
                lines.extend(
                    [
                        f"#### Interval: {interval['from_run_stamp']} -> {interval['to_run_stamp']}",
                        "",
                        f"item_count_delta={interval['item_count_delta']}",
                        f"executed_item_count_delta={interval['executed_item_count_delta']}",
                        f"approval_coverage_rate_delta={interval['approval_coverage_rate_delta']}",
                        f"execution_completion_rate_delta={interval['execution_completion_rate_delta']}",
                        "",
                    ]
                )
    owner_presence = packet.get("owner_presence")
    if owner_presence is not None:
        lines.extend(
            [
                "## Owner Presence",
                "",
                f"presence_status={owner_presence['presence_status']}",
                f"window_run_count={owner_presence['window_run_count']}",
                "",
            ]
        )
        for entry in owner_presence["entries"]:
            lines.extend(
                [
                    f"### Presence Owner: {entry['owner']}",
                    "",
                    f"run_count={entry['run_count']}",
                    f"first_window_run={entry['first_window_run']}",
                    f"last_window_run={entry['last_window_run']}",
                    f"in_first_window_run={entry['in_first_window_run']}",
                    f"in_last_window_run={entry['in_last_window_run']}",
                    "",
                ]
            )
    execution_progress = packet.get("execution_progress")
    if execution_progress is not None:
        lines.extend(
            [
                "## Execution Progress",
                "",
                f"progress_status={execution_progress['progress_status']}",
                f"anchor_run_stamp={execution_progress['anchor_run_stamp']}",
                f"baseline_open_item_count={execution_progress['baseline_open_item_count']}",
                "",
            ]
        )
        for run in execution_progress["runs"]:
            lines.extend(
                [
                    f"### Progress Run: {run['run_stamp']}",
                    "",
                    f"open_item_count={run['open_item_count']}",
                    f"open_item_delta_vs_baseline={run['open_item_delta_vs_baseline']}",
                    f"open_item_ratio_vs_baseline={run['open_item_ratio_vs_baseline']}",
                    "",
                ]
            )
    state_progress = packet.get("state_progress")
    if state_progress is not None:
        lines.extend(
            [
                "## State Progress",
                "",
                f"state_progress_status={state_progress['state_progress_status']}",
                f"anchor_run_stamp={state_progress['anchor_run_stamp']}",
                f"baseline_pending_approval={state_progress['baseline_pending_approval']}",
                "",
            ]
        )
        for run in state_progress["runs"]:
            lines.extend(
                [
                    f"### State Run: {run['run_stamp']}",
                    "",
                    f"pending_approval={run['pending_approval']}",
                    f"ready_to_execute={run['ready_to_execute']}",
                    f"executed={run['executed']}",
                    f"pending_approval_delta_vs_baseline={run['pending_approval_delta_vs_baseline']}",
                    "",
                ]
            )
    return "\n".join(lines)
