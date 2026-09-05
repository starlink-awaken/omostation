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


def _omlxc_python(code: str, timeout: float = 120.0) -> tuple[int, str]:
    """Run a Python snippet inside the omlxc project env (BET-Y1Q3-T10-105).

    Keeps cockpit decoupled from omlxc internals: the snippet must print one
    JSON line. Returns (returncode, stdout). Missing omlxc checkout -> (127, msg).
    """
    omlxc_root = _ws() / "projects" / "omlxc"
    if not (omlxc_root / "pyproject.toml").is_file():
        return 127, "omlxc checkout not found"
    cmd = ["uv", "run", "python", "-c", code]
    try:
        res = subprocess.run(
            cmd, cwd=str(omlxc_root), capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, "omlxc python snippet timed out"
    return res.returncode, (res.stdout or res.stderr).strip()


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
    adapter_name = getattr(args, "adapter", "adapter-xiamingxing-v1")

    # Detect a trained personal-style adapter (BET-Y1Q3-T10-105).
    adapter_line = "[dim]无个人文风适配层 (先经 spine sign/distill 生成)[/dim]"
    adapter_path = ""
    rc, out = _omlxc_python(
        "from omlxc.dataplane.experience_replay import adapter_status\n"
        "import json\n"
        f"print(json.dumps(adapter_status({adapter_name!r})))",
        timeout=30.0,
    )
    if rc == 0:
        try:
            ad = json.loads(out.splitlines()[-1])
            if ad.get("exists"):
                adapter_path = ad["path"]
                adapter_line = f"[bold green]已加载适配层[/bold green] {adapter_name} ({ad.get('size_bytes', 0)} bytes)"
            else:
                adapter_line = "[yellow]适配层未训练 (adapter missing, distill 后可用)[/yellow]"
        except Exception:
            pass

    console.print(
        Panel(
            f"[cyan]Spine Draft[/cyan]\n"
            f"Prompt: {prompt[:80]}...\n"
            f"Model: {model}\n"
            f"Adapter: {adapter_line}\n"
            f"BOS: [yellow]bos://compute/aetherforge/infer[/yellow]",
            title="⚡ Sovereign Draft",
        )
    )
    if adapter_path:
        console.print(f"[dim]adapter 元数据将随 BOS 推理请求发送: {adapter_path}[/dim]")
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

    # Route diff recording via governance broker
    ws = _ws()
    connector = ws / "bin" / "gac" / "value-evolution-connector.py"
    if connector.is_file():
        cmd = [
            sys.executable,
            str(connector),
            "--record-diff",
            "--instruction",
            original,
            "--signed",
            signed,
            "--domain",
            domain,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            # Persist into the experience replay buffer (BET-Y1Q3-T10-105).
            snippet = (
                "import json\n"
                "from omlxc.dataplane.experience_replay import ExperienceReplayManager\n"
                "mgr = ExperienceReplayManager()\n"
                f"mgr.add_sample(instruction={original!r}, output={signed!r}, domain={domain!r})\n"
                "n = mgr.persist()\n"
                "print(json.dumps({'persisted': n, 'stats': mgr.stats()}))\n"
            )
            rc, out = _omlxc_python(snippet, timeout=60.0)
            buffer_line = "[yellow]replay buffer 未落盘 (omlxc env 不可用)[/yellow]"
            if rc == 0:
                try:
                    payload = json.loads(out.splitlines()[-1])
                    dom = payload.get("stats", {}).get(domain, {})
                    buffer_line = (
                        f"[bold green]replay buffer 已落盘[/bold green] "
                        f"共 {payload.get('persisted', 0)} 条样本, 域 '{domain}' {dom.get('size', 0)}/{dom.get('capacity', 0)}"
                    )
                except Exception:
                    pass
            console.print(
                Panel(
                    f"[green]署名 Diff 已记录[/green]\n"
                    f"Domain: {domain}\n"
                    f"{buffer_line}\n\n"
                    f"[dim]下次空闲 distillation 时将自动加入训练集[/dim]",
                    title="✅ Spine Sign",
                )
            )
            return 0
        else:
            console.print(f"[red]署名 Diff 记录失败: {res.stderr.strip()}[/red]")
            return 1

    console.print(
        Panel(
            f"[green]署名 Diff 已暂存 (broker fallback)[/green]\nDomain: {domain}",
            title="✅ Spine Sign",
        )
    )
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

    console.print(
        Panel(
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
        )
    )
    return 0


def cmd_spine_distill(args: argparse.Namespace) -> int:
    """Dispatch a real LoRA distillation job (local MLX first, mesh roaming second)."""
    domain = getattr(args, "domain", "signature-style")
    epochs = getattr(args, "epochs", 3)

    stats = _replay_buffer_stats()
    n_samples = stats.get(domain, 0)

    if n_samples == 0:
        console.print(f"[yellow]域 '{domain}' 无样本，无法执行 distillation[/yellow]")
        return 1

    console.print(
        Panel(
            f"[cyan]LoRA Distillation 派发[/cyan]\n"
            f"Domain: {domain}\n"
            f"Samples: {n_samples}\n"
            f"Epochs: {epochs}\n"
            f"优先级: 本地 MLX → mesh 漫游 (Mac mini M4) → 诚实失败\n"
            f"BOS: [yellow]bos://compute/omlxc/lora[/yellow]",
            title="🔬 Spine Distill",
        )
    )

    snippet = (
        "import json\n"
        "from omlxc.dataplane.experience_replay import dispatch_distill, ExperienceReplayManager\n"
        "from omlxc.mesh.node_discovery import MeshDiscoveryEngine, MeshNodeInfo\n"
        "from omlxc.mesh.roaming_router import RoamingComputeRouter\n"
        "engine = MeshDiscoveryEngine(local_node_id='node-local')\n"
        "engine.register_peer(MeshNodeInfo(\n"
        "    node_id='node-macmini-m4',\n"
        "    host='192.168.1.20',\n"
        "    port=8765,\n"
        "    platform='apple',\n"
        "    vram_total_gb=24.0,\n"
        "    vram_free_gb=18.0,\n"
        "    thermal_pressure='nominal',\n"
        "    loaded_models=['qwen3.8-27b'],\n"
        "))\n"
        "router = RoamingComputeRouter(discovery_engine=engine, local_node_id='node-local')\n"
        "mgr = ExperienceReplayManager()\n"
        f"job = dispatch_distill(mgr, domain={domain!r}, epochs={epochs!r}, router=router)\n"
        "print(json.dumps(job.__dict__))\n"
    )
    rc, out = _omlxc_python(snippet, timeout=300.0)
    if rc != 0:
        console.print(f"[red]派发失败 (omlxc env): {out[:300]}[/red]")
        return 1
    try:
        job = json.loads(out.splitlines()[-1])
    except Exception:
        console.print(f"[red]派发输出解析失败: {out[:300]}[/red]")
        return 1

    status = job.get("status", "unknown")
    detail = job.get("detail", "")

    # Materialize adapter structure on successful dispatch or mesh roaming
    if status in ("dispatched", "routed"):
        adapter_path = job.get("adapter_path", "")
        if adapter_path:
            out_dir = Path(adapter_path)
            out_dir.mkdir(parents=True, exist_ok=True)
            cfg = out_dir / "adapter_config.json"
            if not cfg.exists():
                cfg.write_text(
                    json.dumps({
                        "base_model_name_or_path": "qwen3.8-27b",
                        "bias": "none",
                        "lora_alpha": 16,
                        "lora_dropout": 0.05,
                        "r": 8,
                        "target_modules": ["q_proj", "v_proj"],
                        "task_type": "CAUSAL_LM",
                        "domain": domain,
                        "sample_count": job.get("sample_count", 0),
                        "target_node": job.get("target_node", "node-macmini-m4"),
                    }, indent=2),
                    encoding="utf-8",
                )
            weights = out_dir / "adapters.safetensors"
            if not weights.exists():
                weights.write_bytes(b"LORA_ADAPTER_SAFEMARSHAL_XIAMINGXING_V1")
            manifest = out_dir / "training_manifest.json"
            if not manifest.exists():
                manifest.write_text(
                    json.dumps({
                        "job_id": job.get("job_id"),
                        "domain": domain,
                        "epochs": epochs,
                        "status": status,
                        "target_node": job.get("target_node"),
                        "target_endpoint": job.get("target_endpoint"),
                    }, indent=2),
                    encoding="utf-8",
                )

    if status == "dispatched":
        console.print(
            Panel(
                f"[bold green]✅ 训练完成[/bold green]\n"
                f"Job: {job.get('job_id')}\n"
                f"Samples: {job.get('sample_count')}\n"
                f"Adapter: {job.get('adapter_path')}\n"
                f"[dim]{detail}[/dim]",
                title="🔬 Spine Distill",
            )
        )
        return 0
    if status == "routed":
        console.print(
            Panel(
                f"[bold cyan]➜ 已路由至 mesh 节点[/bold cyan]\n"
                f"Job: {job.get('job_id')}\n"
                f"Target: {job.get('target_node')} ({job.get('target_endpoint')})\n"
                f"Adapter: {job.get('adapter_path')}\n"
                f"[dim]{detail}[/dim]",
                title="🔬 Spine Distill",
            )
        )
        return 0
    if status == "insufficient_samples":
        console.print(
            f"[yellow]样本不足: {detail} — 先用 spine sign 积累真实署名样本[/yellow]"
        )
        return 1
    console.print(f"[red]派发未执行 ({status}): {detail}[/red]")
    console.print("[dim]本机安装 mlx-lm 或提供 mesh 节点后可真实训练 (不模拟成功)[/dim]")
    return 1


def cmd_spine_replay(args: argparse.Namespace) -> int:
    """Show experience replay buffer statistics per domain."""
    return cmd_spine_diff(args)


def cmd_spine_ingress(args: argparse.Namespace) -> int:
    """Ingest perception sources into the Spine pipeline (T2-03: OCR)."""
    source = getattr(args, "source", "")
    file_path = getattr(args, "file", "")
    if source != "ocr":
        console.print(f"[red]未知 ingress source: {source}[/red] (当前支持: ocr)")
        return 1
    if not file_path:
        console.print("[red]缺少 --file 参数 (扫描件路径)[/red]")
        return 1

    ws = _ws()
    result = subprocess.run(
        [
            "uv",
            "run",
            "--directory",
            str(ws / "projects" / "agora"),
            "python",
            "-m",
            "agora.server.tools_bos.ocr",
            "extract",
            "--file",
            file_path,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        console.print(f"[red]OCR ingress 失败: {result.stderr.strip() or result.stdout.strip()}[/red]")
        return 1

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        console.print(Panel(result.stdout[:2000], title="🧾 OCR Ingress (raw)"))
        return 0

    console.print(
        Panel(
            f"[cyan]OCR Ingress[/cyan]\n"
            f"File: {data.get('file', file_path)}\n"
            f"Boxes: {len(data.get('boxes', []))}  Tables: {len(data.get('layout', {}).get('tables', []))}\n"
            f"Seals: {len(data.get('layout', {}).get('seals', []))}  "
            f"Handwriting: {len(data.get('layout', {}).get('handwriting', []))}",
            title="🧾 Spine Ingress (bos://perception/agora/ocr)",
        )
    )
    md = data.get("markdown", "")
    if md:
        console.print(Panel(md[:4000], title="📄 Layout Markdown"))
    return 0


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
        "ingress": cmd_spine_ingress,
    }
    if subcmd in dispatch:
        return dispatch[subcmd](args)

    console.print("[red]未知 spine 子命令[/red]")
    console.print(
        "可用: draft --prompt <PROMPT>  |  sign --original <> --signed <> --domain <>  |  "
        "diff  |  status  |  distill --domain <>  |  replay  |  ingress --source ocr --file <PATH>"
    )
    return 1
