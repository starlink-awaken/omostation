"""cockpit.commands.workflow_mesh — workflow-mesh 可视化入口.

workflow-mesh 是 delivery 流水线的事件织网, 事件存储在:
  .omo/_knowledge/workflow-mesh/events.jsonl

本命令读取事件文件, 让 workflow-mesh 从"暗面"变为用户可见.

子命令:
  status    — workflow-mesh 运行状态 (最近事件统计)
  delivery  — delivery pipeline 状态
  events    — 查看最近 N 条事件

设计: KISS — 直接读 jsonl 文件, 无服务依赖.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter
from pathlib import Path

from .base import _get_console, _panel

_WORKSPACE = Path(__file__).resolve().parents[5]
_EVENTS_PATH = _WORKSPACE / ".omo" / "_knowledge" / "workflow-mesh" / "events.jsonl"
_DELIVERY_EVENTS = _WORKSPACE / ".omo" / "_delivery" / "agent-workflows" / "events.jsonl"


def _read_events(path: Path, limit: int = 100) -> list[dict]:
    """读取 jsonl 事件文件, 返回最近 limit 条 (倒序)."""
    if not path.exists():
        return []
    events: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return []
    for line in reversed(lines[-limit * 3 :]):  # 多读一些再截断
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(events) >= limit:
            break
    return events


def cmd_mesh_status(args: argparse.Namespace) -> int:
    """cockpit workflow mesh status — workflow-mesh 运行状态."""
    console = _get_console()
    events = _read_events(_EVENTS_PATH, limit=200)

    if not events:
        # 降级到 delivery events
        events = _read_events(_DELIVERY_EVENTS, limit=200)
        source = _DELIVERY_EVENTS
    else:
        source = _EVENTS_PATH

    if not events:
        console.print(
            _panel(
                f"[yellow]⚠️  无 workflow-mesh 事件[/yellow]\n查找路径:\n  {_EVENTS_PATH}\n  {_DELIVERY_EVENTS}",
                "yellow",
            )
        )
        return 0

    # 统计
    kind_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    for e in events:
        kind = e.get("kind") or e.get("event") or e.get("type") or "unknown"
        kind_counter[kind] += 1
        status = e.get("status") or e.get("track") or ""
        if status:
            status_counter[status] += 1

    latest_ts = events[0].get("ts") or events[0].get("timestamp") or "?"

    console.print(
        _panel(
            f"[bold cyan]🕸️  Workflow Mesh 状态[/bold cyan]\n"
            f"事件源: {source.relative_to(_WORKSPACE) if source.is_relative_to(_WORKSPACE) else source}\n"
            f"最近事件: {latest_ts}\n"
            f"事件总数 (采样): {len(events)}",
            "cyan",
        )
    )

    from rich import box as rich_box
    from rich.table import Table

    if kind_counter:
        table = Table(box=rich_box.ROUNDED, header_style="bold cyan", title="事件类型分布")
        table.add_column("类型", style="bold")
        table.add_column("次数", style="green", justify="right")
        for kind, count in kind_counter.most_common(10):
            table.add_row(kind, str(count))
        console.print(table)

    if status_counter:
        table2 = Table(box=rich_box.ROUNDED, header_style="bold cyan", title="状态/轨道分布")
        table2.add_column("状态", style="bold")
        table2.add_column("次数", style="green", justify="right")
        for status, count in status_counter.most_common(10):
            table2.add_row(status, str(count))
        console.print(table2)

    return 0


def cmd_mesh_delivery(args: argparse.Namespace) -> int:
    """cockpit workflow mesh delivery — delivery pipeline 状态."""
    console = _get_console()
    events = _read_events(_DELIVERY_EVENTS, limit=500)

    if not events:
        console.print("[yellow]⚠️  无 delivery 事件[/yellow]")
        return 0

    # 按 track 分类
    track_counter: Counter[str] = Counter()
    for e in events:
        track = e.get("track") or "unknown"
        track_counter[track] += 1

    console.print(_panel(f"[bold green]📦 Delivery Pipeline · {len(events)} 事件[/bold green]", "green"))

    from rich import box as rich_box
    from rich.table import Table

    table = Table(box=rich_box.ROUNDED, header_style="bold green")
    table.add_column("轨道 (track)", style="bold")
    table.add_column("事件数", style="green", justify="right")
    table.add_column("占比", style="cyan", justify="right")
    total = len(events)
    for track, count in track_counter.most_common():
        pct = f"{count / total * 100:.1f}%"
        table.add_row(track, str(count), pct)
    console.print(table)

    governance_pct = track_counter.get("governance", 0) / total * 100 if total else 0
    if governance_pct > 40:
        console.print(f"\n[yellow]⚠️  治理事件占比 {governance_pct:.1f}% (GaC 门禁阈值 40%)[/yellow]")
    else:
        console.print(f"\n[green]✅ 治理事件占比 {governance_pct:.1f}% (≤40% 达标)[/green]")

    return 0


def cmd_mesh_events(args: argparse.Namespace) -> int:
    """cockpit workflow mesh events — 查看最近事件."""
    console = _get_console()
    limit = getattr(args, "limit", 20)
    events = _read_events(_EVENTS_PATH, limit=limit)
    if not events:
        events = _read_events(_DELIVERY_EVENTS, limit=limit)

    if not events:
        console.print("[yellow]⚠️  无事件[/yellow]")
        return 0

    from rich import box as rich_box
    from rich.table import Table

    table = Table(box=rich_box.ROUNDED, header_style="bold cyan", title=f"最近 {len(events)} 条事件")
    table.add_column("#", style="dim", width=3)
    table.add_column("时间", style="cyan", width=20)
    table.add_column("类型", style="bold")
    table.add_column("状态", style="green")
    table.add_column("详情", style="dim", no_wrap=False)

    for i, e in enumerate(events, 1):
        ts = e.get("ts") or e.get("timestamp") or "?"
        ts_short = str(ts)[:19]
        kind = e.get("kind") or e.get("event") or e.get("type") or "?"
        status = e.get("status") or e.get("track") or ""
        detail_keys = [k for k in ("task_id", "run_id", "workflow_id", "source") if k in e]
        detail = ", ".join(f"{k}={e[k]}" for k in detail_keys[:2])
        table.add_row(str(i), ts_short, str(kind)[:20], str(status)[:12], detail[:40])
    console.print(table)
    return 0


def cmd_workflow_mesh(args: argparse.Namespace) -> int:
    """cockpit workflow mesh — workflow-mesh 可视化入口."""
    sub = getattr(args, "mesh_command", None)
    if sub == "status":
        return cmd_mesh_status(args)
    if sub == "delivery":
        return cmd_mesh_delivery(args)
    if sub == "events":
        return cmd_mesh_events(args)

    console = _get_console()
    console.print(_panel("[bold cyan]🕸️  Workflow Mesh · 交付事件织网[/bold cyan]", "cyan"))
    console.print("\n[bold]可用子命令:[/]")
    console.print("  [cyan]cockpit workflow mesh status[/]    — 运行状态")
    console.print("  [cyan]cockpit workflow mesh delivery[/]  — delivery pipeline")
    console.print("  [cyan]cockpit workflow mesh events[/]    — 最近事件")
    return 0


# ── Personal dogfood CLI (thin HTTP client over existing APIs) ─────────


def _base_url() -> str:
    """Resolve cockpit HTTP API base from env (COCKPIT_API_URL or default 8090)."""
    return os.environ.get("COCKPIT_API_URL", "http://127.0.0.1:8090")


def _api_post(path: str, payload: dict) -> tuple[int, dict]:
    """POST JSON to cockpit API, return (status_code, response_json).

    Raises a RuntimeError with a clear message on connection or decode failure.
    """
    import httpx

    try:
        with httpx.Client(base_url=_base_url(), timeout=15.0) as client:
            response = client.post(path, json=payload)
        return response.status_code, response.json()
    except httpx.ConnectError as exc:
        raise RuntimeError(f"cannot connect to {_base_url()}: {exc}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"HTTP error: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"invalid response from server: {exc}") from exc


def _api_get(path: str, params: dict | None = None) -> tuple[int, dict]:
    """GET JSON from cockpit API, return (status_code, response_json).

    Raises a RuntimeError with a clear message on connection or decode failure.
    """
    import httpx

    try:
        with httpx.Client(base_url=_base_url(), timeout=15.0) as client:
            response = client.get(path, params=params or {})
        return response.status_code, response.json()
    except httpx.ConnectError as exc:
        raise RuntimeError(f"cannot connect to {_base_url()}: {exc}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"HTTP error: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"invalid response from server: {exc}") from exc


def _api_result(console, status: int, body: dict, action: str) -> int:
    """Unified success/failure check: ok=true → 0, otherwise print error → 1."""
    if status == 200 and body.get("ok") is True:
        return 0
    error = body.get("error", "unknown") if isinstance(body, dict) else "invalid_response"
    console.print(f"[red]✗ {action} failed: {error}[/red]")
    return 1


def _personal_setup(rest: list[str]) -> int:
    """cockpit workflow mesh personal setup — seed trusted-local role."""
    parser = argparse.ArgumentParser(prog="cockpit workflow mesh personal setup")
    parser.add_argument("--principal", default="principal:alice")
    parser.add_argument("--role", default="role:personal-steward")
    parser.add_argument("--role-name", default="Personal Steward")
    parser.add_argument("--scope", default="personal")
    parser.add_argument("--responsibilities", nargs="*", default=["responsibility:follow-up"])
    args = parser.parse_args(rest)
    console = _get_console()
    try:
        status, body = _api_post(
            "/api/workflow-mesh/personal-episode/setup",
            {
                "principal_id": args.principal,
                "role_id": args.role,
                "role_name": args.role_name,
                "scope": args.scope,
                "responsibilities": args.responsibilities,
            },
        )
    except RuntimeError as exc:
        console.print(f"[red]✗ Setup failed: {exc}[/red]")
        return 1
    if _api_result(console, status, body, "Setup"):
        return 1
    console.print(
        _panel(
            f"[green]✅ Role assignment: {body.get('status')}[/green]\nPrincipal: {args.principal}\nRole: {args.role}",
            "green",
        )
    )
    return 0


def _personal_ingest(rest: list[str]) -> int:
    """cockpit workflow mesh personal ingest — resolve local Markdown into episode."""
    parser = argparse.ArgumentParser(prog="cockpit workflow mesh personal ingest")
    parser.add_argument("--item-id", required=True, help="Opaque Iris item ID (base64 relative path)")
    parser.add_argument("--principal", default="principal:alice")
    parser.add_argument("--role", default="role:personal-steward")
    parser.add_argument("--responsibility", default="responsibility:follow-up")
    parser.add_argument("--executor", default="agent:personal-steward")
    args = parser.parse_args(rest)
    console = _get_console()
    try:
        status, body = _api_post(
            "/api/workflow-mesh/personal-signal/ingest",
            {
                "item_id": args.item_id,
                "principal_id": args.principal,
                "role_id": args.role,
                "responsibility_id": args.responsibility,
                "executor_id": args.executor,
            },
        )
    except RuntimeError as exc:
        console.print(f"[red]✗ Ingest failed: {exc}[/red]")
        return 1
    if _api_result(console, status, body, "Ingest"):
        return 1
    episode = body.get("episode", {})
    console.print(
        _panel(
            f"[green]✅ Episode created: {episode.get('episode_id')}[/green]\n"
            f"Summary: {episode.get('summary', '?')}\n"
            f"Reused: {episode.get('reused', False)}",
            "green",
        )
    )
    return 0


def _personal_confirm(rest: list[str]) -> int:
    """cockpit workflow mesh personal confirm — human-confirmed mandate."""
    parser = argparse.ArgumentParser(prog="cockpit workflow mesh personal confirm")
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--principal", default="principal:alice")
    parser.add_argument("--executor", default="agent:personal-steward")
    args = parser.parse_args(rest)
    console = _get_console()
    try:
        status, body = _api_post(
            "/api/workflow-mesh/personal-episode/confirm",
            {
                "episode_id": args.episode_id,
                "principal_id": args.principal,
                "executor_id": args.executor,
                "human_confirmed": True,
            },
        )
    except RuntimeError as exc:
        console.print(f"[red]✗ Confirm failed: {exc}[/red]")
        return 1
    if _api_result(console, status, body, "Confirm"):
        return 1
    confirmation = body.get("confirmation", {})
    console.print(
        _panel(
            f"[green]✅ Mandate granted: {confirmation.get('mandate_id')}[/green]\nEpisode: {args.episode_id}",
            "green",
        )
    )
    return 0


def _personal_draft(rest: list[str]) -> int:
    """cockpit workflow mesh personal draft — PEP-gated local draft creation.

    Without --title/--context/--deadline/--next-action, the server builds a
    draft deterministically from the safe persisted Episode snapshot.
    """
    parser = argparse.ArgumentParser(prog="cockpit workflow mesh personal draft")
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--principal", default="principal:alice")
    parser.add_argument("--title", default=None)
    parser.add_argument("--context", default=None)
    parser.add_argument("--deadline", default=None)
    parser.add_argument("--next-action", dest="next_action", default=None)
    args = parser.parse_args(rest)
    console = _get_console()
    payload: dict = {"episode_id": args.episode_id, "principal_id": args.principal}
    # Only include draft fields when ALL are present (all-or-nothing contract).
    draft_keys = ("title", "context", "deadline", "next_action")
    provided_count = sum(1 for k in draft_keys if getattr(args, k.replace("-", "_")) is not None)
    if provided_count == len(draft_keys):
        payload.update({k: getattr(args, k.replace("-", "_")) for k in draft_keys})
    elif provided_count > 0:
        console.print(
            "[red]✗ Either provide ALL draft fields (--title --context --deadline --next-action) "
            "or omit them ALL for a system-built draft.[/red]"
        )
        return 1
    try:
        status, body = _api_post("/api/workflow-mesh/personal-episode/execute", payload)
    except RuntimeError as exc:
        console.print(f"[red]✗ Draft failed: {exc}[/red]")
        return 1
    if _api_result(console, status, body, "Draft"):
        return 1
    origin = body.get("output_origin", "?")
    console.print(
        _panel(
            f"[green]✅ Draft created ({origin})[/green]\n"
            f"Local draft recorded: {body.get('local_draft_recorded', False)}\n"
            f"Episode: {args.episode_id}",
            "green",
        )
    )
    return 0


def _personal_feedback(rest: list[str]) -> int:
    """cockpit workflow mesh personal feedback — record human outcome.

    Optional --feedback-id identifies one idempotent request. Burden values
    are non-negative finite values; omitted values are not sent.
    """
    parser = argparse.ArgumentParser(prog="cockpit workflow mesh personal feedback")
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--principal", default="principal:alice")
    parser.add_argument("--feedback-id", default=None)
    parser.add_argument("--verdict", required=True, choices=["accept", "edit", "reject", "defer", "ignore"])
    parser.add_argument("--review-duration-seconds", type=float, default=None)
    parser.add_argument("--estimated-time-saved-seconds", type=float, default=None)
    parser.add_argument("--revision-digest", default=None)
    parser.add_argument(
        "--changed-field",
        action="append",
        choices=["title", "context", "deadline", "next_action"],
        default=None,
    )
    args = parser.parse_args(rest)
    console = _get_console()
    for field, value in (
        ("review_duration_seconds", args.review_duration_seconds),
        ("estimated_time_saved_seconds", args.estimated_time_saved_seconds),
    ):
        if value is not None and (value < 0 or not math.isfinite(value)):
            console.print(f"[red]✗ Feedback failed: {field} must be non-negative and finite[/red]")
            return 1
    payload: dict = {
        "episode_id": args.episode_id,
        "principal_id": args.principal,
        "verdict": args.verdict,
    }
    if args.review_duration_seconds is not None:
        payload["review_duration_seconds"] = args.review_duration_seconds
    if args.estimated_time_saved_seconds is not None:
        payload["estimated_time_saved_seconds"] = args.estimated_time_saved_seconds
    if args.feedback_id is not None:
        payload["feedback_id"] = args.feedback_id
    if args.revision_digest is not None:
        payload["revision_digest"] = args.revision_digest
    if args.changed_field is not None:
        payload["changed_fields"] = args.changed_field
    try:
        status, body = _api_post(
            "/api/workflow-mesh/personal-episode/feedback",
            payload,
        )
    except RuntimeError as exc:
        console.print(f"[red]✗ Feedback failed: {exc}[/red]")
        return 1
    if _api_result(console, status, body, "Feedback"):
        return 1
    console.print(
        _panel(
            f"[green]✅ Feedback recorded: {args.verdict}[/green]\nSequence: {body.get('sequence', '?')}",
            "green",
        )
    )
    return 0


def _personal_status(rest: list[str]) -> int:
    """cockpit workflow mesh personal status — read-only episode summary.

    Includes the OMO principal observation: readiness gate (not_ready /
    collecting / passed), gate gaps, weekly samples, verdict
    distribution and evidence origin counts.
    """
    parser = argparse.ArgumentParser(prog="cockpit workflow mesh personal status")
    parser.add_argument("--principal", default="principal:alice")
    args = parser.parse_args(rest)
    console = _get_console()
    try:
        status, body = _api_get(
            "/api/workflow-mesh/personal-episode/status",
            params={"principal_id": args.principal},
        )
    except RuntimeError as exc:
        console.print(f"[red]✗ Status failed: {exc}[/red]")
        return 1
    if _api_result(console, status, body, "Status"):
        return 1
    summary = body.get("summary", {})
    observation = body.get("observation")
    readiness = observation.get("readiness", "?") if observation else "?"
    console.print(
        _panel(
            f"[bold cyan]📊 Personal Episode Status[/bold cyan]\n"
            f"Principal: {args.principal}\n"
            f"Total episodes: {summary.get('total_episodes', 0)}\n"
            f"Pending confirmation: {summary.get('pending_confirmation', 0)}\n"
            f"Inbox cards: {summary.get('inbox_cards', 0)}\n"
            f"Readiness: {readiness}",
            "cyan",
        )
    )

    # Observation details
    if observation:
        gaps = observation.get("gate_gaps", [])
        if gaps:
            console.print("[yellow]Gate gaps:[/yellow]")
            for gap in gaps:
                console.print(f"  • {gap}")
        verdict_dist = observation.get("verdict_distribution", {})
        if verdict_dist:
            from rich import box as rich_box
            from rich.table import Table

            table = Table(box=rich_box.ROUNDED, header_style="bold cyan", title="Verdict Distribution")
            table.add_column("Verdict", style="bold")
            table.add_column("Count", style="green", justify="right")
            for verdict, count in sorted(verdict_dist.items()):
                table.add_row(verdict, str(count))
            console.print(table)

    pending = body.get("pending", [])
    if pending:
        from rich import box as rich_box
        from rich.table import Table

        table = Table(box=rich_box.ROUNDED, header_style="bold cyan", title="Pending Episodes")
        table.add_column("Episode", style="bold")
        table.add_column("Summary", style="dim")
        for card in pending[:10]:
            table.add_row(
                str(card.get("episode", "?"))[:36],
                str(card.get("summary", ""))[:50],
            )
        console.print(table)
    return 0


def cmd_personal(args: argparse.Namespace) -> int:
    """cockpit workflow mesh personal — personal dogfood CLI (thin HTTP client)."""
    sub = getattr(args, "personal_command", None)
    rest = list(getattr(args, "rest", []))

    handlers = {
        "setup": _personal_setup,
        "ingest": _personal_ingest,
        "confirm": _personal_confirm,
        "draft": _personal_draft,
        "feedback": _personal_feedback,
        "status": _personal_status,
    }

    if sub in handlers:
        return handlers[sub](rest)

    console = _get_console()
    console.print(_panel("[bold cyan]👤 Personal Dogfood CLI[/bold cyan]", "cyan"))
    console.print("\n[bold]可用子命令:[/]")
    console.print("  [cyan]setup[/]     — Seed trusted-local role (idempotent)")
    console.print("  [cyan]ingest[/]    — Resolve local Markdown into episode")
    console.print("  [cyan]confirm[/]   — Human-confirmed mandate")
    console.print("  [cyan]draft[/]     — PEP-gated local draft (system or caller-authored)")
    console.print("  [cyan]feedback[/]  — Record human outcome (accept/edit/reject/defer/ignore)")
    console.print("  [cyan]status[/]    — Read-only episode summary")
    console.print("\n[dim]Set COCKPIT_API_URL to target a specific server.[/]")
    return 0
