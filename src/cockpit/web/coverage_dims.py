"""Cockpit coverage dimensions and project metadata constants.

Split from api_system_map_catalog.py (god-module SRP, T6-10).
Pure data, no logic dependencies.
"""

from __future__ import annotations

from typing import Any

PROJECT_DOC_FILES: tuple[str, ...] = (
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "ARCHITECTURE.md",
    "BOUNDARY.md",
    "CALLCHAIN.md",
)

PACKAGE_MANIFESTS: tuple[str, ...] = ("pyproject.toml", "package.json", "docker-compose.yml")
VITE_CONFIGS: tuple[str, ...] = ("vite.config.ts", "vite.config.js", "vite.config.mts", "vite.config.mjs")
NEXT_CONFIGS: tuple[str, ...] = ("next.config.ts", "next.config.js", "next.config.mjs")
STATIC_FRONTEND_MARKERS: tuple[str, ...] = ("index.html", "src/main.tsx", "src/main.jsx", "src/App.tsx")
CLI_ENTRYPOINTS: tuple[str, ...] = ("src/cli.py", "src/cli.ts", "cli.py", "cli.ts")
SERVICE_ENTRYPOINTS: tuple[str, ...] = (
    "dashboard_server.py",
    "src/server.py",
    "src/server.ts",
    "server.py",
    "server.ts",
    "api/server.ts",
    "api/app.py",
)

PROJECT_COVERAGE_DIMENSIONS: tuple[dict[str, str], ...] = (
    {
        "id": "cockpit_surface",
        "title": "Cockpit 入口",
        "description": "项目是否有站内原生入口，而不是只能在系统地图里定位。",
    },
    {
        "id": "registry_contract",
        "title": "注册合同",
        "description": "项目是否声明版本/生命周期、构建运行约束和可追踪实现落点。",
    },
    {
        "id": "security_contract",
        "title": "安全合同",
        "description": "项目是否提供可追踪的安全边界、风险说明或审计入口。",
    },
    {
        "id": "project_docs",
        "title": "项目文档",
        "description": "项目是否具备可读的 README/AGENTS/架构等操作说明。",
    },
    {
        "id": "commands",
        "title": "操作命令",
        "description": "项目是否登记可复制的验证、启动或维护命令。",
    },
    {
        "id": "manifest",
        "title": "构建清单",
        "description": "项目是否存在 pyproject、package 或 compose 等机器清单。",
    },
    {
        "id": "runtime_probe",
        "title": "运行探针",
        "description": "项目是否有可观测端口，且当前能判断运行状态。",
    },
    {
        "id": "verification",
        "title": "验证证据",
        "description": "项目是否有最近 agent-workflow 验证事件。",
    },
    {
        "id": "source_refs",
        "title": "来源定位",
        "description": "项目状态是否能回跳到注册表、端口表或项目指南。",
    },
    {
        "id": "operator_actions",
        "title": "受控动作",
        "description": "项目是否暴露站内导航、复制路径、复制验证等低风险动作。",
    },
)

PROJECT_PORT_ALIASES: dict[str, tuple[str, ...]] = {
    "agora": ("agora",),
    "kairon": ("kairon", "kos", "minerva", "ontoderive"),
    "gbrain": ("gbrain",),
    "omo": ("omo",),
    "metaos": ("metaos",),
    "runtime": ("runtime",),
    "ecos": ("ecos",),
    "cockpit": ("cockpit",),
    "cockpit-ui": ("cockpit-ui",),
    "l4-kernel": ("l4-kernel",),
    "model-driven": ("model-driven",),
    "aetherforge": ("aetherforge", "llm-gateway"),
    "c2g": ("c2g",),
    "bus-foundation": ("bus-foundation", "omni-bus"),
    "observability": ("observability", "langfuse"),
    "family-hub": ("family-hub",),
    "toolbox": ("toolbox", "wps", "bos-skill"),
    "mesh-router": ("mesh-router", "omlx-mesh-router"),
}
