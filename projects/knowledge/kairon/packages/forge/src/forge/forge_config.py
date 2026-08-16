"""
forge_config — Forge 统一配置

所有路径常量、环境变量的单一入口。消除各模块重复定义。

用法:
    from forge_config import FORGE_ROOT, REGISTRY, GRAPH, ...
"""

from __future__ import annotations

import os
from pathlib import Path

# ── 项目根 ──

FORGE_ROOT = Path(__file__).resolve().parent.parent.parent

# ── 工具注册表 ──

REGISTRY = FORGE_ROOT / "tools-registry.json"

# ── 资产注册表 ──

ASSETS_DIR = FORGE_ROOT / "assets"
ASSET_REGISTRY = ASSETS_DIR / "registry.json"

# ── 图谱 ──

GRAPH_DIR = FORGE_ROOT / "graph"
GRAPH = GRAPH_DIR / "graph.json"

# ── 源码目录 ──

SRC = FORGE_ROOT / "src"
SCRIPTS_DIR = FORGE_ROOT / "scripts"
ADAPTERS_DIR = FORGE_ROOT / "adapters"

# ── launchd ──

LAUNCH_AGENTS = Path.home() / "Library/LaunchAgents"
DISABLED_DIR = LAUNCH_AGENTS / "disabled"
LOG_DIR = Path.home() / "Library/Logs"

# ── HTTP API ──

HTTP_PORT = 8766
API_TOKEN = os.environ.get("FORGE_API_TOKEN", "")
MAX_BODY = 10 * 1024 * 1024

# ── CORS ──

# 允许的跨域来源列表，逗号分隔。默认仅允许本地回环地址。
# 示例: FORGE_ALLOWED_ORIGINS="http://example.com,https://app.example.com"
ALLOWED_CORS_ORIGINS_STR = os.environ.get("FORGE_ALLOWED_ORIGINS", "http://127.0.0.1:8766,http://localhost:8766")
ALLOWED_CORS_ORIGINS = {o.strip() for o in ALLOWED_CORS_ORIGINS_STR.split(",") if o.strip()}

# ── 反熵阈值（可由环境变量覆盖）──

STALE_DAYS = int(os.environ.get("FORGE_ENTROPY_STALE_DAYS", "90"))
CANDIDATE_DAYS = int(os.environ.get("FORGE_ENTROPY_CANDIDATE_DAYS", "30"))
