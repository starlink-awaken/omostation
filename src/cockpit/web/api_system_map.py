"""Cockpit system map API.

This endpoint turns workspace SSOT pointers into an operator-facing map. It is
intentionally read-only: Cockpit explains and routes across the system, while
the underlying registries keep owning the facts.
"""

from __future__ import annotations

import json
import os
import re
import socket
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


def _find_workspace_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "project-registry.yaml").is_file():
            return parent
    return Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))).expanduser()


WORKSPACE_ROOT = _find_workspace_root()
SYSTEM_MAP_SOURCE = Path(__file__).resolve()
MAX_SOURCE_PREVIEW_BYTES = 1_000_000


COCKPIT_PAGES: tuple[dict[str, Any], ...] = (
    {
        "id": "Home",
        "title": "首页",
        "group": "入口",
        "purpose": "健康、告警、任务、指标趋势的日常总览。",
        "dimensions": ("entry", "governance", "runtime"),
    },
    {
        "id": "SystemMap",
        "title": "系统地图",
        "group": "入口",
        "purpose": "按层级、项目、能力域和使用路径解释整个 Cockpit。",
        "dimensions": ("entry", "architecture", "coverage"),
    },
    {
        "id": "DomainApps",
        "title": "应用中心",
        "group": "领域应用",
        "purpose": "挂载家庭驾驶舱、OPC 作战台和领域服务。",
        "dimensions": ("domain", "l4", "entry"),
    },
    {
        "id": "Overview",
        "title": "概览中心",
        "group": "运行大盘",
        "purpose": "查看服务节点、运行状态和集群概貌。",
        "dimensions": ("runtime", "service", "health"),
    },
    {
        "id": "McpMesh",
        "title": "网格与 MCP",
        "group": "运行大盘",
        "purpose": "调试 MCP 实例、BOS URI 和路由解析。",
        "dimensions": ("routing", "mcp", "bos"),
    },
    {
        "id": "Topology",
        "title": "全局拓扑",
        "group": "运行大盘",
        "purpose": "观察服务关系、调用流和拓扑健康。",
        "dimensions": ("routing", "runtime", "service"),
    },
    {
        "id": "Compute",
        "title": "算力调配",
        "group": "运行大盘",
        "purpose": "查看模型网关、节点、成本和算力路由。",
        "dimensions": ("compute", "runtime", "cost"),
    },
    {
        "id": "Research",
        "title": "研究中枢",
        "group": "智能与知识",
        "purpose": "管理研究对象、来源、追问、时间线和发布承接。",
        "dimensions": ("research", "knowledge", "publishing"),
    },
    {
        "id": "Protocol",
        "title": "协议工作台",
        "group": "智能与知识",
        "purpose": "巡检工作流定义、动作、后端和协议层运行证据。",
        "dimensions": ("protocol", "workflow", "lifecycle"),
    },
    {
        "id": "Knowledge",
        "title": "知识中枢",
        "group": "智能与知识",
        "purpose": "进入 GBrain/KOS 类知识检索与记忆面。",
        "dimensions": ("knowledge", "memory", "reasoning"),
    },
    {
        "id": "Engines",
        "title": "引擎调度",
        "group": "智能与知识",
        "purpose": "管理 Kairon、GBrain 等引擎状态。",
        "dimensions": ("engine", "knowledge", "runtime"),
    },
    {
        "id": "Assets",
        "title": "技术资产库",
        "group": "智能与知识",
        "purpose": "索引技能、工具管线和自动化工作流。",
        "dimensions": ("capability", "workflow", "tooling"),
    },
    {
        "id": "Workflows",
        "title": "MetaOS 工作流",
        "group": "智能与知识",
        "purpose": "跟踪和测试 Agent 工作流编排。",
        "dimensions": ("orchestration", "workflow", "agent"),
    },
    {
        "id": "C2G",
        "title": "C2G 战略中心",
        "group": "系统治理",
        "purpose": "把战略意图、任务和治理卡片串起来。",
        "dimensions": ("strategy", "governance", "task"),
    },
    {
        "id": "AlertCenter",
        "title": "告警中心",
        "group": "系统治理",
        "purpose": "统一查看告警、规则和处置状态。",
        "dimensions": ("governance", "alert", "health"),
    },
    {
        "id": "L4Health",
        "title": "L4 域健康",
        "group": "系统治理",
        "purpose": "观察自我层域健康、趋势和风险。",
        "dimensions": ("l4", "domain", "health"),
    },
    {
        "id": "Debt",
        "title": "技术债务",
        "group": "系统治理",
        "purpose": "查看技术债、评分和风险闭环。",
        "dimensions": ("governance", "debt", "quality"),
    },
    {
        "id": "Observability",
        "title": "运行可观测",
        "group": "系统治理",
        "purpose": "聚合日志、指标和链路观测入口。",
        "dimensions": ("observability", "runtime", "health"),
    },
    {
        "id": "LogViewer",
        "title": "日志查看器",
        "group": "开发工具",
        "purpose": "检索运行日志和问题现场。",
        "dimensions": ("debug", "runtime", "logs"),
    },
    {
        "id": "TaskCenter",
        "title": "任务中心",
        "group": "开发工具",
        "purpose": "统一查看任务状态、进度和操作控制。",
        "dimensions": ("task", "governance", "workflow"),
    },
    {
        "id": "Performance",
        "title": "性能监控",
        "group": "开发工具",
        "purpose": "查看 CPU、内存、磁盘、网络指标。",
        "dimensions": ("performance", "runtime", "health"),
    },
    {
        "id": "Sandbox",
        "title": "隔离沙箱",
        "group": "开发工具",
        "purpose": "在隔离环境中执行测试或未校验命令。",
        "dimensions": ("runtime", "sandbox", "execution"),
    },
    {
        "id": "QuestBoard",
        "title": "积分冒险",
        "group": "领域应用",
        "purpose": "承接家庭任务、奖励和游戏化体验。",
        "dimensions": ("family", "domain", "motivation"),
    },
    {
        "id": "Settings",
        "title": "底层设置",
        "group": "系统配置",
        "purpose": "配置路由、令牌和治理阈值。",
        "dimensions": ("config", "governance", "runtime"),
    },
)

# 页面自身的低风险操作。项目动作另由项目矩阵提供，成熟度计算需要把两类证据合并。
PAGE_OPERATOR_ACTIONS: dict[str, tuple[str, ...]] = {
    "Home": ("refresh-home", "open-system-map", "open-task-center"),
    "DomainApps": ("open-app", "open-api", "copy-start", "copy-verify"),
    "Overview": ("refresh-runtime", "open-system-map"),
    "McpMesh": ("refresh-mesh", "copy-bos-uri", "open-service"),
    "Topology": ("refresh-topology", "inspect-node"),
    "Compute": ("refresh-compute", "copy-route", "open-cost-board"),
    "Research": ("copy-research-command", "open-research-detail", "open-task-center"),
    "Knowledge": ("search-knowledge", "write-knowledge", "open-source"),
    "Engines": ("refresh-engines", "open-engine"),
    "Assets": ("search-assets", "open-asset", "copy-command"),
    "Protocol": ("refresh-protocol", "open-workflow", "copy-validation"),
    "Workflows": ("refresh-workflows", "approve-workflow", "open-run"),
    "C2G": ("approve-proposal", "reject-proposal", "fix-drift"),
    "AlertCenter": ("acknowledge-alert", "silence-alert", "resolve-alert", "manage-rules"),
    "L4Health": ("refresh-l4-health", "open-domain"),
    "Debt": ("refresh-debt", "open-debt-source"),
    "Observability": ("refresh-observability", "open-log-context"),
    "LogViewer": ("refresh-logs", "filter-logs", "open-log-source"),
    "TaskCenter": ("pause-task", "resume-task", "cancel-task", "open-task-source"),
    "Performance": ("refresh-performance", "select-time-range"),
    "Sandbox": ("execute-sandbox", "copy-sandbox-code", "open-execution-log"),
    "QuestBoard": ("create-quest", "complete-quest", "refresh-quests"),
    "Settings": ("register-instance", "copy-endpoint", "open-mesh"),
}


CAPABILITY_TO_PAGE = {
    "深度研究": "Research",
    "研究管线": "Research",
    "知识摄取与持久化": "Knowledge",
    "知识检索与推理": "Knowledge",
    "治理与合规": "C2G",
    "编排与执行": "Workflows",
    "算力与基础设施": "Compute",
    "通信与路由": "McpMesh",
    "协议与元模型": "Protocol",
    "自我与入口": "SystemMap",
}


PROJECT_TO_PAGE = {
    "agora": "McpMesh",
    "kairon": "Engines",
    "gbrain": "Knowledge",
    "omo": "C2G",
    "metaos": "Workflows",
    "runtime": "Overview",
    "ecos": "Assets",
    "cockpit": "SystemMap",
    "cockpit-ui": "SystemMap",
    "l4-kernel": "L4Health",
    "model-driven": "Assets",
    "aetherforge": "Compute",
    "c2g": "C2G",
    "bus-foundation": "McpMesh",
    "omo-debt": "Debt",
    "observability": "Observability",
    "family-hub": "DomainApps",
    "toolbox": "Assets",
    "mesh-router": "Compute",
}


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


USAGE_PATHS: tuple[dict[str, Any], ...] = (
    {
        "id": "daily-ops",
        "title": "日常体检",
        "intent": "先看系统是否能用，再处理最紧急的问题。",
        "steps": ("Home", "AlertCenter", "TaskCenter", "LogViewer"),
    },
    {
        "id": "architecture-orientation",
        "title": "架构定位",
        "intent": "不知道某个项目归哪一层、该从哪进时使用。",
        "steps": ("SystemMap", "McpMesh", "Assets", "Settings"),
    },
    {
        "id": "governance-loop",
        "title": "治理闭环",
        "intent": "把战略、任务、债务、证据和告警串成一条线。",
        "steps": ("C2G", "Workflows", "Debt", "Observability"),
    },
    {
        "id": "knowledge-work",
        "title": "知识工作",
        "intent": "从知识检索、引擎状态到技能资产逐步定位。",
        "steps": ("Knowledge", "Engines", "Assets", "McpMesh"),
    },
    {
        "id": "research-publication",
        "title": "研究到发布",
        "intent": "从研究对象、知识上下文到发布和任务承接。",
        "steps": ("Research", "Knowledge", "TaskCenter", "C2G"),
    },
    {
        "id": "protocol-integrity",
        "title": "协议完整性",
        "intent": "确认协议定义、动作、后端和治理承接都具备证据。",
        "steps": ("Protocol", "Workflows", "Assets", "C2G"),
    },
    {
        "id": "domain-ops",
        "title": "领域作战",
        "intent": "进入家庭、OPC 等 L4 领域应用，同时守住 SSOT 边界。",
        "steps": ("DomainApps", "L4Health", "QuestBoard", "C2G"),
    },
    {
        "id": "runtime-diagnostics",
        "title": "运行诊断",
        "intent": "从服务状态、资源采样和拓扑证据定位运行问题。",
        "steps": ("Home", "Overview", "Performance", "Topology", "LogViewer"),
    },
    {
        "id": "safe-execution",
        "title": "安全执行",
        "intent": "先在隔离沙箱验证，再把结果带回任务或工作流。",
        "steps": ("Sandbox", "TaskCenter", "Workflows", "LogViewer"),
    },
    {
        "id": "control-plane-onboarding",
        "title": "控制面接入",
        "intent": "注册实例、确认路由和安全门，再挂载领域应用。",
        "steps": ("Settings", "McpMesh", "DomainApps", "Overview"),
    },
)


