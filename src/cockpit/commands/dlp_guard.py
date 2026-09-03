"""cockpit.commands.dlp_guard — 外发前 DLP 扫描命令面 (BET-Y1Q4-T10-01).

扫描文件/文本, 报告敏感发现; 高危挂起 (exit 2 提示人工确认),
可选脱敏输出。引擎: ecos.governance.dlp_broker (规则 <2ms + NER 插件)。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _load_broker():
    import importlib.util
    import sys

    ws = _ws()
    broker_path = ws / "projects/ecos/src/ecos/governance/dlp_broker.py"
    spec = importlib.util.spec_from_file_location("dlp_broker", broker_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("dlp_broker", mod)
    spec.loader.exec_module(mod)
    return mod


def _ws() -> Path:
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        if (parent / "docs" / "project-registry.yaml").is_file():
            return parent
    return Path.cwd()


def cmd_dlp_guard(args: argparse.Namespace) -> int:
    """Scan a file (or text) for sensitive data before outbound release."""
    text = getattr(args, "text", "")
    file_path = getattr(args, "file", "")
    if file_path:
        p = Path(file_path).expanduser()
        if not p.is_file():
            console.print(f"[red]文件不存在: {p}[/red]")
            return 1
        text = p.read_text(encoding="utf-8", errors="replace")
    if not text:
        console.print("[red]缺少 --file 或 --text[/red]")
        return 1

    broker = _load_broker()
    findings = broker.scan(text)
    q = broker.quarantine(text, findings)

    style = "bold red" if q["high_risk_count"] else ("yellow" if findings else "green")
    console.print(
        Panel(
            f"发现: [bold]{len(findings)}[/bold] 处 | 高危: [bold]{q['high_risk_count']}[/bold] 处\n"
            f"状态: {q['status']}\n"
            f"红线: {q['red_line']}",
            title="🛡 DLP Guard",
            style=style,
        )
    )
    if findings:
        table = Table(title="敏感发现", box=None)
        table.add_column("类型", style="cyan")
        table.add_column("风险")
        table.add_column("片段", max_width=44)
        for f in findings[:20]:
            risk_style = "red" if f.risk == "high" else "yellow"
            table.add_row(f.type, f"[{risk_style}]{f.risk}[/{risk_style}]", f.snippet)
        console.print(table)

    if q["alert"]:
        console.print(Panel(f"[bold red]⛔ {q['alert']}[/bold red]\n未脱敏原文已挂起, 不会外发。", title="⚠️ 高危挂起"))

    sanitize_level = getattr(args, "sanitize", None)
    if sanitize_level:
        sanitized = broker.sanitize(text, findings, level=sanitize_level)
        out = (
            Path(file_path).with_suffix(".sanitized" + Path(file_path).suffix)
            if file_path
            else Path("dlp-sanitized.txt")
        )
        out.write_text(sanitized, encoding="utf-8")
        console.print(f"[green]脱敏输出 ({sanitize_level}): {out}[/green]")

    # exit code: 0 clean/medium-only · 2 high-risk quarantined (人工确认)
    return 2 if q["high_risk_count"] else 0
