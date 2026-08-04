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
        summary="SSB 签名链操作 (委派 ecos-ssb)",
    ),
    # ── 基础设施 (Infrastructure) ────────────────────────────────────────────
    "dashboard": CommandMeta(
        name="dashboard",
        category="🖥️ 基础设施 (Infra)",
        summary="打开 Web Dashboard",
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
        summary="模型驱动生命周期入口 (lifecycle / spec / adr / okr)",
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
}