OPERATING_PLAYBOOKS: tuple[dict[str, Any], ...] = (
    {
        "id": "daily-health-check",
        "title": "每日 5 分钟体检",
        "goal": "先确认入口、告警、任务和日志是否正常，把当天最该处理的风险挑出来。",
        "frequency": "daily",
        "owner": "operator",
        "risk": "low",
        "steps": (
            {
                "id": "daily-home-scan",
                "page_id": "Home",
                "action": "查看健康摘要、趋势和首页快捷入口是否有异常。",
                "evidence": "首页健康卡片、运行项目数、待补能力数。",
                "done_when": "能说出当前最重要的一个系统状态变化。",
            },
            {
                "id": "daily-alert-triage",
                "page_id": "AlertCenter",
                "action": "按严重度扫一遍告警，确认是否有需要当天处理的 P0/P1。",
                "evidence": "告警中心的活动告警、规则状态和处置状态。",
                "done_when": "高风险告警已被确认、转任务或标记为无需动作。",
            },
            {
                "id": "daily-task-followup",
                "page_id": "TaskCenter",
                "action": "查看正在执行和阻塞的任务，决定今天推进哪三件事。",
                "evidence": "任务中心的进行中任务、阻塞任务和最近操作。",
                "done_when": "当天三件事有明确入口和下一步。",
            },
            {
                "id": "daily-log-check",
                "page_id": "LogViewer",
                "action": "只针对异常页面或服务看日志现场，避免无目标翻日志。",
                "evidence": "日志查看器里的错误片段、时间窗口和相关服务。",
                "done_when": "异常有证据位置；没有异常则结束巡检。",
            },
        ),
    },
    {
        "id": "weekly-governance-loop",
        "title": "每周治理闭环",
        "goal": "把战略、工作流、技术债和可观测证据串起来，避免治理停留在文档层。",
        "frequency": "weekly",
        "owner": "governance",
        "risk": "medium",
        "steps": (
            {
                "id": "weekly-strategy-review",
                "page_id": "C2G",
                "action": "检查战略意图、任务卡片和当前治理阶段是否一致。",
                "evidence": "C2G 战略中心的任务、决策和治理卡片。",
                "done_when": "本周目标能映射到具体任务或债务条目。",
            },
            {
                "id": "weekly-workflow-evidence",
                "page_id": "Workflows",
                "action": "查看 agent workflow 的最近执行、验证和 closeout 是否有断点。",
                "evidence": "工作流运行记录、verify 事件和 closeout 状态。",
                "done_when": "关键改动都有验证证据或明确补证计划。",
            },
            {
                "id": "weekly-debt-priority",
                "page_id": "Debt",
                "action": "按影响面和阻塞程度重排技术债优先级。",
                "evidence": "技术债务列表、评分和风险来源。",
                "done_when": "至少一个技术债进入本周可执行任务。",
            },
            {
                "id": "weekly-observability-check",
                "page_id": "Observability",
                "action": "核对关键服务是否有日志、指标和链路证据。",
                "evidence": "运行可观测页面的指标、日志和探针状态。",
                "done_when": "治理结论有运行证据支撑，而不是只靠口头判断。",
            },
        ),
    },
    {
        "id": "project-runtime-review",
        "title": "项目运行巡检",
        "goal": "从项目矩阵进入每个关键项目，确认目录、文档、命令、端口和验证是否闭环。",
        "frequency": "on-demand",
        "owner": "engineering",
        "risk": "medium",
        "steps": (
            {
                "id": "project-map-filter",
                "page_id": "SystemMap",
                "action": "在项目矩阵里定位目标项目，看状态、运行、文档和命令列。",
                "evidence": "项目矩阵中的 operational、runtime、docs、commands。",
                "done_when": "目标项目的缺口和下一步清楚可见。",
            },
            {
                "id": "project-runtime-probe",
                "page_id": "Overview",
                "action": "对照运行大盘确认端口监听和服务状态是否一致。",
                "evidence": "端口注册表探针、运行项目数和服务节点状态。",
                "done_when": "能区分目录就绪、服务运行和验证通过三类状态。",
            },
            {
                "id": "project-workflow-proof",
                "page_id": "Workflows",
                "action": "查最近一次验证事件，确认它覆盖了目标项目改动面。",
                "evidence": "agent-workflow verify 事件和 claimed surfaces。",
                "done_when": "项目状态有最近验证证据，或明确标记为 unknown。",
            },
        ),
    },
    {
        "id": "domain-app-ops",
        "title": "领域应用作战",
        "goal": "把家庭、OPC、family-hub 等 L4 能力挂入 Cockpit，同时守住 SSOT 和安全边界。",
        "frequency": "weekly",
        "owner": "domain",
        "risk": "high",
        "steps": (
            {
                "id": "domain-contract-check",
                "page_id": "DomainApps",
                "action": "检查领域 app contract、SSOT 根、URL、验证命令和风险等级。",
                "evidence": "应用中心的 domain app contract 和能力边界。",
                "done_when": "知道每个领域应用是外部挂载、内置模块还是服务能力。",
            },
            {
                "id": "domain-health-check",
                "page_id": "L4Health",
                "action": "查看 L4 域健康，确认家庭、OPC 等领域是否有明显风险。",
                "evidence": "L4 健康趋势、风险提示和领域状态。",
                "done_when": "领域风险已转成任务、告警或本周行动。",
            },
            {
                "id": "domain-family-tasks",
                "page_id": "QuestBoard",
                "action": "把家庭任务、奖励或游戏化需求放在 family-hub 服务边界内处理。",
                "evidence": "积分冒险页、family-hub contract 和家庭任务入口。",
                "done_when": "家庭体验需求不和 Cockpit 平台职责混栈。",
            },
            {
                "id": "domain-governance-sync",
                "page_id": "C2G",
                "action": "把领域行动同步回治理任务，避免 app 成为新的信息孤岛。",
                "evidence": "C2G 任务、周回顾和治理卡片。",
                "done_when": "领域动作有治理归档位置和复盘入口。",
            },
        ),
    },
    {
        "id": "knowledge-work-session",
        "title": "知识工作会话",
        "goal": "从知识检索进入引擎、资产和 MCP 路由，找到资料并确认能力链路可用。",
        "frequency": "on-demand",
        "owner": "knowledge",
        "risk": "low",
        "steps": (
            {
                "id": "knowledge-query",
                "page_id": "Knowledge",
                "action": "先用知识中枢找资料、记忆或项目背景。",
                "evidence": "知识检索结果、记忆索引和相关来源。",
                "done_when": "目标问题有可引用的知识来源。",
            },
            {
                "id": "knowledge-engine-check",
                "page_id": "Engines",
                "action": "确认相关引擎是否可用，避免把检索失败误判成资料不存在。",
                "evidence": "引擎调度页的 Kairon/GBrain/KOS 状态。",
                "done_when": "检索链路的引擎状态已确认。",
            },
            {
                "id": "knowledge-asset-route",
                "page_id": "Assets",
                "action": "查看是否已有技能、工具或自动化能直接处理该问题。",
                "evidence": "技术资产库中的技能、工具管线和 workflow。",
                "done_when": "找到可复用能力，或明确需要补新能力。",
            },
            {
                "id": "knowledge-route-debug",
                "page_id": "McpMesh",
                "action": "如果能力不可达，回到 MCP 网格检查路由和 BOS URI。",
                "evidence": "MCP 实例、BOS URI 和路由解析状态。",
                "done_when": "能力不可达有路由层证据，能进入修复流程。",
            },
        ),
    },
    {
        "id": "research-publication-loop",
        "title": "研究到发布闭环",
        "goal": "把研究对象从问题、证据和追问推进到发布与任务承接。",
        "frequency": "weekly",
        "owner": "knowledge",
        "risk": "medium",
        "steps": (
            {
                "id": "research-object-review",
                "page_id": "Research",
                "action": "确认研究对象、来源、追问和最近事件。",
                "evidence": "研究对象详情、时间线和 dossier。",
                "done_when": "研究结论和下一步问题清楚。",
            },
            {
                "id": "research-knowledge-context",
                "page_id": "Knowledge",
                "action": "补充知识来源和长期上下文。",
                "evidence": "检索结果、来源定位和记忆记录。",
                "done_when": "发布内容有可引用上下文。",
            },
            {
                "id": "research-task-handoff",
                "page_id": "TaskCenter",
                "action": "把研究后的动作沉到任务或草稿。",
                "evidence": "任务来源、负责人和状态。",
                "done_when": "发布后的动作有追踪入口。",
            },
            {
                "id": "research-governance-sync",
                "page_id": "C2G",
                "action": "将高影响研究结论带回战略和治理语境。",
                "evidence": "C2G 卡片、决策或周回顾记录。",
                "done_when": "研究影响进入治理闭环。",
            },
        ),
    },
    {
        "id": "protocol-integrity-loop",
        "title": "协议层完整性检查",
        "goal": "巡检工作流定义、动作、后端、运行证据和治理承接。",
        "frequency": "weekly",
        "owner": "protocol",
        "risk": "medium",
        "steps": (
            {
                "id": "protocol-registry-review",
                "page_id": "Protocol",
                "action": "查看协议工作台中的工作流、动作和后端注册数量。",
                "evidence": "协议层汇总和最近运行记录。",
                "done_when": "定义层、动作层和后端层的状态可解释。",
            },
            {
                "id": "protocol-workflow-proof",
                "page_id": "Workflows",
                "action": "确认工作流运行、审批和失败记录。",
                "evidence": "MetaOS 工作流运行证据。",
                "done_when": "关键协议动作有最近运行或验证证据。",
            },
            {
                "id": "protocol-asset-link",
                "page_id": "Assets",
                "action": "回到技术资产确认定义和实现来源。",
                "evidence": "技能、管线和工作流资产。",
                "done_when": "协议问题能回跳到具体资产。",
            },
            {
                "id": "protocol-governance-handoff",
                "page_id": "C2G",
                "action": "把协议缺口沉到治理任务或路线图。",
                "evidence": "C2G 任务、路线图和验收条件。",
                "done_when": "协议缺口有 owner、优先级和验收口径。",
            },
        ),
    },
    {
        "id": "control-plane-onboarding-loop",
        "title": "控制面接入闭环",
        "goal": "注册新实例后，依次确认路由、领域挂载和运行探针，避免只写入配置不验证链路。",
        "frequency": "on-demand",
        "owner": "operator",
        "risk": "medium",
        "steps": (
            {
                "id": "control-plane-register",
                "page_id": "Settings",
                "action": "登记实例服务名和 MCP 接入点。",
                "evidence": "注册响应、实例地址和控制面状态。",
                "done_when": "实例注册结果明确且没有把 token 写入页面或日志。",
            },
            {
                "id": "control-plane-route-check",
                "page_id": "McpMesh",
                "action": "确认实例进入网格并能解析路由。",
                "evidence": "MCP 实例、BOS URI 和路由探针。",
                "done_when": "新实例有可验证的路由证据。",
            },
            {
                "id": "control-plane-domain-check",
                "page_id": "DomainApps",
                "action": "涉及领域应用时，检查 contract、SSOT 和安全门。",
                "evidence": "应用中心的 contract、健康和安全检查。",
                "done_when": "领域边界和写入风险明确。",
            },
            {
                "id": "control-plane-runtime-check",
                "page_id": "Overview",
                "action": "用真实运行探针确认实例状态。",
                "evidence": "服务状态、端口监听和健康结果。",
                "done_when": "配置、路由和运行三层状态一致。",
            },
        ),
    },
    {
        "id": "runtime-diagnostic-loop",
        "title": "运行诊断闭环",
        "goal": "从真实探针确认运行状态，用资源、拓扑和日志逐步缩小问题范围。",
        "frequency": "on-demand",
        "owner": "operator",
        "risk": "low",
        "steps": (
            {
                "id": "runtime-overview",
                "page_id": "Overview",
                "action": "确认服务节点和运行探针是否有异常。",
                "evidence": "服务状态、端口监听和健康状态。",
                "done_when": "问题范围缩小到具体服务或明确无运行异常。",
            },
            {
                "id": "runtime-performance",
                "page_id": "Performance",
                "action": "查看真实 CPU、内存、磁盘和网络采样。",
                "evidence": "psutil 实时采样和服务资源可用性。",
                "done_when": "确认资源瓶颈存在或排除资源因素。",
            },
            {
                "id": "runtime-topology",
                "page_id": "Topology",
                "action": "只依据显式依赖关系检查服务拓扑，不把推断连线当证据。",
                "evidence": "运行节点和服务声明的依赖边。",
                "done_when": "调用关系有来源，或明确缺少关系证据。",
            },
            {
                "id": "runtime-log-context",
                "page_id": "LogViewer",
                "action": "在明确时间窗口和服务范围内查看日志现场。",
                "evidence": "日志片段、时间窗口和服务过滤条件。",
                "done_when": "异常有可回跳的日志证据。",
            },
        ),
    },
    {
        "id": "safe-execution-loop",
        "title": "安全执行闭环",
        "goal": "用隔离实验降低执行风险，再把可复现结果沉到正式任务和工作流。",
        "frequency": "on-demand",
        "owner": "engineering",
        "risk": "medium",
        "steps": (
            {
                "id": "sandbox-experiment",
                "page_id": "Sandbox",
                "action": "在隔离环境执行最小复现片段。",
                "evidence": "沙箱代码、标准输出和执行结果。",
                "done_when": "实验结果可复现且未越过安全门。",
            },
            {
                "id": "sandbox-task-handoff",
                "page_id": "TaskCenter",
                "action": "把下一步沉到正式任务或只读草稿。",
                "evidence": "任务状态、来源和操作证据。",
                "done_when": "后续动作有负责人和可追踪入口。",
            },
            {
                "id": "sandbox-workflow-check",
                "page_id": "Workflows",
                "action": "需要重复执行时，检查是否已有受控工作流。",
                "evidence": "工作流定义、审批节点和最近运行记录。",
                "done_when": "确认复用现有工作流或提出补能力项。",
            },
        ),
    },
)


