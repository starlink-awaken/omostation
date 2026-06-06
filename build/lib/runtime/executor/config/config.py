"""Agent Runtime 配置模块。"""

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("runtime.executor")

# ── 固定模型 ──────────────────────────────────────────────────────────────────
DEFAULT_MODEL = "deepseek-v4-flash"

# ── 端口 ──────────────────────────────────────────────────────────────────────
AGENT_RUNTIME_PORT = int(os.environ.get("AGENT_RUNTIME_PORT", "9876"))

# ── HTTP 认证 ─────────────────────────────────────────────────────────────────
AUTH_TOKEN = os.environ.get("AGENT_RUNTIME_AUTH_TOKEN") or ""

# ── 路径 ──────────────────────────────────────────────────────────────────────
WORKSPACE = Path(os.environ.get("WORKSPACE", str(Path.home() / "Workspace")))
ECOS_DIR = WORKSPACE / "eCOS"
AGORA_DIR = WORKSPACE / "agora"
KOS_DIR = Path(os.environ.get("KOS_HOME", str(Path.home() / ".kos")))
AGENT_RUNTIME_DIR = Path(__file__).parent

# 路径沙箱：允许文件读写的白名单目录
ALLOWED_PATHS = [
    WORKSPACE,
    Path.home() / ".hermes",
    Path.home() / ".workspace",
    Path.home() / ".kos",
    Path.home() / ".omo",
]

# ── 执行日志 ──────────────────────────────────────────────────────────────────
EXEC_LOG_FILE = AGENT_RUNTIME_DIR / "execution_log.jsonl"

# ── Forge registry 查询 ─────────────────────────────────────────────────────
REGISTRY_PATH = WORKSPACE / "Forge" / "assets" / "registry.json"


def _load_registry() -> dict:
    """加载 Forge 资产注册表，按 name -> entity 索引。"""
    try:
        data = json.loads(REGISTRY_PATH.read_text())
        indexed: dict[str, dict] = {}
        for group in data.get("entities", {}).values():
            # v4 format: {"$schema": "...", "items": [...]}
            # v3 format: [{...}, {...}]
            items = group.get("items", group) if isinstance(group, dict) else group
            if not isinstance(items, list):
                continue
            for entity in items:
                name = entity.get("name", "")
                if name:
                    indexed[name] = entity
                eid = entity.get("id", "")
                if eid and eid != name:
                    indexed[eid] = entity
        return indexed
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {}


def _query_registry_port(known_names: list[str]) -> int | None:
    """按名称优先级列表查询 registry 端口。"""
    reg = _load_registry()
    for name in known_names:
        entry = reg.get(name)
        if entry:
            port = entry.get("port")
            if port and isinstance(port, int) and port > 0:
                return port
    return None


def _query_registry_field(known_names: list[str], field: str) -> str | None:
    """按名称优先级列表查询 registry 字段值。"""
    reg = _load_registry()
    for name in known_names:
        entry = reg.get(name)
        if entry:
            val = entry.get(field)
            if val:
                return str(val)
    return None


# ── MCP 端点（优先级：Forge registry > env var > 硬编码默认值）────────────
_MCP_SERVICE_NAMES = {
    "agora": ["agora-mcp", "agora-dashboard", "agora"],
    "kos": ["bos-daemon", "kos-mcp", "kos", "sharedbrain-bos"],
    "minerva": ["minerva"],
}

_MCP_PORT_DEFAULTS = {
    "agora": os.environ.get("AGORA_MCP_PORT", "7430"),
    "kos": os.environ.get("KOS_MCP_PORT", "7420"),
    "minerva": os.environ.get("MINERVA_MCP_PORT", "8765"),
}


def _build_mcp_endpoints() -> dict[str, str]:
    """构建 MCP 端点映射，优先 registry，其次 env var，最后默认值。"""
    endpoints = {}
    for name in ("agora", "kos", "minerva"):
        # 1. 直接的环境变量覆盖（最高优先级）
        url = os.environ.get(f"{name.upper()}_MCP_URL")
        if url:
            endpoints[name] = url
            continue

        # 2. Forge registry 查询
        known_names = _MCP_SERVICE_NAMES[name]
        port = _query_registry_port(known_names)
        if port is not None:
            endpoints[name] = f"http://localhost:{port}/mcp"
            continue

        # 3. 环境变量中单独的 port 配置
        env_port = os.environ.get(f"{name.upper()}_MCP_PORT")
        if env_port:
            endpoints[name] = f"http://localhost:{env_port}/mcp"
            continue

        # 4. 硬编码默认值（带 warning）
        default_port = _MCP_PORT_DEFAULTS[name]
        log.warning(
            "MCP %s: 未在 Forge registry/env 中找到端口，使用硬编码默认值 %s",
            name,
            default_port,
        )
        endpoints[name] = f"http://localhost:{default_port}/mcp"

    return endpoints


MCP_ENDPOINTS = _build_mcp_endpoints()


# ── iLink 推送（优先级：Forge registry > env var）────────────────────────
def _build_ilink_url() -> str:
    """从 registry 或 env 获取 iLink 推送 URL。"""
    url = os.environ.get("ILINK_SEND_URL") or os.environ.get("ILINK_SEND_URL_LEGACY")
    if url:
        return url

    # Try registry — ilink entry may store URL in health_endpoint or port_env
    reg_url = _query_registry_field(["ilink"], "health_endpoint")
    if reg_url:
        return reg_url

    return ""


ILINK_SEND_URL = _build_ilink_url()

# ── 日志 ──────────────────────────────────────────────────────────────────────


def setup_logging(level=logging.INFO):
    """初始化日志配置。"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )


def sanitize_for_log(text: str, max_len: int = 200) -> str:
    """脱敏敏感信息（API key、token 等）后返回日志安全文本。"""
    import re

    # 替换常见的 API key 模式
    sanitized = re.sub(r'(sk-|api_key["\']?\s*[:=]\s*["\']?)[a-zA-Z0-9_-]{20,}', r"\1***SANITIZED***", text)
    # 替换 Authorization header
    sanitized = re.sub(r"Authorization:\s*Bearer\s+\S+", "Authorization: Bearer ***SANITIZED***", sanitized)
    return sanitized[:max_len]
