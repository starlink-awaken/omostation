"""omo_debt_render — debt packet markdown renderers (P110 split from omo_debt.py).

P110 关联: TASK-F7114ABA (omo lint god-module 800L 硬规则).
omo_debt.py 1085L 拆分: 165L 渲染逻辑独立成此模块, omo_debt.py 降至 <800L.

提供 _render_* 辅助函数 (markdown 模板), 由 omo_debt.write_action_packet /
write_owner_routing / write_dispatch_packet 等 write_* 函数调用.
通过 omo.omo_debt 顶层 re-export 保留向后兼容 (调用方 `from omo.omo_debt import _render_*` 仍可用).
"""

from __future__ import annotations

from typing import Any


def _render_section(title: str, item_ids: list[str]) -> str:
    lines = [f"## {title}", ""]
    if item_ids:
        lines.extend([f"- `{item_id}`" for item_id in item_ids])
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _render_queue_section(
    title: str, entries: list[dict[str, Any]], reason_key: str
) -> str:
    lines = [f"## {title}", ""]
    if entries:
        for entry in entries:
            reason = entry.get(reason_key, "n/a")
            next_review = entry.get("next_review_at") or "unscheduled"
            lines.append(f"- `{entry['id']}` — {reason} ({next_review})")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _render_action_packet_section(title: str, entries: list[dict[str, Any]]) -> str:
    lines = [f"## {title}", ""]
    if entries:
        for entry in entries:
            lines.append(
                f"- `{entry['id']}` — {entry['reason']}` — `{entry['suggested_command']}`"
                if False
                else f"- `{entry['id']}` — {entry['reason']} — `{entry['suggested_command']}`"
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _render_owner_routing_section(owner_packet: dict[str, Any]) -> str:
    lines = [f"## Owner: {owner_packet['owner']}", ""]
    lines.append(
        "Summary: "
        f"{owner_packet['summary']['total_count']} items; "
        f"revalidate_now={owner_packet['summary']['lane_counts']['revalidate_now']}, "
        f"schedule_now={owner_packet['summary']['lane_counts']['schedule_now']}, "
        f"escalate_now={owner_packet['summary']['lane_counts']['escalate_now']}"
    )
    lines.append("")
    for lane_title, lane_name in [
        ("Revalidate Now", "revalidate_now"),
        ("Schedule Now", "schedule_now"),
        ("Escalate Now", "escalate_now"),
        ("Continue Mitigation", "continue_mitigation"),
        ("Watch Only", "watch_only"),
    ]:
        lane_entries = [
            entry
            for entry in owner_packet["entries"]
            if entry["primary_lane"] == lane_name
        ]
        if not lane_entries:
            continue
        lines.extend([f"### {lane_title}", ""])
        for entry in lane_entries:
            flags = ", ".join(entry["priority_flags"]) or "none"
            lines.append(
                f"- `{entry['id']}` — {entry['reason']} — flags: {flags} — `{entry['shell_command']}`"
            )
        lines.append("")
    return "\n".join(lines)


def _render_dispatch_owner_section(owner_packet: dict[str, Any]) -> str:
    lines = [f"## Owner: {owner_packet['owner']}", ""]
    lines.append(f"Dispatched items: {owner_packet['item_count']}")
    lines.append("")
    lines.append("### Frozen Commands")
    lines.append("")
    if owner_packet["entries"]:
        for entry in owner_packet["entries"]:
            lines.append(f"- `{entry['id']}` — `{entry['command']}`")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "_render_action_packet_section",
    "_render_dispatch_owner_section",
    "_render_owner_routing_section",
    "_render_queue_section",
    "_render_section",
]
