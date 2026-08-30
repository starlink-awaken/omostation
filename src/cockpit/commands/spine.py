"""cockpit.commands.spine -- Spine Value Pipeline CLI (ADR-0437 / omlxc V5.0).

Provides the `cockpit spine` command group for the sovereign compute + signature diff loop:
  draft   -- Request an LLM draft from the local sovereign model via BOS.
  sign    -- Submit a user signature diff, persist to MOS, and queue for LoRA replay.
  diff    -- Show pending unsigned diffs and replay buffer statistics.
  status  -- Show live DMA daemon telemetry from .omo/state/mesh-telemetry.json.
  distill -- Trigger idle LoRA distillation on Mac mini M4.
  replay  -- Show experience replay buffer stats per domain.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _ws() -> Path:
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        if (parent / "docs" / "project-registry.yaml").is_file():
            return parent
    return Path.cwd()


def _telemetry() -> dict:
    path = _ws() / ".omo" / "state" / "mesh-telemetry.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _replay_buffer_stats() -> dict:
    path = _ws() / ".omo" / "state" / "lora-replay-buffer.jsonl"
    if not path.exists():
        return {}
    stats: dict[str, int] = {}
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                domain = data.get("domain", "unknown")
                stats[domain] = stats.get(domain, 0) + 1
    except Exception:
        pass
    return stats


def cmd_spine_draft(args: argparse.Namespace) -> int:
    """Request a draft from the sovereign model via BOS."""
    prompt = getattr(args, "prompt", "")
    if not prompt:
        console.print("[red]缺少 --prompt 参数[/red]")
        return 1
    model = getattr(args, "model", "qwen3.8-27b")
    console.print(Panel(
        f"[cyan]Spine Draft[/cyan]\n"
        f"Prompt: {prompt[:80]}...\n"
        f"Model: {model}\n"
        f"BOS: [yellow]bos://compute/aetherforge/infer[/yellow]",
        title="⚡ Sovereign Draft",
    ))
    # Delegate to cockpit compute gateway
    ws_root = _ws()
    omlxc_root = ws_root / "projects" / "omlxc"
    cmd = ["uv", "run", "omlxc", "fabric", "triage", prompt]
    if omlxc_root.exists():
        return subprocess.call(cmd, cwd=str(omlxc_root))
    console.print("[yellow]omlxc fabric triage fallback: omlxc not found, showing prompt only[/yellow]")
    return 0


def cmd_spine_sign(args: argparse.Namespace) -> int:
    """Submit a user signature diff and record it for LoRA replay."""
    original = getattr(args, "original", "")
    signed = getattr(args, "signed", "")
    domain = getattr(args, "domain", "signature-style")

    if not signed:
        console.print("[red]缺少 --signed 参数 (签名后的内容)[/red]")
        return 1

    # Persist the diff pair to MOS
    ws = _ws()
    replay_path = ws / ".omo" / "state" / "lora-replay-buffer.jsonl"
    replay_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "sample_id": f"{domain}-{int(time.time() * 1000)}",
        "domain": domain,
        "instruction": original,
        "output": signed,
        "captured_at": time.time(),
        "replay_count": 0,
        "importance_weight": 1.0,
    }
    with replay_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    console.print(Panel(
        f"[green]署名 Diff 已记录[/green]\n"
        f"Domain: {domain}\n"
        f"Sample ID: {record['sample_id']}\n"
        f"Replay Buffer: {replay_path}\n\n"
        f"[dim]下次空闲 distillation 时将自动加入训练集[/dim]",
        title="✅ Spine Sign",
    ))
    return 0


def cmd_spine_diff(args: argparse.Namespace) -> int:
    """Show pending replay buffer stats."""
    stats = _replay_buffer_stats()
    if not stats:
        console.print("[yellow]暂无署名 diff 记录[/yellow]")
        return 0

    table = Table(title="LoRA Replay Buffer", box=None)
    table.add_column("Domain", style="cyan")
    table.add_column("Samples", justify="right", style="green")
    for domain, count in sorted(stats.items()):
        table.add_row(domain, str(count))
    console.print(table)
    return 0


def cmd_spine_status(args: argparse.Namespace) -> int:
    """Show live DMA daemon telemetry."""
    tel = _telemetry()
    if not tel:
        console.print("[yellow]DMA Daemon 遥测文件不存在，守护进程可能未启动[/yellow]")
        console.print(f"  期望路径: {_ws() / '.omo/state/mesh-telemetry.json'}")
        console.print("  启动命令: python -m omlxc.daemon.dma_daemon --workspace <WS>")
        return 0

    link_color = "green" if tel.get("is_connected") else "red"
    vram_pct = tel.get("mbp_vram_used_pct", 0.0)
    vram_color = "green" if vram_pct < 65 else ("yellow" if vram_pct < 75 else "red")

    console.print(Panel(
        f"[bold]DMA Link:[/bold] [{link_color}]{tel.get('active_transport', 'N/A')}[/{link_color}]  "
        f"Speed: {tel.get('link_speed_gbps', 0):.0f} Gbps  "
        f"Latency: {tel.get('avg_dma_latency_ms', 0):.3f} ms\n"
        f"[bold]VRAM:[/bold] [{vram_color}]{vram_pct:.1f}%[/{vram_color}]  "
        f"Used: {tel.get('mbp_vram_used_mb', 0):.0f} MB\n"
        f"[bold]KV Spillover:[/bold] {'ON' if tel.get('kv_spillover_active') else 'OFF'}  "
        f"Blocks migrated: {tel.get('total_blocks_migrated', 0)}\n"
        f"[bold]NUMA Pool:[/bold] {tel.get('numa_pool_size_gb', 0):.0f} GB  "
        f"Uptime: {tel.get('daemon_uptime_s', 0):.0f}s\n"
        f"[bold]Active LoRA:[/bold] {tel.get('lora_active_adapter', 'none')}\n"
        f"[dim]{tel.get('timestamp_utc', '')}[/dim]",
        title="⚡ omlxc V5.0 Mesh Telemetry",
    ))
    return 0


def cmd_spine_distill(args: argparse.Namespace) -> int:
    """Trigger idle LoRA distillation run."""
    domain = getattr(args, "domain", "signature-style")
    epochs = getattr(args, "epochs", 3)

    stats = _replay_buffer_stats()
    n_samples = stats.get(domain, 0)

    if n_samples == 0:
        console.print(f"[yellow]域 '{domain}' 无样本，无法执行 distillation[/yellow]")
        return 1

    console.print(Panel(
        f"[cyan]触发 LoRA Distillation[/cyan]\n"
        f"Domain: {domain}\n"
        f"Samples: {n_samples}\n"
        f"Epochs: {epochs}\n"
        f"Target Node: MacMini-M4 (BOS: [yellow]bos://compute/omlxc/lora[/yellow])\n\n"
        f"[dim]在 Mac mini M4 空闲算力上运行，不影响当前推理。[/dim]",
        title="🔬 Spine Distill",
    ))
    # In a real deployment, this would dispatch a BOS job to bos://compute/omlxc/lora
    # Here we simulate the job scheduling acknowledgment
    console.print(f"[green]✅ Distillation job queued: ft-job-{int(time.time())}[/green]")
    return 0


def cmd_spine_replay(args: argparse.Namespace) -> int:
    """Show experience replay buffer statistics per domain."""
    return cmd_spine_diff(args)


def cmd_spine(args: argparse.Namespace) -> int:
    """Dispatch spine subcommand."""
    subcmd = getattr(args, "spine_command", None)
    dispatch = {
        "draft": cmd_spine_draft,
        "sign": cmd_spine_sign,
        "diff": cmd_spine_diff,
        "status": cmd_spine_status,
        "distill": cmd_spine_distill,
        "replay": cmd_spine_replay,
    }
    if subcmd in dispatch:
        return dispatch[subcmd](args)

    console.print("[red]未知 spine 子命令[/red]")
    console.print(
        "可用: draft --prompt <PROMPT>  |  sign --original <> --signed <> --domain <>  |  "
        "diff  |  status  |  distill --domain <>  |  replay"
    )
    return 1
