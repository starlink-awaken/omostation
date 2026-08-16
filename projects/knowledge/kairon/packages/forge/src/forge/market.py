"""
Forge Market — GitHub 工具市场安装器

功能:
  forge market install <github-url> [--name <alias>]
  forge market list
  forge market remove <name>

流程:
  URL → git clone --depth 1 → 结构校验 → tools-registry.json 注册 → Agora 同步

安装目标:
  ~/SharedWork/Forge/installed/<name>/
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from forge.forge_config import FORGE_ROOT
from forge.forge_config import REGISTRY as TOOLS_REGISTRY

# ── 默认安装目标 ──
# 注意: ~/SharedWork → /Volumes/SharedWork (可能未挂载)
# 使用 ~/.local/share/forge/market/ 作为本地安装目标
INSTALL_DIR = Path.home() / ".local" / "share" / "forge" / "market"

# ── Capabilities root — patchable for tests ──
# Mirrors agora.mcp.forge_loader.CAPS_ROOT so tests can monkeypatch this module.
try:
    from agora.mcp.forge_loader import CAPS_ROOT, MARKET_REGISTRY  # type: ignore[import-not-found]
except ImportError:
    CAPS_ROOT = Path.home() / "Workspace" / ".omo" / "capabilities"
    MARKET_REGISTRY: Path = CAPS_ROOT / "market.json"  # type: ignore[assignment]


def _load_tools_registry() -> dict:
    """Load the main tools-registry.json."""
    if TOOLS_REGISTRY.exists():
        return cast("dict", json.loads(TOOLS_REGISTRY.read_text(encoding="utf-8")))
    return {"schema_version": "1.2", "tools": []}


def _save_tools_registry(reg: dict) -> None:
    """Save the main tools-registry.json."""
    TOOLS_REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def _github_url_to_name(url: str) -> str:
    """Extract repo name from GitHub URL.
    https://github.com/owner/repo.git → repo
    git@github.com:owner/repo.git → repo
    owner/repo → repo
    """
    url = url.rstrip("/").rstrip(".git")
    if "github.com" in url:
        return url.split("/")[-1]
    elif ":" in url:
        return url.split(":")[-1].split("/")[-1]
    return url.split("/")[-1] if "/" in url else url


def _validate_repo_structure(repo_path: Path) -> list[str]:
    """Validate that the cloned repo has a recognizable structure.

    Returns list of issues (empty = valid).
    """
    issues = []

    # Check for key entry files
    has_entry = False
    entry_candidates = [
        "SKILL.md",
        "main.py",
        "mcp_server.py",
        "server.py",
        "cli.py",
        "index.js",
        "package.json",
        "pyproject.toml",
        "Cargo.toml",
        "Dockerfile",
    ]

    for candidate in entry_candidates:
        if (repo_path / candidate).exists():
            has_entry = True
            break

    if not has_entry:
        issues.append(f"未找到入口文件 ({', '.join(entry_candidates[:4])}...)")

    # Check for README
    has_readme = any((repo_path / f"README{f}").exists() for f in ["", ".md"])
    if not has_readme:
        issues.append("缺少 README")

    return issues


def _register_in_tools_registry(
    name: str,
    repo_url: str,
    install_path: Path,
    description: str = "",
) -> None:
    """Register the installed tool in tools-registry.json."""
    reg = _load_tools_registry()
    now = datetime.now().strftime("%Y-%m-%d")

    # Check for existing entry
    for tool in reg.get("tools", []):
        if tool.get("id") == name:
            tool["updated"] = now
            tool["source"]["url"] = repo_url
            tool["source"]["path"] = str(install_path)
            tool["status"] = "active"
            _save_tools_registry(reg)
            return

    # New entry
    entry = {
        "id": name,
        "name": name,
        "type": "tool",
        "status": "active",
        "category": ["MCP", "Market"],
        "capabilities": ["market-installed"],
        "source": {
            "provider": "github-market",
            "url": repo_url,
            "path": str(install_path),
        },
        "description": description,
        "added": now,
        "updated": now,
    }
    reg.setdefault("tools", []).append(entry)
    _save_tools_registry(reg)


def _unregister_from_tools_registry(name: str) -> bool:
    """Remove from tools-registry.json. Returns True if found."""
    reg = _load_tools_registry()
    before = len(reg.get("tools", []))
    reg["tools"] = [t for t in reg.get("tools", []) if t.get("id") != name]
    if len(reg["tools"]) == before:
        return False
    _save_tools_registry(reg)
    return True


def _sync_to_agora() -> None:
    """Run sync_registry to notify Agora of changes."""
    sync_script = FORGE_ROOT / "src" / "sync_registry.py"
    if sync_script.exists():
        try:
            subprocess.run(
                [sys.executable, str(sync_script), "--silent"],
                capture_output=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            pass


def install(url: str, alias: str | None = None) -> dict[str, Any]:
    """Install a tool from a git URL into the Forge market.

    Args:
        url: GitHub repository URL (https://github.com/owner/repo)
        alias: Optional short name (defaults to repo name)

    Returns:
        dict with status/name/path/issues
    """
    name = alias or _github_url_to_name(url)
    target = INSTALL_DIR / name

    # Step 1: ensure install directory exists (handle symlinks)
    if not INSTALL_DIR.exists():
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    elif not INSTALL_DIR.is_dir():
        return {"status": "error", "name": name, "error": f"安装路径存在但不是目录: {INSTALL_DIR}"}

    if target.exists():
        return {"status": "exists", "name": name, "path": str(target), "issues": ["已安装"]}

    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(target)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return {"status": "error", "name": name, "error": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"status": "error", "name": name, "error": "克隆超时 (120s)"}

    # Step 2: validate
    issues = _validate_repo_structure(target)

    # Step 3: register
    description = ""
    readme_path = target / "README.md"
    if readme_path.exists():
        description = readme_path.read_text(encoding="utf-8", errors="ignore")[:200]

    _register_in_tools_registry(name, url, target, description)

    # Step 4: sync to Agora
    _sync_to_agora()

    return {
        "status": "installed",
        "name": name,
        "path": str(target),
        "issues": issues,
        "warnings": issues if issues else [],
    }


def list_installed() -> list[dict[str, Any]]:
    """List all installed market packages."""
    if not INSTALL_DIR.exists():
        return []

    packages = []
    for p in sorted(INSTALL_DIR.iterdir()):
        if not p.is_dir():
            continue
        # Check in tools-registry
        reg = _load_tools_registry()
        entry = next((t for t in reg.get("tools", []) if t.get("id") == p.name), None)

        git_dir = p / ".git"
        packages.append(
            {
                "name": p.name,
                "path": str(p),
                "registered": entry is not None,
                "status": entry.get("status", "unknown") if entry else "unknown",
                "has_git": git_dir.exists(),
                "description": (entry or {}).get("description", "")[:100],
            }
        )
    return packages


def remove(name: str) -> dict[str, Any]:
    """Remove an installed market package.

    Returns dict with status and details.
    """
    target = INSTALL_DIR / name

    # Unregister first
    found = _unregister_from_tools_registry(name)

    # Remove files
    if target.exists():
        try:
            shutil.rmtree(target)
            removed = True
        except OSError as e:
            return {"status": "error", "name": name, "error": str(e)}
    else:
        removed = False

    _sync_to_agora()

    return {
        "status": "removed" if removed else "not_found",
        "name": name,
        "unregistered": found,
        "files_removed": removed,
    }


# ── CLI 入口 (被 forge.py cmd_market 调用) ──


def cli(args: list[str]) -> int:
    """Market CLI handler. Called from forge.py cmd_market."""
    if not args:
        print("用法: forge market <install|list|remove> [args...]")
        print()
        print("命令:")
        print("  install <github-url>  [--name <alias>]  从 GitHub 安装工具")
        print("  list                                      列出已安装工具")
        print("  remove <name>                             卸载工具")
        return 1

    subcmd = args[0]
    rest = args[1:]

    if subcmd == "install":
        if not rest:
            print("❌ 请指定 GitHub URL")
            return 1
        url = rest[0]
        alias = None
        if "--name" in rest:
            idx = rest.index("--name")
            if idx + 1 < len(rest):
                alias = rest[idx + 1]
        result = install(url, alias)
        if result["status"] == "installed":
            print(f"✅ 已安装: {result['name']}")
            print(f"   路径: {result['path']}")
            if result.get("issues"):
                print(f"   ⚠️  {len(result['issues'])} 个问题:")
                for i in result["issues"]:
                    print(f"      - {i}")
            print("   运行 'forge market list' 查看已安装工具")
        elif result["status"] == "exists":
            print(f"   {result['name']} 已安装")
        else:
            print(f"❌ 安装失败: {result.get('error', '未知错误')}")
            return 1

    elif subcmd == "list":
        packages = list_installed()
        if not packages:
            print("📭 未安装任何市场工具")
            print("   运行 'forge market install <github-url>' 安装")
            return 0
        print(f"已安装 ({len(packages)}):")
        print(f"{'名称':25s} {'状态':12s} {'描述'}")
        print("-" * 70)
        for p in packages:
            print(f"{p['name']:25s} {p['status']:12s} {p['description'][:50]}")

    elif subcmd == "remove":
        if not rest:
            print("❌ 请指定要移除的工具名称")
            return 1
        result = remove(rest[0])
        if result["status"] == "removed":
            print(f"🗑️  已移除: {result['name']}")
        elif result["status"] == "not_found":
            print(f"⚠️  {result['name']} 未安装")
        else:
            print(f"❌ 移除失败: {result.get('error', '未知错误')}")
            return 1

    else:
        print(f"❌ 未知子命令: {subcmd}")
        print("可用: install, list, remove")
        return 1

    return 0


# ── Local tool management (CAPS_ROOT / market.json) ─────────────────
# These complement the git-based install() with a local-path install workflow.
# CAPS_ROOT and MARKET_REGISTRY are module-level and patchable by tests.


def _load_market() -> list[dict]:
    """Load market.json, returning list of tool entries."""
    if MARKET_REGISTRY.exists():
        try:
            return cast("list[dict]", json.loads(MARKET_REGISTRY.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_market(tools: list[dict]) -> None:
    """Save tool list to market.json."""
    MARKET_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    MARKET_REGISTRY.write_text(json.dumps(tools, indent=2, ensure_ascii=False), encoding="utf-8")


def install_local_tool(
    name: str,
    source_path: str,
    bos_uri: str = "",
    description: str = "",
) -> dict:
    """Install a tool from a local path into CAPS_ROOT/market.json.

    Returns:
        dict with 'installed'/'error' keys.
    """
    # Validate name
    valid, err = validate_tool_name(name)
    if not valid:
        return {"error": err}

    src = Path(source_path)
    if not src.exists():
        return {"error": "source_not_found", "path": source_path}

    # Install target
    target = CAPS_ROOT / name
    target.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        for item in src.iterdir():
            dest = target / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
    else:
        shutil.copy2(src, target / src.name)

    # Update market.json (upsert)
    tools = _load_market()
    existing = next((t for t in tools if t.get("name") == name), None)
    entry = {
        "name": name,
        "path": str(target),
        "bos_uri": bos_uri,
        "description": description,
        "installed_at": datetime.now().isoformat(),
    }
    if existing:
        tools = [entry if t.get("name") == name else t for t in tools]
    else:
        tools.append(entry)
    _save_market(tools)

    return {"installed": name, "path": str(target), "bos_uri": bos_uri}


def remove_tool(name: str) -> bool:
    """Remove a tool from CAPS_ROOT and market.json.

    Returns True if found and removed, False if not found.
    """
    tools = _load_market()
    before = len(tools)
    tools = [t for t in tools if t.get("name") != name]
    if len(tools) == before:
        return False
    _save_market(tools)

    target = CAPS_ROOT / name
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)

    return True


def list_tools() -> list[dict]:
    """List all tools in market.json."""
    return _load_market()


# ── Stub exports for backward-compat tests (P33-W5 migration) ──
# validate_bos_uri / validate_tool_name / MARKET_REGISTRY migrated to
# agora.ssrf_guard + agora.core.service_base + agora.mcp.bos_resolver.


def validate_bos_uri(uri: str) -> tuple[bool, str]:
    """Validate BOS URI format. Returns (valid, error_message)."""
    if not uri.startswith("bos://"):
        return False, "invalid_bos_uri: must start with bos://"
    parts = uri[6:].split("/")
    if len(parts) < 2 or not parts[0]:
        return False, "invalid_bos_uri: missing domain or path"
    allowed_domains = {"memory", "omo", "analysis", "persona", "forge"}
    domain = parts[0].lower()
    if domain not in allowed_domains:
        return False, f"invalid_bos_uri: unknown domain '{parts[0]}'"
    return True, ""


def validate_tool_name(name: str) -> tuple[bool, str]:
    """Validate tool name is kebab-case (lowercase alphanumeric with hyphens).
    Returns (valid, error_message).
    """
    import re

    if not name:
        return False, "invalid_tool_name: empty name"
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
        return False, f"invalid_tool_name: '{name}' must be kebab-case (lowercase, hyphens only, no underscores)"
    return True, ""
