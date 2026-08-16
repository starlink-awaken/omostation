"""cockpit.commands.mesh — omlx 算力网格路由入口。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from urllib import request as urlrequest

from rich.console import Console

console = Console()


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _mesh_router_url() -> str:
    port = os.environ.get("MOF_MESH_PORT", "7440")
    return f"http://127.0.0.1:{port}"


def _urlopen_safe(url: str, timeout: float = 5.0):
    """只允许 http/https 的内部 urlopen 包装。"""
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"不支持的 URL scheme: {url}")
    return urlrequest.urlopen(url, timeout=timeout)  # noqa: S310


def cmd_mesh(args: argparse.Namespace) -> int:
    """算力网格入口：nodes / status / route --model / serve。"""
    subcmd = getattr(args, "mesh_command", None)

    if subcmd == "nodes":
        try:
            with _urlopen_safe(f"{_mesh_router_url()}/nodes") as resp:
                console.print_json(data=json.loads(resp.read()))
                return 0
        except Exception as exc:
            console.print(f"[red]获取节点失败: {exc}[/red]")
            return 1
    if subcmd == "status":
        try:
            with _urlopen_safe(f"{_mesh_router_url()}/health") as resp:
                console.print_json(data=json.loads(resp.read()))
                return 0
        except Exception as exc:
            console.print(f"[red]获取状态失败: {exc}[/red]")
            return 1
    if subcmd == "fabric":
        omlxc_root = _workspace_root() / "projects" / "omlxc"
        return subprocess.call(["uv", "run", "omlxc", "fabric", "inspect"], cwd=str(omlxc_root))
    if subcmd == "triage":
        prompt = getattr(args, "prompt", "")
        omlxc_root = _workspace_root() / "projects" / "omlxc"
        return subprocess.call(["uv", "run", "omlxc", "fabric", "triage", prompt], cwd=str(omlxc_root))
    if subcmd == "vram":
        model = getattr(args, "model", "coding")
        tokens = str(getattr(args, "tokens", 32768))
        omlxc_root = _workspace_root() / "projects" / "omlxc"
        return subprocess.call(["uv", "run", "omlxc", "fabric", "vram", model, tokens], cwd=str(omlxc_root))
    if subcmd == "warm":
        model = getattr(args, "model", "coding")
        omlxc_root = _workspace_root() / "projects" / "omlxc"
        return subprocess.call(["uv", "run", "omlxc", "fabric", "warm", "--model", model], cwd=str(omlxc_root))
    if subcmd == "route":
        model = getattr(args, "model", None)
        if not model:
            console.print("[red]缺少 --model[/red]")
            return 1
        try:
            with _urlopen_safe(f"{_mesh_router_url()}/route?model={model}") as resp:
                console.print_json(data=json.loads(resp.read()))
                return 0
        except Exception as exc:
            console.print(f"[red]路由选择失败: {exc}[/red]")
            return 1
    if subcmd == "serve":
        mesh_project = _workspace_root() / "projects" / "mesh" / "router.py"
        if mesh_project.exists():
            return subprocess.call(["python3", str(mesh_project.resolve())])
        console.print("[red]未找到 mesh router 实现[/red]")
        return 1

    console.print("[red]未知 mesh 子命令[/red]")
    console.print("可用: nodes, status, fabric, triage <PROMPT>, vram <MODEL> <TOKENS>, route --model <MODEL>, serve")
    return 1
