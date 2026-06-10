from __future__ import annotations


def _ordered_tasks(tasks: tuple[dict[str, object], ...]) -> list[dict[str, object]]:
    return sorted(
        tasks,
        key=lambda entry: (
            0 if entry["eligible"] else 1,
            entry["phase"],
            entry["task_id"],
        ),
    )


def build_promotion_readiness_packet(
    *,
    generated_at: str,
    current_phase: int,
    tasks: tuple[dict[str, object], ...],
) -> dict[str, object]:
    ordered = _ordered_tasks(tasks)
    return {
        "generated_at": generated_at,
        "current_phase": current_phase,
        "target_phase": current_phase + 1,
        "ready_count": sum(1 for entry in ordered if entry["eligible"]),
        "blocked_count": sum(1 for entry in ordered if not entry["eligible"]),
        "tasks": ordered,
    }


def render_promotion_readiness_markdown(packet: dict[str, object]) -> str:
    lines = [
        "# Task Promotion Readiness",
        "",
        f"Generated at: {packet['generated_at']}",
        f"Current phase: {packet['current_phase']}",
        f"Target phase: {packet['target_phase']}",
        f"Ready tasks: {packet['ready_count']}",
        f"Blocked tasks: {packet['blocked_count']}",
        "",
    ]
    for entry in packet["tasks"]:
        lines.extend(
            [
                f"## {'Ready' if entry['eligible'] else 'Blocked'}: {entry['task_id']}",
                "",
                f"task_ref={entry['task_ref']}",
                f"phase={entry['phase']}",
                f"blockers={','.join(entry['blockers']) or 'none'}",
                "",
            ]
        )
    return "\n".join(lines)
