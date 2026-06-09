"""MCP Bootstrap — auto-discover and launch downstream MCP services.

Agora can automatically discover, launch, and aggregate downstream MCP
services, both within the kairon workspace and from external tools
(npm global, uv tools, etc.). This module provides:

- A KNOWN_SERVICES registry of all kairon MCP entry points
- External MCP tools (npm, uv, system-wide) registry
- Config file management (generate, read, write ~/.agora/agora-proxy-services.json)
- Workspace detection for kairon projects
- Orchestration: scan → generate config → launch via ProxyManager
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_DEFAULT_DATA_DIR = Path.home() / ".agora"
_DEFAULT_CONFIG_FILE = "agora-proxy-services.json"

# L0 Registry — dynamic override for KNOWN_SERVICES
_HAVE_L0_LOADER = False
try:
    from agora.l0_registry_loader import load_known_services as _l0_load_known

    _HAVE_L0_LOADER = True
except ImportError:
    pass


def get_data_dir() -> Path:
    """Return the Agora data directory.

    Respects the ``AGORA_DATA_DIR`` environment variable.
    Defaults to ``~/.agora/`` when unset.
    """
    data_dir = os.environ.get("AGORA_DATA_DIR", "")
    if data_dir:
        return Path(data_dir)
    return _DEFAULT_DATA_DIR


def migrate_legacy_data() -> None:
    """将旧路径（kairon 项目根目录）的数据迁移到 ~/.agora/（新路径）。

    AGORA_DATA_DIR 统一前，数据文件默认存储在项目根目录下。
    此函数在模块加载时自动执行，将旧文件复制到新位置。
    如果新位置已有同文件，则跳过（不覆盖）。
    """
    new_dir = get_data_dir()
    new_dir.mkdir(parents=True, exist_ok=True)

    # 旧路径：kairon 项目根目录
    # mcp_bootstrap.py 位于 packages/agora/src/agora/, 5 级 parent = project-root
    old_dir = Path(__file__).resolve().parent.parent.parent.parent.parent

    files_to_migrate = [
        "agora.db",
        "agora-tasks.json",
        "agora-proxy-services.json",
    ]

    for filename in files_to_migrate:
        old_path = old_dir / filename
        new_path = new_dir / filename
        if old_path.exists() and not new_path.exists():
            shutil.copy2(old_path, new_path)
            msg = f"[agora] Migrated {filename} to {new_path}\n"
            sys.stderr.write(msg)
            logger.info(
                "legacy_data_migrated",
                name=filename,
                from_path=str(old_path),
                to_path=str(new_path),
            )


# Auto-migrate legacy data on import
migrate_legacy_data()


# ── Known MCP service registry ──────────────────────────────────────
# Each entry defines how to launch the service via `uv run --package`.
# SSOT: l0_registry_overrides.yaml → L0 M1 nodes → KNOWN_SERVICES (fallback)
# Static dict retained as fallback; new services should register in L0.


def _get_known_services() -> dict[str, dict[str, Any]]:
    """Merge L0 registry entries with static KNOWN_SERVICES (L0 wins)."""
    if _HAVE_L0_LOADER:
        try:
            l0_known = _l0_load_known()
            if l0_known:
                merged = dict(_KNOWN_FALLBACK)
                merged.update(l0_known)
                return merged
        except Exception:
            pass
    return dict(_KNOWN_FALLBACK)


_KNOWN_FALLBACK: dict[str, dict[str, Any]] = {
    # ── Kairon 工作空间 MCP 服务 ──────────────────────────────
    # 通过 agora 代理由子进程加载的服务
    "agent-runtime": {
        "command": "uv",
        "args": [
            "run",
            "--package",
            "cockpit",
            "python",
            "-m",
            "cockpit.agent_runtime_mcp_server",
        ],
        "description": "Agent Runtime — 任务执行、对话、终端和文件工具运行时",
        "source": "kairon",
    },
    "codeanalyze": {
        "command": "uv",
        "args": ["run", "--package", "codeanalyze", "python", "-m", "codeanalyze.mcp"],
        "description": "代码与文档分析 — CRG 知识图谱、Tree-sitter、代码搜索",
        "source": "kairon",
    },
    "eidos": {
        "command": "uv",
        "args": ["run", "--package", "eidos", "python", "-m", "eidos.mcp_server"],
        "description": "知识建模与校验 — Schema、迁移、验证与导出",
        "source": "kairon",
    },
    "iris": {
        "command": "uv",
        "args": ["run", "--package", "iris", "python", "-m", "iris.mcp_server"],
        "description": "连接器中心 — 外部知识源拉取、搜索与同步",
        "source": "kairon",
    },
    "kos": {
        "command": "uv",
        "args": ["run", "--package", "kos", "python", "-m", "kos.mcp.server"],
        "description": "知识操作系统 — 跨域搜索、本体、协作、共识",
        "source": "kairon",
    },
    "kronos": {
        "command": "uv",
        "args": ["run", "--package", "kronos", "python", "-m", "kronos.cli"],
        "description": "知识摄取管线 — 抓取、转换、分块与入库",
        "source": "kairon",
    },
    "metaos": {
        "command": "uv",
        "args": ["run", "--package", "metaos", "python", "-m", "metaos.mcp_server"],
        "description": "MetaOS — 编排/治理层，决策门控与系统协同",
        "source": "metaos",  # independent project at projects/metaos/
    },
    "minerva": {
        "command": "uv",
        "args": [
            "run",
            "--package",
            "minerva",
            "python",
            "-m",
            "minerva.mcp_server.server",
        ],
        "description": "深度研究系统 — 检索、推理、报告与研究管线",
        "source": "kairon",
    },
    "sophia": {
        "command": "uv",
        "args": [
            "run",
            "--package",
            "sophia",
            "python",
            "-m",
            "sophia.server.mcp_server",
        ],
        "description": "符号化研究范式引擎 — 状态机驱动的研究方法运行时",
        "source": "kairon",
    },
    "cron-service": {
        "command": "uv",
        "args": ["run", "--package", "cron-service", "cron-service", "--mcp"],
        "description": "定时调度引擎 — 作业管理、脚本编排、定时触发",
        "source": "runtime",  # migrated to projects/runtime/
    },
    # ── npm 全局 MCP 工具 ────────────────────────────────────
    "mcp-server-sqlite": {
        "command": "mcp-server-sqlite",
        "args": [],
        "description": "SQLite 数据库操作 — 查询、建表、CRUD",
        "source": "npm",
    },
    "mcp-server-apple-events": {
        "command": "mcp-server-apple-events",
        "args": [],
        "description": "macOS 原生集成 — Apple 提醒事项和日历",
        "source": "npm",
    },
    # ── Docker MCP Gateway ──────────────────────────────────
    "docker-mcp-gateway": {
        "command": "docker",
        "args": ["mcp", "gateway", "run", "--profile", "default"],
        "description": "Docker MCP Gateway — 73 个工具（文件系统、搜索、维基百科、Markitdown、Memory等）",
        "source": "docker",
        "init_timeout": 30,
    },
    # ── GitNexus — 代码仓库知识图谱 MCP ─────────────────────
    "gitnexus": {
        "command": "gitnexus",
        "args": ["mcp"],
        "description": "代码仓库知识图谱 — 索引、搜索、分析代码仓库结构",
        "source": "homebrew",
    },
    # ── Z.AI MCP Server — UI/Artifact/图片/视频分析 ────────
    "zai-mcp-server": {
        "command": "npx",
        "args": ["-y", "@z_ai/mcp-server"],
        "description": "Z.AI MCP — 8个分析工具（UI转换、文字提取、错误诊断、图表分析、图片/视频分析）",
        "source": "npm",
    },
    # ── Agent CLI 跨编排 MCP 服务 ──────────────────────────
    "claude-mcp-serve": {
        "command": "claude",
        "args": ["mcp", "serve"],
        "description": "Claude Code (v2.1) — 跨 Agent 编排，委托代码编辑/分析任务",
        "source": "agent-cli",
        "init_timeout": 20,
    },
    "codex-mcp-server": {
        "command": "codex",
        "args": ["mcp-server"],
        "description": "Codex CLI (v0.135) — 跨 Agent 编排，委托编码/调试任务",
        "source": "agent-cli",
        "init_timeout": 20,
    },
    # ── Chrome DevTools MCP (通过 Gemini 发现) ──────────────
    "chrome-devtools-mcp": {
        "command": "npx",
        "args": ["-y", "chrome-devtools-mcp@latest"],
        "description": "Chrome DevTools MCP — 浏览器调试、DOM/CSS/Network 分析",
        "source": "npm",
    },
    # ── Serena — 开源 AI 助手 MCP (通过 Claude/VS Code 发现) ──
    "serena": {
        "command": "serena",
        "args": ["start-mcp-server"],
        "description": "Serena — 开源 AI 助手 MCP，多 LLM 支持、Shell/文件操作",
        "source": "npm",
        "init_timeout": 10,
    },
    # 注: Hermes 已双向连通 agora，跳过注册防止循环
    # 注: Gemini/Copilot 仅支持 ACP 协议（非标准 MCP），跳过
}
KNOWN_SERVICES = _get_known_services()

# ── Config path ──────────────────────────────────────────────────────
# Default: ~/.agora/agora-proxy-services.json
# Override via AGORA_DATA_DIR env var.

# Workspace root detection — traverse up from this file's location.
# File: packages/agora/src/agora/mcp_bootstrap.py
# parents[0] = src, parents[1] = agora, parents[2] = packages, parents[3] = kairon
_SCRIPT_DIR = Path(__file__).resolve().parent
_KAIRON_PACKAGES_DIR = _SCRIPT_DIR.parents[2]  # → packages/
_KAIRON_WORKSPACE_ROOT = _SCRIPT_DIR.parents[3]  # → kairon/


def _get_config_path() -> Path:
    return get_data_dir() / _DEFAULT_CONFIG_FILE


def _find_workspace_root() -> Path | None:
    """Detect the kairon workspace root.

    Detection order:
    1. ``KAIRON_WORKSPACE`` environment variable (explicit override).
    2. Current working directory — walk up to find ``packages/`` + ``kairon/``.
    3. File-relative detection (works when running via ``uv run`` from workspace).
    """
    # 1. Env var override
    env_ws = os.environ.get("KAIRON_WORKSPACE", "")
    if env_ws:
        candidate = Path(env_ws).resolve()
        packages_dir = candidate / "packages"
        if packages_dir.is_dir():
            return candidate

    # 2. Current working directory — walk up
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        if parent.name == "kairon":
            packages_dir = parent / "packages"
            if packages_dir.is_dir():
                return parent

    # 3. File-relative detection (for ``uv run`` from workspace)
    if (
        _KAIRON_PACKAGES_DIR.name == "packages"
        and _KAIRON_WORKSPACE_ROOT.name == "kairon"
    ):
        if _KAIRON_PACKAGES_DIR.is_dir():
            return _KAIRON_WORKSPACE_ROOT

    # 4. Saved config — read workspace path from existing config
    config_path = _get_config_path()
    if config_path.exists():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
            saved_ws = raw.get("_workspace", "") if isinstance(raw, dict) else ""
            if saved_ws and saved_ws != "auto-detect":
                candidate = Path(saved_ws).resolve()
                packages_dir = candidate / "packages"
                if packages_dir.is_dir():
                    return candidate
        except (json.JSONDecodeError, OSError):
            pass

    # 5. Try common known locations (for global tool install)
    for candidate_path in [
        Path.home() / "Workspace" / "projects" / "kairon",
        Path.home() / "kairon",
    ]:
        if candidate_path.is_dir() and (candidate_path / "packages").is_dir():
            return candidate_path.resolve()

    # Additional detection: a top-level directory containing both kairon and agora projects
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        projects_dir = parent / "projects"
        kairon_dir = projects_dir / "kairon"
        if kairon_dir.is_dir() and (projects_dir / "agora").is_dir():
            # Return the kairon workspace root (contains packages)
            return kairon_dir
    return None


def _check_service_exists(name: str, workspace: Path | None) -> bool:
    """Check if a kairon service's pyproject.toml exists in workspace."""
    if workspace is None:
        return False
    pkg_dir = workspace / "packages" / name
    return (pkg_dir / "pyproject.toml").exists() and (pkg_dir / "src").is_dir()


