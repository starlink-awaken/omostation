#!/usr/bin/env python3
# ruff: noqa
"""G3: MCP 外部工具市场发现 — 扫描本地 MCP 配置 + agora backends + 已知 registry.

场景覆盖审计 G3 缺口实现 (外部 LLM/工具市场深度集成).
forge 已有 discover_ecosystem (npm/brew/docker 包发现), 本模块补 MCP servers 发现
(本地 .claude/.cursor/.windsurf configs + agora 已注册 MCP backends + 已知 registry 目录).
"""

import json
from pathlib import Path
from typing import Any


def probe_local_mcp_configs() -> list[dict]:
    """扫描本地 MCP 客户端配置文件 (Claude Desktop / Cursor / Windsurf / VSCode)."""
    candidates = [
        Path.home() / ".claude" / "claude_desktop_config.json",
        Path.home() / ".claude.json",
        Path.home() / ".cursor" / "mcp.json",
        Path.home() / ".windsurf" / "mcp_config.json",
        Path.home() / ".vscode" / "settings.json",
        Path.home() / ".continue" / "config.json",
    ]
    found: list[dict] = []
    for cfg in candidates:
        if not cfg.exists():
            continue
        try:
            data = json.loads(cfg.read_text())
            # 不同客户端用不同 key: mcpServers / mcp.servers
            mcp_servers = {}
            if isinstance(data, dict):
                mcp_servers = (
                    data.get("mcpServers") or data.get("mcp", {}).get("servers", {})
                    if isinstance(data.get("mcp"), dict)
                    else data.get("mcpServers", {})
                )
            for name, conf in mcp_servers.items():
                if not isinstance(conf, dict):
                    continue
                found.append(
                    {
                        "name": name,
                        "source": str(cfg),
                        "command": conf.get("command", ""),
                        "args": conf.get("args", []),
                        "url": conf.get("url", ""),
                        "type": "local-config",
                    }
                )
        except Exception:
            continue
    return found


def probe_agora_backends() -> list[dict]:
    """扫描 agora 已注册的 MCP backends (runtime config + bos-services.yaml)."""
    candidates = [
        Path.home() / ".agora" / "agora-proxy-services.json",
        Path("/Users/xiamingxing/Workspace/projects/agora/etc/bos-services.yaml"),
    ]
    found: list[dict] = []
    for svc_path in candidates:
        if not svc_path.exists():
            continue
        try:
            if svc_path.suffix == ".json":
                data = json.loads(svc_path.read_text())
                services = data if isinstance(data, list) else data.get("services", [])
            else:
                import yaml

                data = yaml.safe_load(svc_path.read_text()) or {}
                services = data.get("services", []) if isinstance(data, dict) else []
            for s in services:
                if not isinstance(s, dict):
                    continue
                transport = s.get("transport", s.get("protocol", ""))
                if transport in ("mcp_stdio", "mcp", "mcp_proxy") or s.get("protocol") == "mcp":
                    found.append(
                        {
                            "name": s.get("name", ""),
                            "uri": s.get("uri", ""),
                            "transport": transport,
                            "package": s.get("package", ""),
                            "type": "agora-backend",
                        }
                    )
        except Exception:
            continue
    return found


# 已知 MCP servers registry 目录 (供人工浏览 + 后续自动化 fetch)
KNOWN_MCP_REGISTRIES = [
    {
        "name": "modelcontextprotocol/servers",
        "url": "https://github.com/modelcontextprotocol/servers",
        "type": "github-official",
        "note": "Anthropic 官方 MCP servers 参考实现集",
    },
    {
        "name": "punkpeye/awesome-mcp-servers",
        "url": "https://github.com/punkpeye/awesome-mcp-servers",
        "type": "community-awesome",
        "note": "社区策展 MCP servers 大全",
    },
    {
        "name": "glama/mcp-directory",
        "url": "https://glama.ai/mcp/servers",
        "type": "web-directory",
        "note": "MCP servers web 目录 (可搜索)",
    },
]


def list_known_registries() -> list[dict]:
    """列出已知 MCP servers registry 目录 (供发现 + 接入)."""
    return list(KNOWN_MCP_REGISTRIES)


def discover_all() -> dict[str, Any]:
    """汇总 MCP 外部工具市场发现 (本地 + agora + registry 目录)."""
    local = probe_local_mcp_configs()
    agora = probe_agora_backends()
    return {
        "local_configs": local,
        "local_count": len(local),
        "agora_backends": agora,
        "agora_count": len(agora),
        "known_registries": list_known_registries(),
        "total_discovered": len(local) + len(agora),
    }


def main() -> None:
    """CLI: forge discover-mcp — 打印 MCP 外部工具市场发现."""
    result = discover_all()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
