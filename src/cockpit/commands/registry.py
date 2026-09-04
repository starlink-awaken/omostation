"""
cockpit.commands.registry — SSOT 命令元数据目录

设计原则:
  · 唯一数据源 (Single Source of Truth)，所有消费方（TUI 面板、cockpit help、
    自动补全）均从此读取，零重复定义
  · CommandMeta 是纯数据类，不引入任何运行时依赖
  · 按类别分组，便于 CommandPalette 过滤与展示

用法:
  from cockpit.commands.registry import COMMAND_CATALOG, CommandMeta
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommandMeta:
    """命令元数据（不可变）."""

    name: str
    summary: str
    category: str = "🔧 通用 (General)"
    aliases: tuple[str, ...] = field(default_factory=tuple)
    # ── 治理字段 (Phase A2, 全部带默认值, 存量条目零改动) ──
    example: str = ""  # help_map 产品地图示例
    owner: str = "cockpit"
    maturity: str = "stable"  # stable | beta | experimental | deprecated
    risk: str = "low"  # low | medium | high
    delegated_target: str | None = None  # 委派目标, 如 "bin/gac/gac-drift.py"
    chain_enabled: bool = True  # 是否允许进入 chain 编排 (high-risk 默认 False)
    audit_ref: str | None = None  # 指向 docs/command-audit/<path>.yaml


def submodule_count() -> str:
    """主仓注册的子模块数（动态读取 .gitmodules，避免硬编码漂移）。

    向上定位主仓根（含 docs/project-registry.yaml），统计 `[submodule "path"]`
    条目数。非主仓环境或读取失败时返回空串，调用方应优雅降级
    （help/summary 不显示数字，而不是展示过期计数）。
    """
    from pathlib import Path

    cur = Path(__file__).resolve()
    for parent in cur.parents:
        if (parent / "docs" / "project-registry.yaml").is_file():
            gm = parent / ".gitmodules"
            try:
                return str(
                    sum(
                        1
                        for ln in gm.read_text(encoding="utf-8").splitlines()
                        if ln.strip().startswith("[submodule")
                    )
                )
            except OSError:
                return ""
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# CATEGORY_GROUPS: category → (展示顺序, 颜色)。help_map 产品地图分组的唯一顺序来源。
# ──────────────────────────────────────────────────────────────────────────────

CATEGORY_GROUPS: dict[str, tuple[int, str]] = {
    "🚀 入门 (Onboarding)": (10, "bright_green"),
    "📚 研究 (Research)": (20, "cyan"),
    "🧠 知识引擎 (BOS)": (30, "bright_cyan"),
    "📋 项目 (Project)": (40, "yellow"),
    "🤖 Agent 协作": (50, "bright_magenta"),
    "🛡️ 治理工具 (Governance Tools)": (60, "bright_yellow"),
    "🏛️ 治理 (Governance)": (61, "yellow"),
    "🧹 代码质量 (Code Quality)": (70, "green"),
    "🖥️ 基础设施 (Infra)": (80, "bright_blue"),
    "📡 通讯 (Messaging)": (90, "blue"),
    "🔌 项目 CLI (Project CLIs)": (100, "bright_blue"),
    "🧰 工具集 (Utilities)": (110, "white"),
    "📦 数据 (Data)": (120, "white"),
    "🛠️ 系统 (System)": (130, "blue"),
    "👤 用户 (User)": (140, "magenta"),
    "📄 专项工具 (Domain)": (150, "white"),
    "🔌 总线接入 (ECCP)": (160, "bright_blue"),
    "🔧 通用 (General)": (900, "white"),
}

# ──────────────────────────────────────────────────────────────────────────────
# 8 大正交一级领域 (Orthogonal Domains) 与向后兼容映射
# ──────────────────────────────────────────────────────────────────────────────

ORTHOGONAL_DOMAINS: dict[str, str] = {
    "governance": "🏛️ 架构与治理 (Governance, Contracts, GAC, Audits)",
    "workflow": "📋 智能体与交付 (Workflows, Agent Lifecycle, Residents, BCOS)",
    "memory": "🧠 记忆与认知 (Memory OS, Knowledge Graph, Search, Brain)",
    "compute": "⚡️ 算力与推理 (Compute Fabric, Models, VRAM, Mesh)",
    "bus": "🌐 总线与通信 (Omni-Bus, Agora, BOS Services, Events)",
    "scene": "🗺️ 业务场景 (Scenario Cards, Journeys, Gongwen, Brief)",
    "system": "🖥️ 系统与运维 (System Health, Dashboard, Runtime Sandbox)",
    "user": "👤 体验与向导 (Quickstart, Help, Onboarding, TUI)",
}

LEGACY_COMMAND_MAPPING: dict[str, tuple[str, str]] = {
    # 治理域
    "gac": ("governance", "gac"),
    "audit": ("governance", "audit"),
    "debt": ("governance", "debt"),
    "contracts": ("governance", "contracts"),
    "policy": ("governance", "policy"),
    "watchdog": ("governance", "watchdog"),
    "kems": ("governance", "kems"),
    # 工作流域
    "agent": ("workflow", "agent"),
    "agent-workflow": ("workflow", "workflow"),
    "bcos": ("workflow", "bcos"),
    "resident": ("workflow", "resident"),
    "iterate": ("workflow", "iterate"),
    # 记忆域
    "memory": ("memory", "memory"),
    "knowledge": ("memory", "knowledge"),
    "vault": ("memory", "vault"),
    "search": ("memory", "search"),
    "brain": ("memory", "brain"),
    "gbrain": ("memory", "gbrain"),
    "kairon": ("memory", "kairon"),
    # 算力域
    "fabric": ("compute", "fabric"),
    "mesh": ("compute", "mesh"),
    "warm": ("compute", "warm"),
    "vram": ("compute", "vram"),
    "triage": ("compute", "triage"),
    # 总线域
    "agora": ("bus", "agora"),
    "bos": ("bus", "bos"),
    "bus": ("bus", "bus"),
    "events": ("bus", "events"),
    "capability": ("bus", "capability"),
    # 场景域
    "scenario": ("scene", "scenario"),
    "journey": ("scene", "journey"),
    "gongwen": ("scene", "gongwen"),
    "brief": ("scene", "brief"),
    "family-hub": ("scene", "family-hub"),
    # 系统域
    "status": ("system", "status"),
    "health": ("system", "health"),
    "dashboard": ("system", "dashboard"),
    "readiness": ("system", "readiness"),
    "runtime": ("system", "runtime"),
    "telemetry": ("system", "telemetry"),
    # 用户体验域
    "quickstart": ("user", "quickstart"),
    "help": ("user", "help"),
    "demo": ("user", "demo"),
    "completion": ("user", "completion"),
    "docs": ("user", "docs"),
}



# ──────────────────────────────────────────────────────────────────────────────
# COMMAND_CATALOG: 所有 cockpit 子命令的权威元数据
# 顺序: 按类别 → 字母排序，方便 Code Review 与扩展
# ──────────────────────────────────────────────────────────────────────────────

COMMAND_CATALOG: dict[str, CommandMeta] = {
    # ── 研究工作台 (Research Workbench) ──────────────────────────────────────
    "research": CommandMeta(
        name="research",
        category="📚 研究 (Research)",
        summary="深度研究工作台 (ask / publish / list / audit / …)",
    ),
    "search": CommandMeta(
        name="search",
        category="📚 研究 (Research)",
        summary="跨源搜索 (数据库 + BOS 知识引擎)",
    ),
    "knowledge": CommandMeta(
        name="knowledge",
        category="📚 研究 (Research)",
        summary="本地知识库管理 (import / query / stats)",
    ),
    "memory": CommandMeta(
        name="memory",
        category="📚 研究 (Research)",
        summary="Memory OS 统一控制面 (status/recall/write/forget → bos://memory/mos/*)",
        aliases=("mos",),
    ),
    "daily": CommandMeta(
        name="daily",
        category="📚 研究 (Research)",
        summary="每日研究简报 (生成 + 推送)",
    ),
    "brief": CommandMeta(
        name="brief",
        category="📚 研究 (Research)",
        summary="会话简报 (生成摘要)",
    ),
    "discover": CommandMeta(
        name="discover",
        category="📚 研究 (Research)",
        summary="发现可用功能和资源",
    ),
    # ── 项目管理 (Project Management) ────────────────────────────────────────
    "iterate": CommandMeta(
        name="iterate",
        category="📋 项目 (Project)",
        summary="迭代管理 (sprint / backlog / roadmap)",
    ),
    "scenario": CommandMeta(
        name="scenario",
        category="📋 项目 (Project)",
        summary="统一 scenario 入口 (radar / assistant / health)",
    ),
    "wave2": CommandMeta(
        name="wave2",
        category="📋 项目 (Project)",
        summary="Wave2 项目战略视图",
    ),
    "workflow": CommandMeta(
        name="workflow",
        category="📋 项目 (Project)",
        summary="工作流管理 (run / list / status)",
    ),
    "agent-workflow": CommandMeta(
        name="agent-workflow",
        category="📋 项目 (Project)",
        summary="Agent 工作流编排",
        aliases=("agent",),
    ),
    "agent": CommandMeta(
        name="agent",
        category="📋 项目 (Project)",
        summary="Agent 工作流编排（agent-workflow 别名）",
    ),
    "events-watch": CommandMeta(
        name="events-watch",
        category="📡 通讯 (Messaging)",
        summary="监听 BOS Inbox 紧急待办与提醒快照",
    ),
    "quickstart-check": CommandMeta(
        name="quickstart-check",
        category="👤 用户 (User)",
        summary="快速检查新用户环境核验状态",
    ),
    "agent-onboard": CommandMeta(
        name="agent-onboard",
        category="🤖 Agent 协作",
        summary="新 Agent 入职 checklist + 环境初始化",
    ),
    "swarm": CommandMeta(
        name="swarm",
        category="🤖 Agent 协作",
        summary="多 agent 实时活动监控 (runs/locks/worktree/冲突)",
    ),
    "channels": CommandMeta(
        name="channels",
        category="🔌 总线接入 (ECCP)",
        summary="External channels inventory (ECCP)",
    ),
    "bos-inbox": CommandMeta(
        name="bos-inbox",
        category="🧠 知识引擎 (BOS)",
        summary="BOS Inbox 多源私有知识神经网查询与操作",
    ),
    "bos-capability": CommandMeta(
        name="bos-capability",
        category="🧠 知识引擎 (BOS)",
        summary="BOS capability 域 / toolbox 外部能力 (list / invoke)",
    ),
    "readiness": CommandMeta(
        name="readiness",
        category="📋 项目 (Project)",
        summary="Readiness Dashboard (Phase / Gate / 核验)",
    ),
    "debt": CommandMeta(
        name="debt",
        category="📋 项目 (Project)",
        summary="技术债管理 (list / score / resolve)",
    ),
    "kems": CommandMeta(
        name="kems",
        category="📋 项目 (Project)",
        summary="知识经济指标体系 (KEMS · KPI 追踪)",
    ),
    "c2g": CommandMeta(
        name="c2g",
        category="📋 项目 (Project)",
        summary="Concept-to-Governance 生命周期转化",
    ),
    "compass": CommandMeta(
        name="compass",
        category="📋 项目 (Project)",
        summary="战略罗盘 (OKR / 目标对齐)",
    ),
    # ── 系统与运维 (System / Ops) ────────────────────────────────────────────
    "status": CommandMeta(
        name="status",
        category="🛠️ 系统 (System)",
        summary="系统健康仪表盘 (Phase / CARDS / 研究工作台)",
    ),
    "health": CommandMeta(
        name="health",
        category="🛠️ 系统 (System)",
        summary="一键系统健康检查 (7 维度)",
    ),
    "product-health": CommandMeta(
        name="product-health",
        category="🛠️ 系统 (System)",
        summary="产品健康度检测",
    ),
    "monitor": CommandMeta(
        name="monitor",
        category="🛠️ 系统 (System)",
        summary="实时监控 (进程 / 资源 / 指标)",
    ),
    "audit": CommandMeta(
        name="audit",
        category="🛠️ 系统 (System)",
        summary="🔍 6 维度全方位审计",
    ),
    "gac": CommandMeta(
        name="gac",
        category="🛠️ 系统 (System)",
        summary="GaC 治理健康检查 (ADR-0106, 7 机制 + 115 规则 + drift)",
    ),
    "runtime": CommandMeta(
        name="runtime",
        category="🛠️ 系统 (System)",
        summary="运行时环境管理",
    ),
    "agent-runtime": CommandMeta(
        name="agent-runtime",
        category="🛠️ 系统 (System)",
        summary="Agent 运行时生命周期管理",
    ),
    "version": CommandMeta(
        name="version",
        category="🛠️ 系统 (System)",
        summary="版本信息",
    ),
    "tui": CommandMeta(
        name="tui",
        category="🛠️ 系统 (System)",
        summary="极客终端交互控制台 (Textual 全屏 TUI · Vim 键盘流)",
    ),
    "journey": CommandMeta(
        name="journey",
        category="🛠️ 系统 (System)",
        summary="Journey State Graph 状态表达校验器",
    ),
    "panorama": CommandMeta(
        name="panorama",
        category="🛠️ 系统 (System)",
        summary="7 维全景终极可观测仪表盘 (执行/服务/内容/知识/数据/异常/债务)",
    ),
    "project": CommandMeta(
        name="project",
        category="🛠️ 系统 (System)",
        summary=f"{submodule_count()} 项目全景 4D 体检与诊断",
    ),
    # ── 数据与导入 (Data / Import) ───────────────────────────────────────────
    "import": CommandMeta(
        name="import",
        category="📦 数据 (Data)",
        summary="导入外部内容 (Markdown / URL / 文件)",
    ),
    "data": CommandMeta(
        name="data",
        category="📦 数据 (Data)",
        summary="数据目录索引 / 类型注册 / TTL 清理",
    ),
    "contracts": CommandMeta(
        name="contracts",
        category="📦 数据 (Data)",
        summary="契约验证 (validate / list / export)",
    ),
    # ── BOS / 知识引擎 (BOS / Knowledge Engine) ─────────────────────────────
    "bos": CommandMeta(
        name="bos",
        category="🧠 知识引擎 (BOS)",
        summary="BOS URI 查询与管理 (list / resolve / read / inbox / …)",
    ),
    "brain": CommandMeta(
        name="brain",
        category="🧠 知识引擎 (BOS)",
        summary="个人数字大脑 (ask / remember / history / context)",
    ),
    "gbrain": CommandMeta(
        name="gbrain",
        category="🧠 知识引擎 (BOS)",
        summary="Postgres-native 知识库 (search / import / stats)",
    ),
    "kairon": CommandMeta(
        name="kairon",
        category="🧠 知识引擎 (BOS)",
        summary="kairon 知识引擎 monorepo 聚合入口",
    ),
    "vault": CommandMeta(
        name="vault",
        category="🧠 知识引擎 (BOS)",
        summary="搜索 L4 Vault 知识库",
    ),
    "domains": CommandMeta(
        name="domains",
        category="🧠 知识引擎 (BOS)",
        summary="列出 L4 所有域及其状态",
    ),
    "skill": CommandMeta(
        name="skill",
        category="🧠 知识引擎 (BOS)",
        summary="运行 L4 定时技能",
    ),
    # ── 治理与架构 (Governance / Arch) ───────────────────────────────────────
    "governance": CommandMeta(
        name="governance",
        category="🏛️ 治理 (Governance)",
        summary="架构治理 (委派 arcnode-*)",
    ),
    "mcp": CommandMeta(
        name="mcp",
        category="🏛️ 治理 (Governance)",
        summary="启动 MCP server 或列出工具",
    ),
    "cards": CommandMeta(
        name="cards",
        category="🏛️ 治理 (Governance)",
        summary="CARDS 卡片状态管理 (list / get / search / serve)",
    ),
    "context": CommandMeta(
        name="context",
        category="🏛️ 治理 (Governance)",
        summary="显示系统上下文 (Phase / CARDS / 约束 / 引导)",
    ),
    "bdsk": CommandMeta(
        name="bdsk",
        category="🏛️ 治理 (Governance)",
        summary="B.D.S.K. 虚拟董事会 (4角对抗辩论与 0-Touch 影子预演)",
    ),
    # ── 通讯与事件 (Messaging / Events) ─────────────────────────────────────
    "events": CommandMeta(
        name="events",
        category="📡 通讯 (Messaging)",
        summary="实时查看 Agora SSE 事件流 (Phase 34 L3 Dashboard)",
    ),
    "bus": CommandMeta(
        name="bus",
        category="📡 通讯 (Messaging)",
        summary="Omni-Bus 三平面入口 (status / topics / publish)",
    ),
    "agora": CommandMeta(
        name="agora",
        category="📡 通讯 (Messaging)",
        summary="Agora BOS 网关入口 (委派 agora CLI)",
    ),
    "ssb": CommandMeta(
        name="ssb",
        category="📡 通讯 (Messaging)",
        summary="[DEPRECATED] SSB 签名链操作 — ECOS SSB 独立 CLI 已弃用，请使用 cockpit 替代",
    ),
    # ── 基础设施 (Infrastructure) ────────────────────────────────────────────
    "dashboard": CommandMeta(
        name="dashboard",
        category="🖥️ 基础设施 (Infra)",
        summary="打开 Web Dashboard",
    ),
    "telemetry": CommandMeta(
        name="telemetry",
        category="🖥️ 基础设施 (Infra)",
        summary="命令全生命周期可观测性与 Prometheus 指标导出",
    ),
    "observe": CommandMeta(
        name="observe",
        category="🖥️ 基础设施 (Infra)",
        summary="可观测性栈（Langfuse）入口 (up / down / logs)",
    ),
    "mesh": CommandMeta(
        name="mesh",
        category="🖥️ 基础设施 (Infra)",
        summary="omlx 算力网格路由入口 (nodes / route / serve)",
    ),
    "mof": CommandMeta(
        name="mof",
        category="🖥️ 基础设施 (Infra)",
        summary="MOF 元模型操作 (委派 mof CLI)",
    ),
    "model-driven": CommandMeta(
        name="model-driven",
        category="🖥️ 基础设施 (Infra)",
        summary="[DEPRECATED] 模型驱动生命周期入口 (ADR-0240 D1) — 拒绝执行",
    ),
    # ── 专项工具 (Domain Tools) ──────────────────────────────────────────────
    "gongwen": CommandMeta(
        name="gongwen",
        category="📄 专项工具 (Domain)",
        summary="📄 公文写作门户引导 (文种 / 规范 / 入口)",
    ),
    "finance": CommandMeta(
        name="finance",
        category="📄 专项工具 (Domain)",
        summary="💰 个人财务门户引导 (场景 / 原则 / 入口)",
    ),
    "family-hub": CommandMeta(
        name="family-hub",
        category="📄 专项工具 (Domain)",
        summary="家庭数字枢纽入口 (status / api / mcp)",
    ),
    "omo": CommandMeta(
        name="omo",
        category="📄 专项工具 (Domain)",
        summary="OMO 健康自管系统",
    ),
    "compute": CommandMeta(
        name="compute",
        category="📄 专项工具 (Domain)",
        summary="算力与计算任务管理",
    ),
    "code": CommandMeta(
        name="code",
        category="📄 专项工具 (Domain)",
        summary="代码审查与质量管理",
    ),
    # ── 用户与配置 (User / Config) ───────────────────────────────────────────
    "profile": CommandMeta(
        name="profile",
        category="👤 用户 (User)",
        summary="查看/编辑身份档案 (L4 入口)",
    ),
    "quickstart": CommandMeta(
        name="quickstart",
        category="👤 用户 (User)",
        summary="🚀 新用户快速上手向导（环境核验 + 上手指引）",
        aliases=("init",),
    ),
    "init": CommandMeta(
        name="init",
        category="👤 用户 (User)",
        summary="🚀 初始化向导（同 quickstart）",
    ),
    "help": CommandMeta(
        name="help",
        category="👤 用户 (User)",
        summary="查看产品地图与快速入门",
    ),
    "demo": CommandMeta(
        name="demo",
        category="👤 用户 (User)",
        summary="快速演示",
    ),
    "completion": CommandMeta(
        name="completion",
        category="👤 用户 (User)",
        summary="生成 Shell 自动补全脚本 (bash/zsh/fish)",
    ),
    "docs": CommandMeta(
        name="docs",
        category="👤 用户 (User)",
        summary="CLI 参考手册生成与导出 (docs/CLI-REFERENCE.md)",
    ),
    # ── Phase A2 补齐: handlers 已注册但 catalog 缺失的 23 条 ─────────────────
    "domain-status": CommandMeta(
        name="domain-status",
        category="🏛️ 治理 (Governance)",
        summary="显示 Documents 域项目绑定与引导状态",
    ),
    "facts-audit": CommandMeta(
        name="facts-audit",
        category="🏛️ 治理 (Governance)",
        summary="审计 Documents 文档域 facts 文件",
    ),
    "facts-validation": CommandMeta(
        name="facts-validation",
        category="🏛️ 治理 (Governance)",
        summary="读取 Runtime Facts 审计回执",
    ),
    "model-freshness": CommandMeta(
        name="model-freshness",
        category="🏛️ 治理 (Governance)",
        summary="读取 Runtime 模型新鲜度回执",
    ),
    "sanyi-status": CommandMeta(
        name="sanyi-status",
        category="🏛️ 治理 (Governance)",
        summary="读取 Runtime 三医状态一致性回执",
    ),
    "controller-shadow": CommandMeta(
        name="controller-shadow",
        category="🏛️ 治理 (Governance)",
        summary="读取 Runtime 旧控制器影子迁移回执",
    ),
    "policy": CommandMeta(
        name="policy",
        category="🏛️ 治理 (Governance)",
        summary="⚖️ 领域监管合规与 Policy-as-Code 红线审查 (E-POL-*)",
        delegated_target="ecos.cli.constraint policy",
    ),
    "resident": CommandMeta(
        name="resident",
        category="🤖 Agent 协作",
        summary="Resident 常驻 Agent 体系 (status/roles/daemon/decision/execute/...)",
        delegated_target="omo resident",
    ),
    "cell": CommandMeta(
        name="cell",
        category="🤖 Agent 协作",
        summary="🤖 AGE-v2 动态 Agent Cell (规划/执行/验证/治理)",
    ),
    "bcos": CommandMeta(
        name="bcos",
        category="📋 项目 (Project)",
        summary="BCOS 业务域系统 (evolve/signals/north-star)",
        delegated_target="bin/bc-os/*.py",
    ),
    "capabilities": CommandMeta(
        name="capabilities",
        category="🛠️ 系统 (System)",
        summary="统一能力发现入口 — 搜索/推荐/全量列出 (CLI+BOS+Scene+Journey)",
    ),
    "intent": CommandMeta(
        name="intent",
        category="📄 专项工具 (Domain)",
        summary="🧠 自然语言意图解构与工程规格编译器 (ADR-0195)",
    ),
    "decide": CommandMeta(
        name="decide",
        category="📄 专项工具 (Domain)",
        summary="📬 决策收件箱 (列出/添加/批准/拒绝)",
    ),
    "challenge": CommandMeta(
        name="challenge",
        category="📄 专项工具 (Domain)",
        summary="⚡️ 影子红蓝对抗审查与合规自动打补丁 (ADR-0196)",
    ),
    "cartridge": CommandMeta(
        name="cartridge",
        category="📄 专项工具 (Domain)",
        summary="👁️ 长尾领域治理卡带工坊 (ADR-0198/0203)",
    ),
    "render": CommandMeta(
        name="render",
        category="📄 专项工具 (Domain)",
        summary="渲染输出",
    ),
    "im-triage": CommandMeta(
        name="im-triage",
        category="📄 专项工具 (Domain)",
        summary="IM 消息分诊",
    ),
    "fabric": CommandMeta(
        name="fabric",
        category="🖥️ 基础设施 (Infra)",
        summary="🧑‍💻 主权混合算力与 KV 缓存快照 (ADR-0197)",
    ),
    "ops": CommandMeta(
        name="ops",
        category="🖥️ 基础设施 (Infra)",
        summary="🔧 Service Gateway — 统一运维控制面",
    ),
    "watchdog": CommandMeta(
        name="watchdog",
        category="🖥️ 基础设施 (Infra)",
        summary="🐕 自治守护犬与自愈探针 (Agora Bus / Resident 监视器)",
    ),
    "ask": CommandMeta(
        name="ask",
        category="🧠 知识引擎 (BOS)",
        summary="快速大模型对话问答 (AetherForge)",
    ),
    "proxy-env": CommandMeta(
        name="proxy-env",
        category="🛠️ 系统 (System)",
        summary="输出兼容外部客户端的本地环境变量 (OPENAI_API_BASE)",
    ),
    "spine": CommandMeta(
        name="spine",
        category="📚 研究 (Research)",
        summary="Spine 主干真值流与署名自进化操作 (ADR-0437)",
    ),
    # ── 双旗标审计补齐 (parser 已注册但 catalog 缺条目) ──────────────────────
    "chain": CommandMeta(
        name="chain",
        category="🖥️ 基础设施 (Infra)",
        summary="多命令联动链路编排 (list/show/run/validate/init, YAML 声明式)",
    ),
    "command-audit": CommandMeta(
        name="command-audit",
        category="🏛️ 治理 (Governance)",
        summary="15 维命令评分卡管理 (init/validate/report/lint)",
    ),
    "harness": CommandMeta(
        name="harness",
        category="🏛️ 治理 (Governance)",
        summary="Harness 全生命周期合规 (trace/verify/gac/compliance/…)",
    ),
    "audit-ledger": CommandMeta(
        name="audit-ledger",
        category="🏛️ 治理 (Governance)",
        summary="治理审计账本查询 (隐藏运维面)",
    ),
    "fabric-mesh": CommandMeta(
        name="fabric-mesh",
        category="🖥️ 基础设施 (Infra)",
        summary="算力网格 fabric 检视 (隐藏运维面)",
    ),
    "dlp-guard": CommandMeta(
        name="dlp-guard",
        category="🏛️ 治理 (Governance)",
        summary="外发前防泄密扫描 (敏感识别+挂起+脱敏)",
    ),
    "memory-distill": CommandMeta(
        name="memory-distill",
        category="📚 研究 (Research)",
        summary="记忆蒸馏 (隐藏运维面)",
    ),
}