def _check_tool_available(name: str, info: dict[str, Any]) -> bool:
    """Check if a service/tool is available on this system.

    Dispatches based on the ``source`` field:
    - ``kairon``: checks workspace package exists
    - ``npm`` / other: checks if the command exists on PATH
    - ``docker``: checks if ``docker`` is available and ``docker mcp gateway`` subcommand works
    """
    source = info.get("source", "kairon")
    if source == "kairon":
        workspace = _find_workspace_root()
        return _check_service_exists(name, workspace)
    if source == "docker":
        if not shutil.which("docker"):
            return False
        try:
            result = subprocess.run(
                ["docker", "mcp", "gateway", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    # External tools: check if command exists on PATH
    command = info.get("command", "")
    optional = {
        "docker-mcp-gateway",
        "gitnexus",
        "zai-mcp-server",
        "claude-mcp-serve",
        "codex-mcp-server",
        "serena",
        "chrome-devtools-mcp",
    }
    if name in optional:
        logger.warning("Assuming optional service %s may be unavailable", name)
        # If command is npx, ensure npx exists
        if command == "npx":
            return bool(shutil.which("npx"))
        return bool(command)
    return bool(command and shutil.which(command))


def _check_uv_available() -> bool:
    """Check if ``uv`` is available on PATH."""
    return shutil.which("uv") is not None


def _check_package_installed(package_name: str, workspace: Path | None) -> bool:
    """Quick check if a package is installed in the uv environment."""
    if not _check_uv_available():
        return False
    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "--package",
                package_name,
                "--",
                sys.executable,
                "-c",
                "import sys; print('ok')",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(workspace) if workspace else None,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# ── Config management ────────────────────────────────────────────────


def _default_config(workspace: Path | None) -> dict[str, Any]:
    """Generate default proxy config enabling all known services.

    Only includes services that are available on this system:
    - Kairon packages are enabled if their package directory exists
    - External tools (npm, etc.) are enabled if their command is on PATH
    """
    services = []
    for name, info in _get_known_services().items():
        available = _check_tool_available(name, info)
        entry: dict[str, Any] = {
            "name": name,
            "enabled": available,
            "description": info["description"],
            "command": info["command"],
            "args": info["args"],
            "source": info.get("source", "kairon"),
        }
        if "init_timeout" in info:
            entry["init_timeout"] = info["init_timeout"]
        services.append(entry)

    return {
        "_generated_by": "agora.mcp_bootstrap",
        "_workspace": str(workspace) if workspace else "auto-detect",
        "services": services,
    }


def load_or_generate_config() -> tuple[list[dict[str, Any]], Path]:
    """Load existing config or generate a default one.

    If the config exists but ``_workspace`` is stale (``auto-detect``),
    and the workspace is now detected, the config is updated with the
    correct path.

    Returns:
        Tuple of (services_list, config_path).
    """
    config_path = _get_config_path()
    workspace = _find_workspace_root()

    if config_path.exists():
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        services = raw if isinstance(raw, list) else raw.get("services", [])

        if services:
            # Fix stale _workspace field if needed
            if (
                isinstance(raw, dict)
                and workspace
                and raw.get("_workspace") == "auto-detect"
            ):
                raw["_workspace"] = str(workspace)
                config_path.write_text(
                    json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
                )

            logger.info(
                "proxy_config_loaded", path=str(config_path), count=len(services)
            )
            return services, config_path

    # Generate default config
    logger.info("proxy_config_generating", path=str(config_path))
    config = _default_config(workspace)

    # Ensure config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(
        "proxy_config_generated", path=str(config_path), count=len(config["services"])
    )

    return config["services"], config_path


def reload_config() -> list[dict[str, Any]]:
    """Force reload config from disk, regenerating if needed."""
    config_path = _get_config_path()
    if config_path.exists():
        config_path.unlink()
    services, _ = load_or_generate_config()
    return services


def edit_config() -> None:
    """Open the config file in the default editor."""
    config_path = _get_config_path()
    if not config_path.exists():
        load_or_generate_config()

    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vim"))
    subprocess.run([editor, str(config_path)])
    reload_config()


# ── Service status ──────────────────────────────────────────────────


def get_config_status() -> dict[str, Any]:
    """Return current config status for CLI display.

    Returns dict with config path, workspace, and service statuses.
    """
    workspace = _find_workspace_root()
    config_path = _get_config_path()

    services = []
    for name, info in _get_known_services().items():
        available = _check_tool_available(name, info)
        source = info.get("source", "kairon")
        installed = (
            _check_package_installed(name, workspace)
            if source == "kairon" and available
            else available
        )
        services.append(
            {
                "name": name,
                "description": info["description"],
                "source": source,
                "available": available,
                "uv_available": _check_uv_available(),
                "installed": installed,
            }
        )

    return {
        "config_path": str(config_path),
        "config_exists": config_path.exists(),
        "workspace": str(workspace) if workspace else None,
        "uv_available": _check_uv_available(),
        "services": services,
    }


# ── Bootstrap orchestration ─────────────────────────────────────────


def _build_enabled_services(
    config_services: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build ProxyManager-compatible service configs for enabled services.

    Filters config list to enabled=true services and enriches with
    workspace cwd for stdio launching.
    """
    workspace = _find_workspace_root()
    result: list[dict[str, Any]] = []

    for svc in config_services:
        if not svc.get("enabled", False):
            continue

        name = svc.get("name", "")
        command = svc.get("command", "")
        args = svc.get("args", [])

        if not name or not command:
            continue

        entry: dict[str, Any] = {
            "name": name,
            "mcp_endpoint": "stdio",
            "command": command,
            "args": args,
        }

        # Pass through init_timeout (e.g. docker-mcp-gateway needs 30s, agent CLI servers need 15s)
        init_timeout = svc.get("init_timeout")
        if init_timeout is not None:
            entry["init_timeout"] = init_timeout

        if workspace and _check_service_exists(name, workspace):
            entry["cwd"] = str(workspace)

        result.append(entry)

    return result


async def scan_and_launch(proxy_manager: Any) -> dict[str, str]:
    """Scan workspace, load config, launch all enabled downstream MCP services.

    This is the main entry point for auto-bootstrap. It:

    1. Loads or generates the proxy config file
    2. Builds ProxyManager-compatible service configs
    3. Launches all enabled services via proxy_manager.start()

    Args:
        proxy_manager: Instance of ProxyManager to use for launching.

    Returns:
        Dict mapping service_name → result string (same as ProxyManager.start()).
    """
    config_services, config_path = load_or_generate_config()
    enabled_services = _build_enabled_services(config_services)

    if not enabled_services:
        logger.info("proxy_bootstrap_no_services", config_path=str(config_path))
        return {}

    logger.info(
        "proxy_bootstrap_launching",
        config_path=str(config_path),
        count=len(enabled_services),
        services=[s["name"] for s in enabled_services],
    )

    results = await proxy_manager.start(enabled_services)
    return results