ROADMAP_ITEMS: tuple[dict[str, Any], ...] = (
    {
        "id": "first-mile-system-map",
        "priority": "P0",
        "stage": "now",
        "status": "shipped",
        "title": "建立 Cockpit 第一入口地图",
        "domain": "entry",
        "cockpit_page": "SystemMap",
        "problem": "页面多但缺一张总图，用户不知道从哪里开始。",
        "actions": (
            "按站点结构、使用路径、架构层级、功能域和项目矩阵组织入口。",
            "把权威读源集中展示，避免 Cockpit 自己维护漂移事实。",
        ),
        "acceptance": (
            "用户能从首页或侧边栏进入 SystemMap。",
            "SystemMap 能定位项目、能力域、常用路径和 SSOT 读源。",
        ),
    },
    {
        "id": "global-search-routing",
        "priority": "P0",
        "stage": "now",
        "status": "shipped",
        "title": "让全局搜索真正能导航",
        "domain": "entry",
        "cockpit_page": "SystemMap",
        "problem": "顶部搜索框原先更像摆设，不能跨页面、项目、能力域检索。",
        "actions": (
            "接入页面、项目别名和能力关键词的站内导航搜索。",
            "支持输入项目名、能力域、页面名后直接跳转目标页面。",
        ),
        "acceptance": (
            "搜索 cockpit、治理、OPC、compute 等关键词能返回可点击入口。",
            "无匹配时明确提示，不吞键盘操作。",
        ),
    },
    {
        "id": "domain-app-health-actions",
        "priority": "P0",
        "stage": "now",
        "status": "shipped",
        "title": "领域应用健康检查与启动动作",
        "domain": "domain-apps",
        "cockpit_page": "DomainApps",
        "problem": "应用中心能展示 contract，但启动、健康检查、验证还没有形成闭环。",
        "actions": (
            "为每个 domain app 增加 health probe 和 verify command 状态。",
            "把 start/open/verify 的边界明确成只读、复制命令或受控动作。",
        ),
        "acceptance": (
            "家庭驾驶舱、OPC、family-hub 都显示最新健康状态。",
            "高风险写入类能力在 UI 中有安全门提示。",
        ),
    },
    {
        "id": "project-native-status",
        "priority": "P1",
        "stage": "next",
        "status": "shipped",
        "title": "把定位视图升级为项目原生状态面",
        "domain": "project-coverage",
        "cockpit_page": "SystemMap",
        "problem": "部分项目原先只能被定位，缺少目录、文档、命令和构建清单状态。",
        "actions": (
            "从项目目录、AGENTS.md 和常见 manifest 读取基础状态。",
            "在项目矩阵中展示文档覆盖、命令、风险和下一步。",
        ),
        "acceptance": (
            "项目矩阵不只显示职责，还能看到基础可操作状态。",
            "缺文档、缺命令或缺 manifest 的项目有明确风险提示。",
        ),
    },
    {
        "id": "project-runtime-probes",
        "priority": "P1",
        "stage": "next",
        "status": "shipped",
        "title": "项目运行探针与最近验证",
        "domain": "project-coverage",
        "cockpit_page": "SystemMap",
        "problem": "基础状态已接入后，还需要把端口监听和最近验证放到同一个项目面。",
        "actions": (
            "接入端口注册表和 agent-workflow 验证事件。",
            "在项目矩阵中显示运行状态、监听端口和最近验证。",
        ),
        "acceptance": (
            "项目矩阵能区分目录就绪、服务运行、验证通过三个层次。",
            "高频项目能看到最近一次验证命令和结果。",
        ),
    },
    {
        "id": "project-runtime-actions",
        "priority": "P2",
        "stage": "now",
        "status": "shipped",
        "title": "项目级受控运行操作",
        "domain": "project-coverage",
        "cockpit_page": "SystemMap",
        "problem": "Cockpit 现在能看项目运行态，但还不能安全地执行项目级 start/verify/restart。",
        "actions": (
            "把可执行动作收敛到受控命令和确认门。",
            "高风险操作只提供复制命令或显式确认入口。",
        ),
        "acceptance": (
            "项目矩阵能区分只读信息和可执行动作。",
            "所有执行动作都有审计和失败反馈。",
        ),
    },
    {
        "id": "project-action-execution-audit",
        "priority": "P2",
        "stage": "later",
        "status": "planned",
        "title": "项目动作执行与审计",
        "domain": "project-coverage",
        "cockpit_page": "TaskCenter",
        "problem": "项目动作现在只提供复制命令和导航，尚未接入带确认门的后台执行与审计。",
        "actions": (
            "把 start/verify/restart 收敛到受控任务队列。",
            "为高风险动作增加确认门、超时、日志和失败回滚提示。",
        ),
        "acceptance": (
            "用户能在 TaskCenter 看到项目动作执行历史。",
            "每次执行都有命令、退出码、日志位置和触发人。",
        ),
    },
    {
        "id": "ssot-deep-links",
        "priority": "P1",
        "stage": "now",
        "status": "shipped",
        "title": "SSOT 行级深链",
        "domain": "governance",
        "cockpit_page": "SystemMap",
        "problem": "当前能指向权威文件，但不能一键定位到具体条目。",
        "actions": (
            "为 project registry、port registry、BOS services、GaC rules 生成行级定位。",
            "在页面卡片上补 source key 和 source path。",
        ),
        "acceptance": (
            "点击项目或能力能知道权威读源和具体来源。",
            "新增页面不会复制易漂移计数。",
        ),
    },
    {
        "id": "source-open-actions",
        "priority": "P2",
        "stage": "now",
        "status": "shipped",
        "title": "来源证据预览",
        "domain": "governance",
        "cockpit_page": "SystemMap",
        "problem": "当前已经能展示和复制 path:line，但用户仍需要离开 Cockpit 才能核对来源内容。",
        "actions": (
            "提供只读 source_ref 预览接口，按 workspace 白名单读取目标行附近内容。",
            "前端点击来源定位时直接展示文件、行号和上下文，同时保留复制精确位置。",
        ),
        "acceptance": (
            "点击来源能在 SystemMap 内看到目标行附近的权威内容。",
            "预览接口拒绝 Workspace 外部路径，且不执行本机打开命令。",
        ),
    },
    {
        "id": "guided-ops-checklists",
        "priority": "P2",
        "stage": "now",
        "status": "shipped",
        "title": "面向场景的操作清单",
        "domain": "usage",
        "cockpit_page": "SystemMap",
        "problem": "使用路径已经成型，但还没有逐步勾选式执行面。",
        "actions": (
            "把日常体检、治理闭环、知识工作、领域作战做成 checklist。",
            "把 checklist 的完成证据连接到任务中心和日志。",
        ),
        "acceptance": (
            "用户能按场景完成一次端到端巡检。",
            "每个 checklist 有下一步入口和证据位置。",
        ),
    },
    {
        "id": "playbook-evidence-persistence",
        "priority": "P2",
        "stage": "now",
        "status": "shipped",
        "title": "操作清单证据持久化",
        "domain": "usage",
        "cockpit_page": "TaskCenter",
        "problem": "操作清单现在能指导使用，但完成状态和证据还需要进入任务中心。",
        "actions": (
            "为 playbook step 增加任务中心只读草稿和证据字段。",
            "先提供可复制任务材料，正式写入仍走 C2G/OMO 受控入口。",
        ),
        "acceptance": (
            "用户能在 TaskCenter 看见每个 playbook 的任务草稿。",
            "草稿包含步骤、证据字段和安全门说明。",
        ),
    },
    {
        "id": "playbook-omo-writeback",
        "priority": "P2",
        "stage": "later",
        "status": "planned",
        "title": "操作清单写入 OMO",
        "domain": "usage",
        "cockpit_page": "TaskCenter",
        "problem": "TaskCenter 已能展示 playbook 草稿，但还没有通过 C2G/OMO 正式创建治理任务。",
        "actions": (
            "把 playbook 草稿提交到 C2G/OMO broker。",
            "记录完成时间、证据链接和触发来源。",
        ),
        "acceptance": (
            "用户能把草稿转成正式 OMO planned task。",
            "写入有审计记录且不绕过治理 broker。",
        ),
    },
)


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        if path.name == "port-registry.yaml":
            return _recover_port_registry(path)
        return {}


