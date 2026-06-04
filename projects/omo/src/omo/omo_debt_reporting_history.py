from __future__ import annotations

from datetime import datetime


def _validate_run_stamp(run_stamp: str) -> None:
    try:
        datetime.strptime(run_stamp, "%Y-%m-%dT%H-%M-%SZ")
    except ValueError as exc:
        raise ValueError(f"invalid dispatch run stamp: {run_stamp}") from exc


def _history_entry(
    dispatch_run: dict[str, str],
    reporting_packet: dict[str, object] | None,
) -> dict[str, object]:
    run_stamp = dispatch_run["run_stamp"]
    entry = {
        "run_stamp": run_stamp,
        "dispatch_run_ref": dispatch_run["dispatch_run_ref"],
        "reporting_ref": None,
        "reporting_exists": False,
        "report_generated_at": None,
        "total_items": None,
        "executed_item_count": None,
        "approval_coverage_rate": None,
        "execution_completion_rate": None,
    }
    if reporting_packet is None:
        return entry
    if reporting_packet.get("run_stamp") != run_stamp:
        raise ValueError(f"reporting run stamp mismatch: {reporting_packet.get('run_stamp')} != {run_stamp}")
    summary = reporting_packet["summary"]
    entry.update(
        {
            "reporting_ref": f".omo/debt/reporting/runs/{run_stamp}/current.yaml",
            "reporting_exists": True,
            "report_generated_at": reporting_packet["generated_at"],
            "total_items": summary["total_items"],
            "executed_item_count": summary["executed_item_count"],
            "approval_coverage_rate": summary["approval_coverage_rate"],
            "execution_completion_rate": summary["execution_completion_rate"],
        }
    )
    return entry


def build_reporting_history_packet(
    *,
    generated_at: str,
    dispatch_runs: tuple[dict[str, str], ...],
    reporting_packets_by_run: dict[str, dict[str, object]],
) -> dict[str, object]:
    ordered_runs = sorted(dispatch_runs, key=lambda run: run["run_stamp"], reverse=True)
    run_stamps = [run["run_stamp"] for run in ordered_runs]
    for run_stamp in run_stamps:
        _validate_run_stamp(run_stamp)
    if len(run_stamps) != len(set(run_stamps)):
        raise ValueError("duplicate dispatch run stamp in reporting history")
    runs = [
        _history_entry(dispatch_run, reporting_packets_by_run.get(dispatch_run["run_stamp"]))
        for dispatch_run in ordered_runs
    ]
    return {
        "generated_at": generated_at,
        "latest_run_stamp": runs[0]["run_stamp"] if runs else None,
        "prior_run_stamp": runs[1]["run_stamp"] if len(runs) > 1 else None,
        "run_count": len(runs),
        "runs": runs,
    }


def render_reporting_history_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Debt Reporting History",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Latest run: {packet['latest_run_stamp'] or 'none'}",
        f"Prior run: {packet['prior_run_stamp'] or 'none'}",
        "",
    ]
    for run in packet["runs"]:
        lines.extend(
            [
                f"## Run: {run['run_stamp']}",
                "",
                f"dispatch_run_ref={run['dispatch_run_ref']}",
                f"reporting_exists={'yes' if run['reporting_exists'] else 'no'}",
                f"approval_coverage_rate={run['approval_coverage_rate']}",
                f"execution_completion_rate={run['execution_completion_rate']}",
                "",
            ]
        )
    return "\n".join(lines)
