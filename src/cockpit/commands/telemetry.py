"""Cockpit telemetry command — inspect and export Prometheus metrics (BET-Y1Q4-T8-14)."""

from __future__ import annotations

import argparse
from typing import Any

from rich.console import Console
from rich.table import Table

from cockpit.domain.exit_codes import ExitCode
from cockpit.telemetry.metrics import get_metrics_collector


def cmd_telemetry(args: argparse.Namespace) -> int:
    """Entrypoint for `cockpit telemetry`."""
    action = getattr(args, "telemetry_action", "status") or "status"
    collector = get_metrics_collector()
    is_json = getattr(args, "json", False)
    is_dry_run = getattr(args, "dry_run", False)
    console = Console()

    if action == "reset":
        if is_dry_run:
            if is_json:
                import json

                print(json.dumps({"dry_run": True, "action": "reset", "ready": True}))
            else:
                console.print("[yellow][DRY-RUN][/] 预检: 即将重置本地 CLI 埋点数据。")
            return int(ExitCode.SUCCESS)

        collector.reset()
        if is_json:
            import json

            print(json.dumps({"ok": True, "action": "reset"}))
        else:
            console.print("[green]✓[/] 本地 CLI 埋点数据已成功重置。")
        return int(ExitCode.SUCCESS)

    if action == "export":
        prom_text = collector.export_prometheus_text()
        if is_json:
            import json

            print(json.dumps({"format": "prometheus", "metrics_text": prom_text}))
        else:
            # Direct text output for Prometheus scrapers
            print(prom_text, end="")
        return int(ExitCode.SUCCESS)

    # Default action: status / summary
    summary = collector.get_summary()
    if is_json:
        import json

        payload: dict[str, Any] = {"status": "ok", "telemetry": summary}
        if is_dry_run:
            payload["dry_run"] = True
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return int(ExitCode.SUCCESS)

    # TTY Rich Table
    console.print("[bold cyan]📊 Cockpit 命令全生命周期遥测指标[/bold cyan]")
    if is_dry_run:
        console.print("[yellow][DRY-RUN 模式][/yellow]")

    summary_table = Table(title="全局概览", border_style="cyan")
    summary_table.add_column("指标 (Metric)", style="bold white")
    summary_table.add_column("数值 (Value)", style="cyan")

    summary_table.add_row("总调用次数 (Total Invocations)", str(summary["total_invocations"]))
    summary_table.add_row("总错误次数 (Total Errors)", str(summary["total_errors"]))
    err_rate_pct = f"{summary['error_rate'] * 100:.2f}%"
    summary_table.add_row("整体错误率 (Error Rate)", err_rate_pct)
    lat = summary["latency_seconds"]
    summary_table.add_row("平均执行延迟 (Avg Latency)", f"{lat['avg'] * 1000:.1f} ms")
    summary_table.add_row("P50 / P90 / P99 延迟", f"{lat['p50'] * 1000:.1f}ms / {lat['p90'] * 1000:.1f}ms / {lat['p99'] * 1000:.1f}ms")
    console.print(summary_table)

    if summary["domain_distribution"]:
        dom_table = Table(title="正交一级领域调用分布", border_style="green")
        dom_table.add_column("领域 (Domain)", style="bold cyan")
        dom_table.add_column("调用量 (Count)", style="green")
        for dom, cnt in sorted(summary["domain_distribution"].items(), key=lambda x: -x[1]):
            dom_table.add_row(dom, str(cnt))
        console.print(dom_table)

    console.print("\n[dim]💡 提示: 运行 [cyan]cockpit telemetry export[/cyan] 可输出 Prometheus 标准抓取格式。[/dim]")
    return int(ExitCode.SUCCESS)