def _recover_port_registry(path: Path) -> dict[str, Any]:
    """Recover simple port records while preserving a malformed-registry signal.

    The registry is an external SSOT and remains read-only here. This parser only
    recovers the stable ``port -> name/transport/status`` records needed for the
    project runtime view; it never invents a port or a listening result.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    ports: dict[int, dict[str, str]] = {}
    current_port: int | None = None
    current: dict[str, str] = {}

    def flush() -> None:
        if current_port is not None and current.get("name"):
            ports[current_port] = dict(current)

    for line in lines:
        port_match = re.match(r"^\s{2}(\d+):\s*$", line)
        if port_match:
            flush()
            current_port = int(port_match.group(1))
            current = {}
            continue
        if current_port is None:
            continue
        field_match = re.match(r'^\s{4}(name|transport|status):\s*["\']?([^"\']+?)["\']?\s*$', line)
        if field_match:
            current[field_match.group(1)] = field_match.group(2).strip()
    flush()

    return {"ports": ports, "types": {}, "_parse_warning": "port-registry.yaml recovered after YAML parse failure"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _read_text_lossy(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=404, detail="source file is not readable") from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _path_state(path: Path) -> dict[str, Any]:
    return {"path": str(path), "exists": path.exists()}


def _exists_any(base: Path, candidates: tuple[str, ...]) -> bool:
    return any((base / candidate).exists() for candidate in candidates)


def _line_number(path: Path, pattern: str) -> int | None:
    text = _read_text(path)
    if not text:
        return None
    matcher = re.compile(pattern)
    for index, line in enumerate(text.splitlines(), start=1):
        if matcher.search(line):
            return index
    return None


def _source_ref(path: Path, label: str, source_key: str, line: int | None = None) -> dict[str, Any]:
    target = str(path)
    if line:
        target = f"{target}:{line}"
    return {
        "source_key": source_key,
        "label": label,
        "path": str(path),
        "line": line,
        "exists": path.exists(),
        "target": target,
    }


def _source_ref_for_id(path: Path, item_id: str, label: str, source_key: str) -> dict[str, Any]:
    return _source_ref(path, label, source_key, _line_number(path, rf'"id": "{re.escape(item_id)}"'))


def _parse_source_ref_target(target: str | None, path: str | None, line: int | None) -> tuple[Path, int | None]:
    raw_path = path
    parsed_line = line
    if target:
        raw_target = target.strip()
        line_match = re.match(r"^(?P<path>.+):(?P<line>\d+)$", raw_target)
        if line_match:
            raw_path = line_match.group("path")
            parsed_line = int(line_match.group("line"))
        else:
            raw_path = raw_target
    if not raw_path:
        raise HTTPException(status_code=400, detail="target or path is required")

    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = WORKSPACE_ROOT / candidate
    resolved = candidate.resolve(strict=False)
    workspace_root = WORKSPACE_ROOT.resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="source path must stay inside workspace") from exc
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="source file does not exist")
    if resolved.stat().st_size > MAX_SOURCE_PREVIEW_BYTES:
        raise HTTPException(status_code=413, detail="source file is too large for preview")
    return resolved, max(1, parsed_line) if parsed_line else None


def build_source_ref_preview(
    target: str | None = None,
    path: str | None = None,
    line: int | None = None,
    context: int = 4,
) -> dict[str, Any]:
    source_path, source_line = _parse_source_ref_target(target, path, line)
    text = _read_text_lossy(source_path)
    lines = text.splitlines()
    total_lines = len(lines)
    focus_line = min(source_line or 1, total_lines or 1)
    start = max(1, focus_line - context)
    end = min(total_lines, focus_line + context) if total_lines else 0
    preview_lines = [
        {
            "number": number,
            "text": lines[number - 1],
            "highlight": bool(source_line and number == focus_line),
        }
        for number in range(start, end + 1)
    ]
    return {
        "path": str(source_path),
        "workspace_relative_path": str(source_path.relative_to(WORKSPACE_ROOT.resolve())),
        "line": source_line,
        "target": f"{source_path}:{source_line}" if source_line else str(source_path),
        "total_lines": total_lines,
        "context_start": start,
        "context_end": end,
        "lines": preview_lines,
        "guard": "只读来源预览；路径必须位于当前 Workspace 内，接口不执行本机打开命令。",
    }


def _command_with_cwd(path: Path, command: str) -> str:
    return f'cd "{path}" && {command}'


def _first_matching_command(commands: list[str], include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> str | None:
    for command in commands:
        lowered = command.lower()
        if any(token in lowered for token in include) and not any(token in lowered for token in exclude):
            return command
    return None


def _package_scripts(path: Path) -> dict[str, str]:
    package = _read_json(path / "package.json")
    scripts = package.get("scripts")
    if isinstance(scripts, dict):
        return {str(key): str(value) for key, value in scripts.items()}
    return {}


def _project_verify_command(path: Path, commands: list[str], manifests: list[dict[str, Any]]) -> str | None:
    command = _first_matching_command(
        commands,
        ("verify", "test", "lint", "build", "pytest", "gac", "docker compose config"),
        ("dev", "serve", "start"),
    )
    if command:
        return _command_with_cwd(path, command)

    manifest_names = {item["name"] for item in manifests}
    scripts = _package_scripts(path)
    if "test" in scripts:
        return _command_with_cwd(path, "bun run test")
    if "build" in scripts:
        return _command_with_cwd(path, "bun run build")
    if "pyproject.toml" in manifest_names:
        return _command_with_cwd(path, "uv run pytest -q")
    if "docker-compose.yml" in manifest_names:
        return _command_with_cwd(path, "docker compose config -q")
    return None


def _project_start_command(path: Path, commands: list[str]) -> str | None:
    command = _first_matching_command(
        commands,
        ("dev", "serve", "start", "uvicorn", "dashboard_server", "run api"),
        ("test", "lint", "build", "verify"),
    )
    if command:
        return _command_with_cwd(path, command)

    scripts = _package_scripts(path)
    if "dev" in scripts:
        return _command_with_cwd(path, "bun run dev")
    if "api" in scripts:
        return _command_with_cwd(path, "bun run api")
    return None


def _project_actions(
    project_id: str, project_path: Path, page_id: str, operational: dict[str, Any]
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = [
        {
            "id": "open-cockpit-page",
            "label": "打开入口",
            "kind": "navigate",
            "value": page_id,
            "enabled": True,
            "risk": "low",
            "executes": False,
            "guard": "站内导航，不执行项目命令。",
        },
        {
            "id": "copy-project-path",
            "label": "复制路径",
            "kind": "copy_text",
            "value": str(project_path),
            "enabled": project_path.exists(),
            "risk": "low",
            "executes": False,
            "guard": "只复制项目路径，不读取或写入项目数据。",
        },
    ]

    commands = list(operational.get("commands") or [])
    manifests = list(operational.get("manifests") or [])
    verify_command = _project_verify_command(project_path, commands, manifests)
    if verify_command:
        actions.append(
            {
                "id": "copy-verify-command",
                "label": "复制验证",
                "kind": "copy_command",
                "value": verify_command,
                "enabled": project_path.exists(),
                "risk": "low",
                "executes": False,
                "guard": "复制验证命令，由用户在终端手动执行。",
            }
        )

    start_command = _project_start_command(project_path, commands)
    if start_command:
        actions.append(
            {
                "id": "copy-start-command",
                "label": "复制启动",
                "kind": "copy_command",
                "value": start_command,
                "enabled": project_path.exists(),
                "risk": "medium",
                "executes": False,
                "guard": "复制启动命令；Cockpit 不直接启动或重启服务。",
            }
        )

    if project_id == "cockpit":
        actions.append(
            {
                "id": "copy-cockpit-preview",
                "label": "复制预览",
                "kind": "copy_text",
                "value": "http://127.0.0.1:5173/",
                "enabled": True,
                "risk": "low",
                "executes": False,
                "guard": "复制当前 Cockpit 前端预览地址。",
            }
        )

    return actions


def _first_action(actions: list[dict[str, Any]], action_id: str) -> dict[str, Any] | None:
    return next((action for action in actions if action.get("id") == action_id), None)


def _triage_command(
    project_id: str,
    command_id: str,
    label: str,
    category: str,
    command: str,
    reason: str,
    *,
    enabled: bool = True,
    risk: str = "low",
) -> dict[str, Any]:
    return {
        "id": command_id,
        "label": label,
        "kind": "copy_command",
        "value": command,
        "enabled": enabled,
        "risk": risk,
        "executes": False,
        "guard": "复制排查命令；Cockpit 不直接执行终端命令。",
        "category": category,
        "project_id": project_id,
        "reason": reason,
    }


def _port_probe_command(ports: list[dict[str, Any]]) -> str | None:
    port_values = [str(port["port"]) for port in ports[:6] if port.get("port")]
    if not port_values:
        return None
    return f"for port in {' '.join(port_values)}; do lsof -nP -iTCP:$port -sTCP:LISTEN || true; done"


def _port_registry_search_command(project_id: str) -> str:
    aliases = PROJECT_PORT_ALIASES.get(project_id, (project_id,))
    pattern = "|".join(re.escape(alias) for alias in aliases)
    return _command_with_cwd(
        WORKSPACE_ROOT,
        f'rg -n "{pattern}" "protocols/port-registry.yaml" "projects/agora/etc/bos-services.yaml"',
    )


def _workflow_evidence_search_command(project_id: str) -> str:
    return _command_with_cwd(WORKSPACE_ROOT, f'rg -n "{re.escape(project_id)}" ".omo/_delivery/agent-workflows/runs"')


def _project_inventory_command(project_path: Path) -> str:
    return _command_with_cwd(
        project_path,
        'ls -la "AGENTS.md" "CLAUDE.md" "README.md" "ARCHITECTURE.md" '
        '"pyproject.toml" "package.json" "docker-compose.yml" 2>/dev/null || true',
    )


def _project_triage_commands(project: dict[str, Any]) -> list[dict[str, Any]]:
    project_id = project["id"]
    project_path = Path(project["path"])
    runtime = project.get("runtime", {})
    verification = runtime.get("latest_verification", {})
    actions = list(project.get("actions") or [])
    commands: list[dict[str, Any]] = []

    port_command = _port_probe_command(runtime.get("ports") or [])
    if port_command:
        commands.append(
            _triage_command(
                project_id,
                "runtime-check-ports",
                "检查端口",
                "runtime",
                port_command,
                "确认已登记端口是否真的在本机监听。",
                risk="low" if runtime.get("status") == "running" else "medium",
            )
        )

    if runtime.get("status") == "stopped":
        start_action = _first_action(actions, "copy-start-command")
        if start_action:
            commands.append(
                _triage_command(
                    project_id,
                    "runtime-copy-start",
                    "复制启动",
                    "runtime",
                    start_action["value"],
                    "项目端口已登记但未监听，先复制启动命令由人确认执行。",
                    enabled=bool(start_action.get("enabled")),
                    risk="medium",
                )
            )

    if runtime.get("status") == "unobserved":
        commands.append(
            _triage_command(
                project_id,
                "runtime-find-registry",
                "查端口登记",
                "runtime",
                _port_registry_search_command(project_id),
                "项目缺少可观测端口，先核对端口注册表和 BOS 服务。",
                risk="low",
            )
        )

    if verification.get("status") in {"failed", "unknown"}:
        verify_action = _first_action(actions, "copy-verify-command")
        if verify_action:
            commands.append(
                _triage_command(
                    project_id,
                    "verification-rerun",
                    "复跑验证",
                    "verification",
                    verify_action["value"],
                    "最近验证失败或缺失，复制项目验证命令复现。",
                    enabled=bool(verify_action.get("enabled")),
                    risk="low",
                )
            )
        commands.append(
            _triage_command(
                project_id,
                "verification-find-evidence",
                "查验证证据",
                "verification",
                _workflow_evidence_search_command(project_id),
                "查找 agent-workflow 里是否已有该项目的验证或 closeout 证据。",
                risk="low",
            )
        )

    if project.get("operational", {}).get("status") != "ready":
        commands.append(
            _triage_command(
                project_id,
                "coverage-inventory",
                "查项目清单",
                "coverage",
                _project_inventory_command(project_path),
                "项目文档、命令或 manifest 不完整，先核对本地清单。",
                enabled=project_path.exists(),
                risk="low",
            )
        )

    return commands


def _is_port_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.04):
            return True
    except OSError:
        return False


def _project_ports(project_id: str, port_registry: dict[str, Any], port_registry_path: Path) -> list[dict[str, Any]]:
    aliases = PROJECT_PORT_ALIASES.get(project_id, (project_id,))
    registry_ports = port_registry.get("ports") or {}
    port_types = port_registry.get("types") or {}
    ports: list[dict[str, Any]] = []

    for raw_port, service in registry_ports.items():
        try:
            port = int(raw_port)
        except (TypeError, ValueError):
            continue
        if isinstance(service, dict):
            label = str(service.get("name") or service.get("service") or "")
            transport = service.get("transport")
        else:
            label = str(service)
            transport = None
        service_name = label.split("#", 1)[0].strip()
        searchable = service_name.lower()
        if any(alias.lower() in searchable for alias in aliases):
            ports.append(
                {
                    "port": port,
                    "service": service_name or label,
                    "raw_label": label,
                    "type": transport or port_types.get(port) or port_types.get(str(port)) or "registered",
                    "listening": _is_port_listening(port),
                    "source_ref": _source_ref(
                        port_registry_path,
                        f"端口 {port}",
                        "port_registry",
                        _line_number(port_registry_path, rf"^\s*{port}:\s"),
                    ),
                }
            )

    return sorted(ports, key=lambda item: item["port"])


def _latest_project_verification(project_id: str, project_path: Path, operational: dict[str, Any]) -> dict[str, Any]:
    events_path = WORKSPACE_ROOT / ".omo" / "_delivery" / "agent-workflows" / "events.jsonl"
    project_prefix = f"projects/{project_id}"
    claims_by_run: dict[str, set[str]] = defaultdict(set)
    verify_events: list[dict[str, Any]] = []

    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []

    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        run_id = event.get("run_id")
        if not run_id:
            continue
        if event.get("event") == "agent_workflow_claim":
            for path in event.get("paths") or []:
                claims_by_run[run_id].add(str(path))
        if event.get("event") == "agent_workflow_verify":
            verify_events.append(event)

    for event in reversed(verify_events):
        run_id = event.get("run_id", "")
        surfaces = set(str(path) for path in (event.get("changed_files") or []))
        surfaces.update(claims_by_run.get(run_id, set()))
        if any(path == project_prefix or path.startswith(f"{project_prefix}/") for path in surfaces):
            return {
                "status": "verified" if event.get("ok") else "failed",
                "run_id": run_id,
                "ts": event.get("ts"),
                "checks": len(event.get("checks") or []),
                "command": None,
                "source": "agent_workflow",
            }

    verify_command = _project_verify_command(
        project_path,
        list(operational.get("commands") or []),
        list(operational.get("manifests") or []),
    )
    if verify_command:
        return {
            "status": "documented",
            "run_id": None,
            "ts": None,
            "checks": 0,
            "command": verify_command,
            "source": "project_commands",
        }

    return {
        "status": "unknown",
        "run_id": None,
        "ts": None,
        "checks": 0,
        "command": None,
        "source": "missing",
    }


def _project_workflow_lifecycle(project_id: str) -> dict[str, Any]:
    events_path = WORKSPACE_ROOT / ".omo" / "_delivery" / "agent-workflows" / "events.jsonl"
    project_prefix = f"projects/{project_id}"
    events_by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)

    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {
            "latest_run_id": None,
            "latest_status": "unknown",
            "latest_ts": None,
            "runs": [],
            "summary": {"runs": 0, "verified": 0, "failed": 0, "active": 0},
        }

    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        run_id = event.get("run_id")
        if run_id:
            events_by_run[str(run_id)].append(event)

    runs: list[dict[str, Any]] = []
    for run_id, events in events_by_run.items():
        surfaces: set[str] = set()
        for event in events:
            surfaces.update(str(path) for path in (event.get("paths") or []))
            surfaces.update(str(path) for path in (event.get("changed_files") or []))
        project_surfaces = sorted(
            path for path in surfaces if path == project_prefix or path.startswith(f"{project_prefix}/")
        )
        if not project_surfaces:
            continue

        timeline: list[dict[str, Any]] = []
        start_event = next((event for event in events if event.get("event") == "agent_workflow_start"), None)
        workflow_id = start_event.get("workflow_id") if start_event else "unknown"
        objective = start_event.get("objective") if start_event else ""
        status = "active"
        verify_status = "unknown"
        verify_checks = 0
        latest_ts = events[-1].get("ts")

        for event in events:
            event_type = event.get("event")
            if event_type == "agent_workflow_start":
                timeline.append(
                    {
                        "type": "start",
                        "status": "started",
                        "ts": event.get("ts"),
                        "summary": event.get("objective") or workflow_id,
                    }
                )
            elif event_type == "agent_workflow_claim":
                claimed_paths = [
                    str(path)
                    for path in (event.get("paths") or [])
                    if str(path) == project_prefix or str(path).startswith(f"{project_prefix}/")
                ]
                if claimed_paths:
                    timeline.append(
                        {
                            "type": "claim",
                            "status": "claimed",
                            "ts": event.get("ts"),
                            "summary": f"claimed {len(claimed_paths)} path(s)",
                            "paths": claimed_paths[:6],
                        }
                    )
            elif event_type == "agent_workflow_verify":
                changed = [
                    str(path)
                    for path in (event.get("changed_files") or [])
                    if str(path) == project_prefix or str(path).startswith(f"{project_prefix}/")
                ]
                if changed:
                    ok = bool(event.get("ok"))
                    verify_status = "verified" if ok else "failed"
                    verify_checks = len(event.get("checks") or [])
                    status = verify_status
                    timeline.append(
                        {
                            "type": "verify",
                            "status": verify_status,
                            "ts": event.get("ts"),
                            "summary": f"checks={verify_checks}",
                            "paths": changed[:6],
                        }
                    )
            elif event_type == "agent_workflow_closeout":
                ok = bool(event.get("ok"))
                status = "closed" if ok else "failed"
                timeline.append(
                    {
                        "type": "closeout",
                        "status": status,
                        "ts": event.get("ts"),
                        "summary": f"status={event.get('status', 'unknown')}",
                    }
                )

        runs.append(
            {
                "run_id": run_id,
                "workflow_id": workflow_id,
                "objective": objective or "",
                "status": status,
                "verify_status": verify_status,
                "verify_checks": verify_checks,
                "latest_ts": latest_ts,
                "paths": project_surfaces[:8],
                "events": timeline[-8:],
            }
        )

    runs.sort(key=lambda item: item.get("latest_ts") or "", reverse=True)
    visible_runs = runs[:4]
    return {
        "latest_run_id": visible_runs[0]["run_id"] if visible_runs else None,
        "latest_status": visible_runs[0]["status"] if visible_runs else "unknown",
        "latest_ts": visible_runs[0]["latest_ts"] if visible_runs else None,
        "runs": visible_runs,
        "summary": {
            "runs": len(runs),
            "verified": sum(1 for run in runs if run["verify_status"] == "verified"),
            "failed": sum(1 for run in runs if run["verify_status"] == "failed" or run["status"] == "failed"),
            "active": sum(1 for run in runs if run["status"] == "active"),
        },
    }


def _commands_from_agents(path: Path, limit: int = 4) -> list[str]:
    text = _read_text(path / "AGENTS.md")
    if not text:
        return []

    match = re.search(r"## Commands\s*```(?:\w+)?\s*(.*?)```", text, re.DOTALL)
    if not match:
        return []

    commands: list[str] = []
    for raw_line in match.group(1).splitlines():
        command = raw_line.strip()
        if command and not command.startswith("#"):
            commands.append(command)
        if len(commands) >= limit:
            break
    return commands


def _read_package_manifest(project_path: Path) -> dict[str, Any]:
    manifest = _read_json(project_path / "package.json")
    return manifest if isinstance(manifest, dict) else {}


def _runtime_profile(
    project_id: str,
    project_data: dict[str, Any],
    project_path: Path,
    operational: dict[str, Any],
    ports: list[dict[str, Any]],
) -> dict[str, Any]:
    role_text = str(project_data.get("role") or "").lower()
    stack_text = str(project_data.get("stack") or "").lower()
    commands = operational.get("commands") or []
    commands_text = " ".join(commands).lower()
    package_manifest = _read_package_manifest(project_path)
    scripts = package_manifest.get("scripts") if isinstance(package_manifest.get("scripts"), dict) else {}
    script_text = " ".join(f"{key} {value}" for key, value in scripts.items() if isinstance(value, str)).lower()
    manifests = {item.get("name") for item in (operational.get("manifests") or [])}

    if ports:
        return {
            "profile": "service",
            "needs_runtime": True,
            "probe_reason": "已登记可观测端口，可直接用监听结果判断运行状态。",
        }

    if "docker-compose.yml" in manifests:
        return {
            "profile": "service",
            "needs_runtime": True,
            "probe_reason": "存在 compose 运行清单，但当前缺少端口登记。",
        }

    if _exists_any(project_path, VITE_CONFIGS) or _exists_any(project_path, STATIC_FRONTEND_MARKERS):
        return {
            "profile": "static",
            "needs_runtime": False,
            "probe_reason": "检测到 Vite/静态前端入口，按需启动开发服务器，不作为常驻运行探针。",
        }

    if _exists_any(project_path, NEXT_CONFIGS):
        return {
            "profile": "service",
            "needs_runtime": True,
            "probe_reason": "检测到 Next.js 应用配置，通常需要显式启动并登记访问端口。",
        }

    if _exists_any(project_path, SERVICE_ENTRYPOINTS) or any(
        token in f"{commands_text} {script_text}"
        for token in ("uvicorn", "gunicorn", "fastapi", "server.ts", "server.py", "api/server", "dashboard_server")
    ):
        return {
            "profile": "service",
            "needs_runtime": True,
            "probe_reason": "检测到服务入口或启动脚本，但尚未登记运行端口。",
        }

    if _exists_any(project_path, CLI_ENTRYPOINTS) or "cli" in role_text or "cli" in commands_text:
        return {
            "profile": "cli",
            "needs_runtime": False,
            "probe_reason": "检测到 CLI 入口，命令按需执行即可，不需要常驻探针。",
        }

    if "pyproject.toml" in manifests:
        return {
            "profile": "library",
            "needs_runtime": False,
            "probe_reason": "当前更像库/框架型 Python 项目，主要靠构建与测试验证，而不是常驻服务端口。",
        }

    if "package.json" in manifests and any(
        token in f"{role_text} {stack_text}" for token in ("ui", "frontend", "前端")
    ):
        return {
            "profile": "static",
            "needs_runtime": False,
            "probe_reason": "项目角色更接近前端表现层，端口只在本地调试时按需出现。",
        }

    if any(token in f"{role_text} {stack_text}" for token in ("sdk", "framework", "monorepo", "库", "框架")):
        return {
            "profile": "library",
            "needs_runtime": False,
            "probe_reason": "项目描述偏向框架/SDK/monorepo 形态，不以常驻运行探针为主。",
        }

    return {
        "profile": "unknown",
        "needs_runtime": True,
        "probe_reason": "尚未识别运行形态；如果该项目需要服务进程，请补端口注册，否则补充无需常驻的依据。",
    }


def _project_runtime_status(
    project_id: str,
    project_data: dict[str, Any],
    operational: dict[str, Any],
    port_registry: dict[str, Any],
    port_registry_path: Path,
) -> dict[str, Any]:
    project_path = WORKSPACE_ROOT / "projects" / project_id
    ports = _project_ports(project_id, port_registry, port_registry_path)
    latest_verification = _latest_project_verification(project_id, project_path, operational)
    listening_count = sum(1 for port in ports if port["listening"])
    profile = _runtime_profile(project_id, project_data, project_path, operational, ports)

    if listening_count:
        status = "running"
        probe_reason = "已探测到登记端口正在监听。"
    elif ports:
        status = "stopped"
        probe_reason = "已登记端口但当前未监听，需要人工确认是否应启动。"
    elif not profile["needs_runtime"]:
        status = "not_applicable"
        probe_reason = profile["probe_reason"]
    else:
        status = "unobserved"
        probe_reason = profile["probe_reason"]

    return {
        "status": status,
        "profile": profile["profile"],
        "needs_runtime": profile["needs_runtime"],
        "probe_reason": probe_reason,
        "ports": ports,
        "listening_count": listening_count,
        "latest_verification": latest_verification,
    }


def _project_operational_status(project_id: str) -> dict[str, Any]:
    path = WORKSPACE_ROOT / "projects" / project_id
    doc_files = [
        {"name": name, "path": str(path / name), "exists": (path / name).exists()} for name in PROJECT_DOC_FILES
    ]
    present_docs = [item for item in doc_files if item["exists"]]
    commands = _commands_from_agents(path)
    manifests = [
        {"name": name, "path": str(path / name), "exists": (path / name).exists()} for name in PACKAGE_MANIFESTS
    ]
    existing_manifests = [item for item in manifests if item["exists"]]

    risks: list[str] = []
    if not path.exists():
        risks.append("project_path_missing")
    if not present_docs:
        risks.append("docs_missing")
    if not commands:
        risks.append("commands_missing")
    if not existing_manifests:
        risks.append("manifest_missing")

    if not path.exists():
        status = "missing"
    elif risks:
        status = "partial"
    else:
        status = "ready"

    next_action = {
        "ready": "保持项目注册表与 Cockpit 映射同步。",
        "partial": "补齐项目文档、命令或构建清单后升级为原生状态面。",
        "missing": "确认项目是否已归档、迁移或需要从注册表下线。",
    }[status]

    return {
        "status": status,
        "docs": {
            "present": len(present_docs),
            "expected": len(PROJECT_DOC_FILES),
            "items": doc_files,
        },
        "commands": commands,
        "manifests": existing_manifests,
        "risks": risks,
        "next_action": next_action,
    }


def _parse_capability_domains(path: Path) -> list[dict[str, Any]]:
    text = _read_text(path)
    headings = list(re.finditer(r"^##\s+([1-8])\.\s+(.+?)(?:\s+\((.*?)\))?\s*$", text, re.MULTILINE))
    domains: list[dict[str, Any]] = []

    for index, match in enumerate(headings):
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[start:end]
        title = match.group(2).strip()
        english = (match.group(3) or "").strip()
        rows = _parse_markdown_rows(body)
        providers = sorted(
            {
                provider.strip()
                for row in rows
                for provider in re.split(r"\s*\+\s*|\s*,\s*| / ", row.get("提供者", ""))
                if provider.strip() and provider.strip() != "—"
            }
        )
        page_id = CAPABILITY_TO_PAGE.get(title, "SystemMap")
        domains.append(
            {
                "id": f"capability-{match.group(1)}",
                "title": title,
                "english": english,
                "capability_items": [row.get("能力", "") for row in rows if row.get("能力")],
                "providers": providers,
                "cockpit_page": page_id,
                "coverage": "native" if page_id != "SystemMap" else "orientation",
                "source_refs": [
                    _source_ref(
                        path,
                        f"能力域 {title}",
                        "functional_capability_map",
                        text[: match.start()].count("\n") + 1,
                    )
                ],
            }
        )

    return domains


def _parse_markdown_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if header is None:
            header = cells
            continue
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells, strict=False)))
    return rows


def _build_layers(
    registry: dict[str, Any], projects: list[dict[str, Any]], registry_path: Path
) -> list[dict[str, Any]]:
    layer_names = registry.get("layers") or {}
    projects_by_layer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for project in projects:
        projects_by_layer[project["layer"]].append(project)

    return [
        {
            "id": layer_id,
            "name": layer_name,
            "projects": projects_by_layer.get(layer_id, []),
            "project_count": len(projects_by_layer.get(layer_id, [])),
            "cockpit_pages": sorted({project["cockpit_page"] for project in projects_by_layer.get(layer_id, [])}),
            "source_refs": [
                _source_ref(
                    registry_path,
                    f"层级 {layer_id}",
                    "project_registry",
                    _line_number(registry_path, rf"^\s*{re.escape(layer_id)}:\s"),
                )
            ],
        }
        for layer_id, layer_name in layer_names.items()
    ]


def _project_source_refs(
    project_id: str, project_path: Path, registry_path: Path, ports: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    refs = [
        _source_ref(
            registry_path,
            "项目注册",
            "project_registry",
            _line_number(registry_path, rf"^\s*{re.escape(project_id)}:\s*$"),
        )
    ]
    agents_path = project_path / "AGENTS.md"
    if agents_path.exists():
        refs.append(_source_ref(agents_path, "项目操作指南", "project_agents", 1))
    for port in ports[:2]:
        source = port.get("source_ref")
        if source:
            refs.append(source)
    return refs


def _coverage_check(check_id: str, status: str, detail: str, next_action: str) -> dict[str, str]:
    definition = next(item for item in PROJECT_COVERAGE_DIMENSIONS if item["id"] == check_id)
    return {
        "id": check_id,
        "title": definition["title"],
        "status": status,
        "detail": detail,
        "next_action": next_action,
    }


def _project_coverage_checks(project: dict[str, Any]) -> list[dict[str, str]]:
    operational = project.get("operational", {})
    runtime = project.get("runtime", {})
    verification = runtime.get("latest_verification", {})
    source_refs = project.get("source_refs") or []
    actions = project.get("actions") or []

    docs = operational.get("docs") or {}
    docs_present = int(docs.get("present") or 0)
    docs_expected = int(docs.get("expected") or len(PROJECT_DOC_FILES))
    docs_status = "failed" if docs_present == 0 else "ready" if docs_present >= docs_expected else "warning"

    runtime_status = runtime.get("status")
    verification_status = verification.get("status")
    missing_sources = [ref for ref in source_refs if not ref.get("exists")]

    return [
        _coverage_check(
            "cockpit_surface",
            "ready" if project.get("coverage") == "native" else "warning",
            f"入口：{project.get('cockpit_page', 'SystemMap')}，覆盖：{project.get('coverage', 'orientation')}。",
            "保持页面映射同步。" if project.get("coverage") == "native" else "补原生项目页面或领域应用挂载入口。",
        ),
        _coverage_check(
            "project_docs",
            docs_status,
            f"已找到 {docs_present} / {docs_expected} 个项目文档。",
            "补齐缺失项目文档。" if docs_status != "ready" else "保持文档与项目状态同步。",
        ),
        _coverage_check(
            "commands",
            "ready" if operational.get("commands") else "failed",
            f"已登记 {len(operational.get('commands') or [])} 条操作命令。",
            "在项目 AGENTS.md 的 Commands 区块登记常用命令。"
            if not operational.get("commands")
            else "保持验证、启动和维护命令可复制。",
        ),
        _coverage_check(
            "manifest",
            "ready" if operational.get("manifests") else "failed",
            f"已发现 {len(operational.get('manifests') or [])} 个构建清单。",
            "补 pyproject.toml、package.json 或 docker-compose.yml。"
            if not operational.get("manifests")
            else "保持机器清单可被 Cockpit 识别。",
        ),
        _coverage_check(
            "runtime_probe",
            (
                "ready"
                if runtime_status in {"running", "not_applicable"}
                else "warning"
                if runtime_status == "stopped"
                else "failed"
            ),
            (
                f"运行状态：{runtime_status}，形态：{runtime.get('profile', 'unknown')}，"
                f"监听端口 {runtime.get('listening_count', 0)} / {len(runtime.get('ports') or [])}。"
            ),
            "启动服务或修正端口注册。"
            if runtime_status == "stopped"
            else "补端口注册，或明确标注项目为何需要常驻服务。"
            if runtime_status == "unobserved"
            else "保持运行形态说明和验证证据同步。"
            if runtime_status == "not_applicable"
            else "保持端口注册和运行状态同步。",
        ),
        _coverage_check(
            "verification",
            "ready"
            if verification_status == "verified"
            else "failed"
            if verification_status in {"failed", "unknown"}
            else "warning",
            (
                f"最近验证：{verification_status}，checks={verification.get('checks', 0)}。"
                + (f" 已登记命令：{verification.get('command')}。" if verification.get("command") else "")
            ),
            "复现失败验证并补 closeout 证据。"
            if verification_status == "failed"
            else "先补验证命令或构建清单，再建立可复制的验证入口。"
            if verification_status == "unknown"
            else "运行已登记验证命令，并通过 agent-workflow 留证。"
            if verification_status == "documented"
            else "保持验证证据新鲜。",
        ),
        _coverage_check(
            "source_refs",
            "failed" if not source_refs else "warning" if missing_sources else "ready",
            f"来源定位 {len(source_refs)} 个，缺失 {len(missing_sources)} 个。",
            "补齐注册表、端口表或项目指南的 source_ref。"
            if not source_refs or missing_sources
            else "保持来源定位可预览。",
        ),
        _coverage_check(
            "operator_actions",
            "ready" if actions else "failed",
            f"受控动作 {len(actions)} 个。",
            "至少提供打开入口、复制路径或复制验证命令。"
            if not actions
            else "继续保持动作只复制或站内导航，不直接执行。",
        ),
    ]


def _project_diagnostics(project: dict[str, Any]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    operational = project.get("operational", {})
    runtime = project.get("runtime", {})
    verification = runtime.get("latest_verification", {})

    if operational.get("status") != "ready":
        diagnostics.append(
            {
                "id": "operational-gap",
                "severity": "high" if operational.get("status") == "missing" else "medium",
                "title": "基础状态未就绪",
                "detail": " / ".join(operational.get("risks") or ["operational_status_not_ready"]),
                "next_action": operational.get("next_action") or "补齐项目文档、命令和 manifest。",
            }
        )
    if runtime.get("status") == "stopped":
        ports = ", ".join(f":{port['port']}" for port in runtime.get("ports", [])[:3]) or "registered port"
        diagnostics.append(
            {
                "id": "runtime-stopped",
                "severity": "medium",
                "title": "端口未监听",
                "detail": f"已登记运行端口但当前未监听：{ports}。",
                "next_action": "确认是否需要启动服务，或更新端口注册表状态。",
            }
        )
    if runtime.get("status") == "unobserved":
        diagnostics.append(
            {
                "id": "runtime-unobserved",
                "severity": "medium",
                "title": "缺少运行探针",
                "detail": runtime.get("probe_reason") or "项目未登记可观测端口，Cockpit 只能判断目录状态。",
                "next_action": "如该项目有常驻服务，补端口注册；否则补充无需常驻的依据。",
            }
        )
    if verification.get("status") == "failed":
        diagnostics.append(
            {
                "id": "verification-failed",
                "severity": "high",
                "title": "最近验证失败",
                "detail": f"最近验证事件失败，checks={verification.get('checks', 0)}。",
                "next_action": "优先复制验证命令复现，并把结果回写到 agent-workflow 证据。",
            }
        )
    elif verification.get("status") == "unknown":
        diagnostics.append(
            {
                "id": "verification-unknown",
                "severity": "high",
                "title": "缺少验证方案",
                "detail": "未找到最近 agent-workflow 验证事件，且当前没有可复制的验证命令。",
                "next_action": "先补验证命令或最小构建清单，再通过受控 workflow 留证。",
            }
        )
    elif verification.get("status") == "documented":
        diagnostics.append(
            {
                "id": "verification-documented",
                "severity": "low",
                "title": "可验证未留证",
                "detail": "项目已经登记验证命令，但最近还没有 workflow 验证证据。",
                "next_action": "择机运行已登记命令，并把结果补进 agent-workflow 证据。",
            }
        )
    if not diagnostics:
        diagnostics.append(
            {
                "id": "ready",
                "severity": "low",
                "title": "状态可日用",
                "detail": "基础状态、运行探针和最近验证未发现阻断项。",
                "next_action": "保持项目注册表、端口和验证证据同步。",
            }
        )
    return diagnostics


def _project_portfolio_state(project: dict[str, Any]) -> dict[str, Any]:
    checks = project.get("coverage_checks") or []
    ready = sum(1 for check in checks if check["status"] == "ready")
    warning = sum(1 for check in checks if check["status"] == "warning")
    failed = sum(1 for check in checks if check["status"] == "failed")
    score = round(((ready * 100) + (warning * 50)) / len(checks)) if checks else 0

    operational_status = project.get("operational", {}).get("status")
    runtime_status = project.get("runtime", {}).get("status")
    verification_status = project.get("runtime", {}).get("latest_verification", {}).get("status")
    workflow_active = int(project.get("workflow", {}).get("summary", {}).get("active") or 0)

    if operational_status == "missing" or verification_status == "failed" or failed >= 3:
        status = "blocked"
    elif failed > 0 or runtime_status in {"stopped", "unobserved"} or operational_status != "ready":
        status = "at_risk"
    elif warning > 0 or workflow_active:
        status = "watch"
    else:
        status = "healthy"

    non_ready_dimensions = [
        {
            "id": check["id"],
            "title": check["title"],
            "status": check["status"],
            "next_action": check["next_action"],
        }
        for check in checks
        if check["status"] != "ready"
    ]
    primary_diagnostic = (project.get("diagnostics") or [{}])[0]
    next_action = (
        primary_diagnostic.get("next_action")
        or project.get("operational", {}).get("next_action")
        or (non_ready_dimensions[0]["next_action"] if non_ready_dimensions else "保持项目状态同步。")
    )

    return {
        "score": score,
        "status": status,
        "ready": ready,
        "warning": warning,
        "failed": failed,
        "primary_gap": primary_diagnostic.get("title") or "状态可日用",
        "next_action": next_action,
        "non_ready_dimensions": non_ready_dimensions[:5],
    }


def _build_projects(
    registry: dict[str, Any], port_registry: dict[str, Any], registry_path: Path, port_registry_path: Path
) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    for project_id, project_data in (registry.get("projects") or {}).items():
        if not isinstance(project_data, dict):
            continue
        page_id = PROJECT_TO_PAGE.get(project_id, "SystemMap")
        project_path = WORKSPACE_ROOT / "projects" / project_id
        operational = _project_operational_status(project_id)
        runtime = _project_runtime_status(project_id, project_data, operational, port_registry, port_registry_path)
        project = {
            "id": project_id,
            "layer": project_data.get("layer", "unknown"),
            "stack": project_data.get("stack", "unknown"),
            "role": project_data.get("role", ""),
            "cockpit_page": page_id,
            "coverage": "native" if page_id != "SystemMap" or project_id.startswith("cockpit") else "orientation",
            "path": str(project_path),
            "exists": project_path.exists(),
            "operational": operational,
            "runtime": runtime,
            "workflow": _project_workflow_lifecycle(project_id),
            "source_refs": _project_source_refs(project_id, project_path, registry_path, runtime["ports"]),
            "actions": _project_actions(project_id, project_path, page_id, operational),
        }
        project["triage_commands"] = _project_triage_commands(project)
        project["coverage_checks"] = _project_coverage_checks(project)
        project["diagnostics"] = _project_diagnostics(project)
        project["portfolio"] = _project_portfolio_state(project)
        projects.append(project)
    return projects


def _build_domain_apps_summary() -> dict[str, Any]:
    try:
        from cockpit.web.api_domain_apps import build_domain_apps

        payload = build_domain_apps()
    except Exception:
        return {
            "status": "unavailable",
            "strategy": "Cockpit is the L3 entry; L4 domains keep SSOT and vertical app ownership.",
            "summary": {
                "total": 0,
                "ready": 0,
                "needs_attention": 0,
                "running": 0,
                "stopped": 0,
                "high_risk": 0,
                "external_mounts": 0,
                "security_passed": 0,
                "security_warn": 0,
                "security_failed": 1,
                "security_blocking": 1,
                "security_attention_apps": 1,
                "score": 0,
                "security_posture": "blocked",
            },
            "items": [],
            "attention_items": [
                {
                    "id": "domain-apps-api",
                    "name": "Domain Apps API",
                    "health": "unavailable",
                    "runtime_status": "unknown",
                    "risk_level": "high",
                    "security_posture": "blocked",
                    "next_action": "修复 /api/domain-apps 后再判断领域写入能力是否可挂载。",
                }
            ],
            "next_action": "修复 /api/domain-apps 后再判断领域写入能力是否可挂载。",
        }

    summary = payload.get("summary", {})
    items = []
    for item in payload.get("items", []):
        security_summary = item.get("security_summary", {})
        capabilities = item.get("capabilities", {})
        runtime = item.get("runtime", {})
        items.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "domain": item.get("domain"),
                "kind": item.get("kind"),
                "integration_mode": item.get("integration_mode"),
                "risk_level": item.get("risk_level"),
                "health": item.get("health"),
                "runtime_status": runtime.get("status", "unknown"),
                "launch_url": (item.get("links") or {}).get("launch_url"),
                "api_url": (item.get("links") or {}).get("api_url"),
                "security_posture": security_summary.get("posture", "unknown"),
                "security_attention": int(security_summary.get("attention") or 0),
                "security_failed": int(security_summary.get("failed") or 0),
                "read_capabilities": capabilities.get("read", []),
                "write_capabilities": capabilities.get("write", []),
                "action_count": len(item.get("actions") or []),
                "next_action": _domain_app_next_action(item),
            }
        )

    total = int(summary.get("total") or 0)
    ready = int(summary.get("ready") or 0)
    running = int(summary.get("running") or 0)
    attention_apps = int(summary.get("security_attention_apps") or 0)
    failed = int(summary.get("security_failed") or 0)
    warn = int(summary.get("security_warn") or 0)
    health_score = (ready / total) * 40 if total else 0
    runtime_score = (running / total) * 20 if total else 0
    security_score = ((total - attention_apps) / total) * 30 if total else 0
    mount_score = 10 if total else 0
    score = round(health_score + runtime_score + security_score + mount_score)
    status = "blocked" if failed else "attention" if warn or attention_apps else "watch" if running < total else "ready"
    attention_items = [
        item
        for item in items
        if item["health"] != "ready" or item["runtime_status"] == "stopped" or item["security_posture"] != "passed"
    ]
    enriched_summary = {
        **summary,
        "score": score,
        "security_posture": "blocked" if failed else "attention" if warn or attention_apps else "passed",
    }
    next_action = "保持领域应用健康、安全门和启动命令新鲜。"
    if status == "blocked":
        next_action = "先修复领域应用安全失败项，再开放写入或反向代理能力。"
    elif status == "attention":
        next_action = "处理领域应用安全警告和健康提醒，避免 Cockpit 挂载不可信能力。"
    elif status == "watch":
        next_action = "启动或验证停止的领域服务，让应用中心从入口变成日用能力。"

    return {
        "status": status,
        "strategy": payload.get("strategy", ""),
        "summary": enriched_summary,
        "items": items,
        "attention_items": attention_items[:5],
        "next_action": next_action,
    }


def _domain_app_next_action(item: dict[str, Any]) -> str:
    security_summary = item.get("security_summary", {})
    if int(security_summary.get("failed") or 0):
        return "修复失败的安全检查后再开放写入或自动化动作。"
    if int(security_summary.get("warn") or 0):
        return "清理安全警告，让领域应用进入可挂载状态。"
    if item.get("health") != "ready":
        return "补齐应用根、SSOT 或构建数据，让健康状态回到 ready。"
    if (item.get("runtime") or {}).get("status") == "stopped":
        return "按登记启动命令拉起服务或确认它只需要按需启动。"
    return "保持 SSOT、验证命令和安全门证据新鲜。"


def _domain_app_security_gap(domain_apps: dict[str, Any]) -> dict[str, str] | None:
    summary = domain_apps.get("summary", {})
    failed = int(summary.get("security_failed") or 0)
    warn = int(summary.get("security_warn") or 0)
    if domain_apps.get("status") == "unavailable":
        return {
            "id": "domain-app-write-gates",
            "severity": "medium",
            "title": "领域应用安全门状态不可读",
            "evidence": "SystemMap 无法读取 DomainApps 安全矩阵。",
            "next": "修复 /api/domain-apps 后再判断领域写入能力是否可挂载。",
        }
    if failed == 0 and warn == 0:
        return None

    attention_apps = [item["id"] for item in domain_apps.get("items", []) if item.get("security_posture") != "passed"]
    return {
        "id": "domain-app-write-gates",
        "severity": "high" if failed else "medium",
        "title": "领域应用写入能力仍需安全门",
        "evidence": f"应用中心安全矩阵仍有 {failed} 个失败、{warn} 个警告：{', '.join(attention_apps)}。",
        "next": "在 DomainApps 消除 warn/fail 项后，再考虑写回、反向代理或自动执行动作。",
    }


def _project_focus_queue(
    projects: list[dict[str, Any]],
    queue_id: str,
    title: str,
    severity: str,
    reason: str,
    matcher: Any,
) -> dict[str, Any]:
    matched = [project for project in projects if matcher(project)]
    return {
        "id": queue_id,
        "title": title,
        "severity": severity,
        "reason": reason,
        "count": len(matched),
        "project_ids": [project["id"] for project in matched],
        "top_projects": [
            {
                "id": project["id"],
                "diagnostics": project.get("diagnostics", [])[:2],
            }
            for project in matched[:4]
        ],
    }


def _build_project_focus(projects: list[dict[str, Any]]) -> dict[str, Any]:
    queues = [
        _project_focus_queue(
            projects,
            "needs-action",
            "需要动作",
            "high",
            "项目不是 ready、需要常驻但未监听/未登记，或验证失败/暂无验证。",
            lambda project: (
                project.get("operational", {}).get("status") != "ready"
                or project.get("runtime", {}).get("status") in {"stopped", "unobserved"}
                or project.get("runtime", {}).get("latest_verification", {}).get("status") in {"failed", "unknown"}
            ),
        ),
        _project_focus_queue(
            projects,
            "operational-gap",
            "目录/文档缺口",
            "medium",
            "项目目录、文档、manifest 或命令登记仍未补齐。",
            lambda project: project.get("operational", {}).get("status") != "ready",
        ),
        _project_focus_queue(
            projects,
            "runtime-gap",
            "运行未就绪",
            "medium",
            "项目需要常驻服务，但端口未监听或尚未登记可观测端口。",
            lambda project: project.get("runtime", {}).get("status") in {"stopped", "unobserved"},
        ),
        _project_focus_queue(
            projects,
            "verification-gap",
            "验证待补证",
            "medium",
            "最近验证失败，或当前连可复制验证方案都还没有。",
            lambda project: (
                project.get("runtime", {}).get("latest_verification", {}).get("status") in {"failed", "unknown"}
            ),
        ),
        _project_focus_queue(
            projects,
            "verification-ready",
            "可验证未留证",
            "low",
            "项目已经登记验证命令，但还缺最近一次 workflow 证据。",
            lambda project: project.get("runtime", {}).get("latest_verification", {}).get("status") == "documented",
        ),
        _project_focus_queue(
            projects,
            "ready-and-running",
            "可日用项目",
            "low",
            "目录状态 ready，且运行中或已明确无需常驻服务。",
            lambda project: (
                project.get("operational", {}).get("status") == "ready"
                and project.get("runtime", {}).get("status") in {"running", "not_applicable"}
                and project.get("runtime", {}).get("latest_verification", {}).get("status")
                in {"verified", "documented"}
            ),
        ),
    ]
    queue_lookup = {queue["id"]: queue for queue in queues}
    return {
        "queues": queues,
        "summary": {
            "needs_action": queue_lookup["needs-action"]["count"],
            "operational_gap": queue_lookup["operational-gap"]["count"],
            "runtime_gap": queue_lookup["runtime-gap"]["count"],
            "verification_gap": queue_lookup["verification-gap"]["count"],
            "verification_ready": queue_lookup["verification-ready"]["count"],
            "ready_and_running": queue_lookup["ready-and-running"]["count"],
        },
    }


def _project_triage_queue(
    projects: list[dict[str, Any]],
    queue_id: str,
    title: str,
    severity: str,
    reason: str,
    category: str,
) -> dict[str, Any]:
    commands = [
        command
        for project in projects
        for command in project.get("triage_commands", [])
        if command.get("category") == category
    ]
    return {
        "id": queue_id,
        "title": title,
        "severity": severity,
        "reason": reason,
        "count": len(commands),
        "project_ids": sorted({command["project_id"] for command in commands}),
        "commands": commands[:8],
    }


def _build_project_triage(projects: list[dict[str, Any]]) -> dict[str, Any]:
    queues = [
        _project_triage_queue(
            projects,
            "runtime",
            "运行排查",
            "medium",
            "端口未监听、缺少端口登记或需要人工启动确认的项目。",
            "runtime",
        ),
        _project_triage_queue(
            projects,
            "verification",
            "验证排查",
            "high",
            "最近验证失败，或当前缺少可复制验证方案的项目。",
            "verification",
        ),
        _project_triage_queue(
            projects,
            "coverage",
            "清单排查",
            "medium",
            "项目文档、命令或 manifest 不完整的项目。",
            "coverage",
        ),
    ]
    return {
        "queues": queues,
        "summary": {
            "total_commands": sum(queue["count"] for queue in queues),
            "runtime_commands": queues[0]["count"],
            "verification_commands": queues[1]["count"],
            "coverage_commands": queues[2]["count"],
        },
    }


def _build_project_capability_coverage(projects: list[dict[str, Any]]) -> dict[str, Any]:
    total_projects = len(projects)
    dimension_summary: list[dict[str, Any]] = []

    for dimension in PROJECT_COVERAGE_DIMENSIONS:
        checks = [
            (project, next(check for check in project.get("coverage_checks", []) if check["id"] == dimension["id"]))
            for project in projects
        ]
        ready = sum(1 for _, check in checks if check["status"] == "ready")
        warning = sum(1 for _, check in checks if check["status"] == "warning")
        failed = sum(1 for _, check in checks if check["status"] == "failed")
        score = round((ready / total_projects) * 100) if total_projects else 0
        status = "ready" if warning == 0 and failed == 0 else "warning" if failed == 0 else "failed"
        attention_projects = [
            {
                "id": project["id"],
                "status": check["status"],
                "next_action": check["next_action"],
            }
            for project, check in checks
            if check["status"] != "ready"
        ][:4]

        dimension_summary.append(
            {
                "id": dimension["id"],
                "title": dimension["title"],
                "description": dimension["description"],
                "status": status,
                "ready": ready,
                "warning": warning,
                "failed": failed,
                "score": score,
                "attention_projects": attention_projects,
            }
        )

    total_cells = total_projects * len(PROJECT_COVERAGE_DIMENSIONS)
    ready_cells = sum(
        1 for project in projects for check in project.get("coverage_checks", []) if check["status"] == "ready"
    )
    warning_cells = sum(
        1 for project in projects for check in project.get("coverage_checks", []) if check["status"] == "warning"
    )
    failed_cells = sum(
        1 for project in projects for check in project.get("coverage_checks", []) if check["status"] == "failed"
    )

    weakest_dimensions = sorted(
        dimension_summary,
        key=lambda item: (item["score"], -item["failed"], -item["warning"], item["title"]),
    )[:3]

    return {
        "dimensions": list(PROJECT_COVERAGE_DIMENSIONS),
        "dimension_summary": dimension_summary,
        "weakest_dimensions": weakest_dimensions,
        "matrix": [
            {
                "project_id": project["id"],
                "layer": project["layer"],
                "cockpit_page": project["cockpit_page"],
                "ready": sum(1 for check in project.get("coverage_checks", []) if check["status"] == "ready"),
                "warning": sum(1 for check in project.get("coverage_checks", []) if check["status"] == "warning"),
                "failed": sum(1 for check in project.get("coverage_checks", []) if check["status"] == "failed"),
                "checks": project.get("coverage_checks", []),
            }
            for project in projects
        ],
        "summary": {
            "projects": total_projects,
            "dimensions": len(PROJECT_COVERAGE_DIMENSIONS),
            "total_cells": total_cells,
            "ready_cells": ready_cells,
            "warning_cells": warning_cells,
            "failed_cells": failed_cells,
            "score": round((ready_cells / total_cells) * 100) if total_cells else 0,
        },
    }


def _build_project_portfolio(
    projects: list[dict[str, Any]], project_capability_coverage: dict[str, Any]
) -> dict[str, Any]:
    bucket_defs = (
        ("blocked", "阻塞项目", "high", "验证失败、目录缺失或多个能力维度失败，需要优先处理。"),
        ("at_risk", "风险项目", "medium", "运行、文档、命令或探针存在缺口，影响稳定日用。"),
        ("watch", "观察项目", "medium", "存在提醒项或活跃工作流，短期需要跟进。"),
        ("healthy", "健康项目", "low", "核心覆盖维度已经就绪，保持证据新鲜即可。"),
    )
    buckets = []
    for bucket_id, title, severity, reason in bucket_defs:
        matched = [project for project in projects if project.get("portfolio", {}).get("status") == bucket_id]
        buckets.append(
            {
                "id": bucket_id,
                "title": title,
                "severity": severity,
                "reason": reason,
                "count": len(matched),
                "project_ids": [project["id"] for project in matched],
            }
        )

    status_rank = {"blocked": 0, "at_risk": 1, "watch": 2, "healthy": 3}
    priority_source = sorted(
        projects,
        key=lambda project: (
            status_rank.get(project.get("portfolio", {}).get("status"), 9),
            project.get("portfolio", {}).get("score", 0),
            -project.get("portfolio", {}).get("failed", 0),
            -project.get("portfolio", {}).get("warning", 0),
            project["id"],
        ),
    )
    priority_projects = [
        {
            "id": project["id"],
            "layer": project["layer"],
            "cockpit_page": project["cockpit_page"],
            "score": project.get("portfolio", {}).get("score", 0),
            "status": project.get("portfolio", {}).get("status", "unknown"),
            "primary_gap": project.get("portfolio", {}).get("primary_gap", ""),
            "next_action": project.get("portfolio", {}).get("next_action", ""),
            "failed": project.get("portfolio", {}).get("failed", 0),
            "warning": project.get("portfolio", {}).get("warning", 0),
            "runtime_status": project.get("runtime", {}).get("status", "unknown"),
            "verification_status": project.get("runtime", {}).get("latest_verification", {}).get("status", "unknown"),
            "non_ready_dimensions": project.get("portfolio", {}).get("non_ready_dimensions", []),
            "triage_commands": len(project.get("triage_commands") or []),
        }
        for project in priority_source
        if project.get("portfolio", {}).get("status") != "healthy"
    ][:8]

    if not priority_projects:
        priority_projects = [
            {
                "id": project["id"],
                "layer": project["layer"],
                "cockpit_page": project["cockpit_page"],
                "score": project.get("portfolio", {}).get("score", 0),
                "status": project.get("portfolio", {}).get("status", "healthy"),
                "primary_gap": project.get("portfolio", {}).get("primary_gap", "状态可日用"),
                "next_action": project.get("portfolio", {}).get("next_action", "保持项目状态同步。"),
                "failed": 0,
                "warning": project.get("portfolio", {}).get("warning", 0),
                "runtime_status": project.get("runtime", {}).get("status", "unknown"),
                "verification_status": project.get("runtime", {})
                .get("latest_verification", {})
                .get("status", "unknown"),
                "non_ready_dimensions": project.get("portfolio", {}).get("non_ready_dimensions", []),
                "triage_commands": len(project.get("triage_commands") or []),
            }
            for project in priority_source[:4]
        ]

    blocked = next(bucket for bucket in buckets if bucket["id"] == "blocked")
    at_risk = next(bucket for bucket in buckets if bucket["id"] == "at_risk")
    watch = next(bucket for bucket in buckets if bucket["id"] == "watch")
    score = project_capability_coverage.get("summary", {}).get("score", 0)
    posture = (
        "blocked" if blocked["count"] else "at_risk" if at_risk["count"] else "watch" if watch["count"] else "healthy"
    )

    return {
        "summary": {
            "score": score,
            "status": posture,
            "projects": len(projects),
            "blocked": blocked["count"],
            "at_risk": at_risk["count"],
            "watch": watch["count"],
            "healthy": next(bucket for bucket in buckets if bucket["id"] == "healthy")["count"],
            "priority_projects": len(priority_projects),
            "weakest_dimensions": len(project_capability_coverage.get("weakest_dimensions") or []),
        },
        "buckets": buckets,
        "priority_projects": priority_projects,
        "weakest_dimensions": project_capability_coverage.get("weakest_dimensions") or [],
    }


def _build_gap_list(
    projects: list[dict[str, Any]],
    feature_domains: list[dict[str, Any]],
    domain_apps: dict[str, Any],
) -> list[dict[str, str]]:
    orientation_only = [project["id"] for project in projects if project["coverage"] == "orientation"]
    operational_gaps = [
        project["id"] for project in projects if project.get("operational", {}).get("status") != "ready"
    ]
    gaps = []
    domain_gap = _domain_app_security_gap(domain_apps)
    if domain_gap:
        gaps.append(domain_gap)
    if orientation_only or operational_gaps:
        gaps.append(
            {
                "id": "project-native-surface",
                "severity": "medium",
                "title": "部分项目仍需补齐状态面",
                "evidence": ", ".join(sorted(set(orientation_only + operational_gaps))),
                "next": "优先补齐高频项目的文档、命令、构建清单和运行探针。",
            }
        )
    if not feature_domains:
        gaps.append(
            {
                "id": "capability-map-unavailable",
                "severity": "high",
                "title": "能力地图不可读",
                "evidence": "docs/FUNCTIONAL-CAPABILITY-MAP.md 未能解析出能力域。",
                "next": "修复能力地图格式或提供机器可读 registry。",
            }
        )
    return gaps


def _build_roadmap() -> dict[str, Any]:
    lane_labels = {
        "now": "现在补",
        "next": "下一步",
        "later": "后续增强",
    }
    lanes = []
    items = [
        {
            **item,
            "source_refs": [_source_ref_for_id(SYSTEM_MAP_SOURCE, item["id"], "路线图定义", "system_map_api")],
        }
        for item in ROADMAP_ITEMS
    ]
    for lane_id, label in lane_labels.items():
        lane_items = [item for item in items if item["stage"] == lane_id]
        lanes.append({"id": lane_id, "title": label, "items": lane_items})
    return {
        "items": items,
        "lanes": lanes,
        "summary": {
            "total": len(items),
            "shipped": sum(1 for item in items if item["status"] == "shipped"),
            "planned": sum(1 for item in items if item["status"] != "shipped"),
            "p0": sum(1 for item in items if item["priority"] == "P0"),
        },
    }


def _build_playbooks(page_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    playbooks: list[dict[str, Any]] = []
    for playbook in OPERATING_PLAYBOOKS:
        steps = []
        for step in playbook["steps"]:
            page = page_lookup.get(step["page_id"])
            if not page:
                continue
            steps.append({**step, "page": page})
        playbooks.append(
            {
                **playbook,
                "steps": steps,
                "source_refs": [
                    _source_ref_for_id(SYSTEM_MAP_SOURCE, playbook["id"], "操作清单定义", "system_map_api")
                ],
            }
        )
    return playbooks


def _build_usage_paths(page_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **path,
            "pages": [page_lookup[step] for step in path["steps"] if step in page_lookup],
            "source_refs": [_source_ref_for_id(SYSTEM_MAP_SOURCE, path["id"], "使用路径定义", "system_map_api")],
        }
        for path in USAGE_PATHS
    ]


def _page_maturity_next_action(
    projects: list[dict[str, Any]],
    domains: list[dict[str, Any]],
    usage_paths: list[dict[str, Any]],
    playbook_steps: list[dict[str, Any]],
    roadmap_items: list[dict[str, Any]],
    actions: int,
) -> str:
    if not usage_paths:
        return "把页面接入至少一条使用路径。"
    if not playbook_steps:
        return "补一条操作清单步骤，让页面进入日常流程。"
    if not domains:
        return "补功能域映射，说明页面承载的能力。"
    if not projects:
        return "补项目或服务映射，避免页面只有入口没有对象。"
    if not actions:
        return "补受控动作或排查命令，让页面能推进问题。"
    if not roadmap_items:
        return "补路线图或验收项，让页面演进可追踪。"
    return "保持页面、项目、清单和路线图证据新鲜。"


def _build_page_maturity(
    projects: list[dict[str, Any]],
    feature_domains: list[dict[str, Any]],
    usage_paths: list[dict[str, Any]],
    playbooks: list[dict[str, Any]],
    roadmap: dict[str, Any],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    roadmap_items = roadmap.get("items") or []
    for page in COCKPIT_PAGES:
        page_id = page["id"]
        page_projects = [project for project in projects if project.get("cockpit_page") == page_id]
        page_domains = [domain for domain in feature_domains if domain.get("cockpit_page") == page_id]
        page_usage_paths = [
            path for path in usage_paths if any(path_page.get("id") == page_id for path_page in path.get("pages") or [])
        ]
        page_playbook_steps = [
            step
            for playbook in playbooks
            for step in playbook.get("steps") or []
            if step.get("page_id") == page_id or (step.get("page") or {}).get("id") == page_id
        ]
        page_roadmap_items = [item for item in roadmap_items if item.get("cockpit_page") == page_id]
        project_action_count = sum(
            len(project.get("actions") or []) + len(project.get("triage_commands") or []) for project in page_projects
        )
        page_action_ids = list(PAGE_OPERATOR_ACTIONS.get(page_id, ()))
        action_count = project_action_count + len(page_action_ids)
        score = (
            (25 if page_projects else 0)
            + (20 if page_domains else 0)
            + (20 if page_usage_paths else 0)
            + (15 if page_playbook_steps else 0)
            + (10 if page_roadmap_items else 0)
            + (10 if action_count else 0)
        )
        status = "ready" if score >= 70 else "watch" if score >= 40 else "gap"
        items.append(
            {
                "page": page,
                "page_id": page_id,
                "score": score,
                "status": status,
                "projects": [project.get("id") for project in page_projects],
                "domains": [domain.get("id") for domain in page_domains],
                "usage_paths": [path.get("id") for path in page_usage_paths],
                "playbook_steps": [step.get("id") for step in page_playbook_steps],
                "roadmap_items": [item.get("id") for item in page_roadmap_items],
                "actions": action_count,
                "operator_actions": page_action_ids,
                "next_action": _page_maturity_next_action(
                    page_projects,
                    page_domains,
                    page_usage_paths,
                    page_playbook_steps,
                    page_roadmap_items,
                    action_count,
                ),
            }
        )

    return {
        "items": items,
        "attention_items": [
            item for item in sorted(items, key=lambda row: (row["score"], row["page_id"])) if item["status"] != "ready"
        ][:8],
        "summary": {
            "total": len(items),
            "ready": sum(1 for item in items if item["status"] == "ready"),
            "watch": sum(1 for item in items if item["status"] == "watch"),
            "gap": sum(1 for item in items if item["status"] == "gap"),
            "score": round(sum(item["score"] for item in items) / len(items)) if items else 0,
        },
    }


def _count_source_refs(*collections: list[dict[str, Any]]) -> int:
    total = 0
    for collection in collections:
        for item in collection:
            total += len(item.get("source_refs") or [])
            for port in item.get("runtime", {}).get("ports", []):
                if port.get("source_ref"):
                    total += 1
    return total


def _count_project_actions(projects: list[dict[str, Any]]) -> int:
    return sum(len(project.get("actions") or []) for project in projects)


def build_system_map() -> dict[str, Any]:
    registry_path = WORKSPACE_ROOT / "docs" / "project-registry.yaml"
    capability_map_path = WORKSPACE_ROOT / "docs" / "FUNCTIONAL-CAPABILITY-MAP.md"
    port_registry_path = WORKSPACE_ROOT / "protocols" / "port-registry.yaml"
    registry = _read_yaml(registry_path)
    port_registry = _read_yaml(port_registry_path)
    projects = _build_projects(registry, port_registry, registry_path, port_registry_path)
    project_focus = _build_project_focus(projects)
    project_triage = _build_project_triage(projects)
    project_capability_coverage = _build_project_capability_coverage(projects)
    project_portfolio = _build_project_portfolio(projects, project_capability_coverage)
    domain_apps = _build_domain_apps_summary()
    feature_domains = _parse_capability_domains(capability_map_path)
    layers = _build_layers(registry, projects, registry_path)
    page_lookup = {page["id"]: page for page in COCKPIT_PAGES}
    gaps = _build_gap_list(projects, feature_domains, domain_apps)
    roadmap = _build_roadmap()
    playbooks = _build_playbooks(page_lookup)
    usage_paths = _build_usage_paths(page_lookup)
    page_maturity = _build_page_maturity(projects, feature_domains, usage_paths, playbooks, roadmap)

    return {
        "schema_version": "v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "architecture": {
            "model": (registry.get("workspace") or {}).get("architecture", "5+4+1+1"),
            "ecos_version": (registry.get("workspace") or {}).get("ecos_version", "v6"),
            "dependency_direction": "entry surfaces -> routing mesh -> engines/runtime/protocol -> governed state and evidence",
        },
        "source_paths": {
            "project_registry": _path_state(registry_path),
            "architecture": _path_state(WORKSPACE_ROOT / "ARCHITECTURE.md"),
            "functional_capability_map": _path_state(capability_map_path),
            "layer_index": _path_state(WORKSPACE_ROOT / "docs" / "generated" / "project-layer-index.md"),
            "port_registry": _path_state(port_registry_path),
            "bos_services": _path_state(WORKSPACE_ROOT / "projects" / "agora" / "etc" / "bos-services.yaml"),
        },
        "cockpit_pages": list(COCKPIT_PAGES),
        "layers": layers,
        "projects": projects,
        "project_focus": project_focus,
        "project_triage": project_triage,
        "project_capability_coverage": project_capability_coverage,
        "project_portfolio": project_portfolio,
        "domain_apps": domain_apps,
        "feature_domains": feature_domains,
        "roadmap": roadmap,
        "playbooks": playbooks,
        "usage_paths": usage_paths,
        "page_maturity": page_maturity,
        "gaps": gaps,
        "summary": {
            "projects": len(projects),
            "layers": len(layers),
            "feature_domains": len(feature_domains),
            "cockpit_pages": len(COCKPIT_PAGES),
            "native_project_surfaces": sum(1 for project in projects if project["coverage"] == "native"),
            "orientation_project_surfaces": sum(1 for project in projects if project["coverage"] != "native"),
            "ready_projects": sum(1 for project in projects if project["operational"]["status"] == "ready"),
            "partial_projects": sum(1 for project in projects if project["operational"]["status"] == "partial"),
            "missing_projects": sum(1 for project in projects if project["operational"]["status"] == "missing"),
            "running_projects": sum(1 for project in projects if project["runtime"]["status"] == "running"),
            "stopped_projects": sum(1 for project in projects if project["runtime"]["status"] == "stopped"),
            "unobserved_projects": sum(1 for project in projects if project["runtime"]["status"] == "unobserved"),
            "not_applicable_projects": sum(
                1 for project in projects if project["runtime"]["status"] == "not_applicable"
            ),
            "gaps": len(gaps),
            "roadmap_items": roadmap["summary"]["total"],
            "playbooks": len(playbooks),
            "project_actions": _count_project_actions(projects),
            "projects_needing_action": project_focus["summary"]["needs_action"],
            "project_triage_commands": project_triage["summary"]["total_commands"],
            "project_coverage_score": project_capability_coverage["summary"]["score"],
            "project_portfolio_score": project_portfolio["summary"]["score"],
            "blocked_projects": project_portfolio["summary"]["blocked"],
            "at_risk_projects": project_portfolio["summary"]["at_risk"],
            "domain_apps": domain_apps["summary"]["total"],
            "domain_app_score": domain_apps["summary"]["score"],
            "domain_app_security_attention": domain_apps["summary"]["security_attention_apps"],
            "page_maturity_score": page_maturity["summary"]["score"],
            "page_maturity_ready": page_maturity["summary"]["ready"],
            "page_maturity_watch": page_maturity["summary"]["watch"],
            "page_maturity_gap": page_maturity["summary"]["gap"],
            "source_refs": _count_source_refs(
                projects,
                layers,
                feature_domains,
                roadmap["items"],
                playbooks,
                usage_paths,
            ),
        },
    }


@router.get("/api/cockpit/system-map")
async def get_system_map() -> dict[str, Any]:
    return build_system_map()


@router.get("/api/cockpit/source-ref")
async def get_source_ref_preview(
    target: str | None = Query(default=None, description="Source ref target, usually absolute path:line"),
    path: str | None = Query(default=None, description="Source file path when target is not provided"),
    line: int | None = Query(default=None, ge=1, description="Optional 1-based source line"),
    context: int = Query(default=4, ge=0, le=20, description="Number of surrounding lines to include"),
) -> dict[str, Any]:
    return build_source_ref_preview(target=target, path=path, line=line, context=context)
