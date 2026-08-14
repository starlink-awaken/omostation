"""Cockpit Ask & Proxy-Env Commands — 本地大模型快速调用与环境代理."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request

from rich.console import Console
from rich.markdown import Markdown

console = Console()

AETHERFORGE_BASE_URL = os.environ.get("AETHERFORGE_BASE_URL", "http://127.0.0.1:9290/v1")

def _get_api_key() -> str:
    """Retrieve AetherForge API key from macOS Keychain or environment."""
    key = os.environ.get("AETHERFORGE_API_KEY", "")
    if key:
        return key
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "aetherforge-gateway", "-w"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception:
        return ""

def _get_model() -> str:
    """Get the available coding model from the local directory."""
    url = f"{AETHERFORGE_BASE_URL}/models"
    req = urllib.request.Request(url)
    key = _get_api_key()
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=3.0) as response:
            catalog = json.load(response)
            items = catalog.get("data", [])
            for item in items:
                if item.get("id", "").startswith("coding"):
                    return item["id"]
            if items:
                return items[0]["id"]
    except Exception:
        pass
    return "coding-next"

def cmd_ask(args) -> int:
    """快速询问本地大模型."""
    prompt = " ".join(args.prompt) if getattr(args, "prompt", None) else None
    if not prompt:
        console.print("[yellow]用法: cockpit ask \"你的问题\"[/yellow]")
        return 1
        
    model = getattr(args, "model", None) or _get_model()
    
    url = f"{AETHERFORGE_BASE_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }
    
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"))
    req.add_header("Content-Type", "application/json")
    
    key = _get_api_key()
    if key:
        req.add_header("Authorization", f"Bearer {key}")
        
    try:
        with console.status(f"[cyan]AetherForge ({model}) is thinking...[/cyan]"):
            with urllib.request.urlopen(req, timeout=120.0) as response:
                result = json.load(response)
                content = result["choices"][0]["message"]["content"]
                
        console.print()
        console.print(Markdown(content))
        console.print()
        return 0
        
    except urllib.error.HTTPError as e:
        console.print(f"[red]HTTP Error {e.code}: {e.read().decode('utf-8')}[/red]")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1

def cmd_proxy_env(args) -> int:
    """输出兼容外部 CLI 的环境变量."""
    key = _get_api_key()
    if not key:
        console.print("[red]AETHERFORGE_API_KEY 未找到。请确认 AetherForge 已就绪或环境变量已设置。[/red]")
        return 1
        
    console.print(f"export OPENAI_API_BASE=\"{AETHERFORGE_BASE_URL}\"")
    console.print(f"export OPENAI_API_KEY=\"{key}\"")
    console.print(f"export AETHERFORGE_BASE_URL=\"{AETHERFORGE_BASE_URL}\"")
    console.print(f"export AETHERFORGE_API_KEY=\"{key}\"")
    console.print("\n# 用法: eval $(cockpit proxy-env)")
    return 0
