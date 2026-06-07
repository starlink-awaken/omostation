"""BOS URI 解析器 — agora 侧 (P33-W4 + P34-W1 战役 1 升级).

输入: bos://<domain>/<package/<action> + args
输出: 实际 MCP 工具调用结果 (stdio 子进程 / internal / http)

P33-W3 揭出 M3 高严重度: omo 进程 verify_endpoint 时, 20/21 kairon URI 不可达.
本质: URI 解析在错误进程 (omo). 正确位置: agora 进程 — subprocess spawn
kairon 子进程, MCP 协议通信. 此模块即战役 1 的 agora 侧落地.

P34-W1 升级: 从"进程 alive 验证"到"真 stdio JSON 协议通信".
  - 完整 JSON-RPC (写请求到 stdin, 读响应从 stdout)
  - 5s 超时控制 (select + timeout)
  - 错误处理 (BrokenPipe / JSONDecode / EOF)
  - 进程池复用 (同 URI 多次调用复用同一进程)

P46 W2 升级: StdioAdapter 协议抽象封装, 支持渐进迁移到标准 MCP.
  - StdioAdapter.call(uri, args) → dict: 统一调用接口
  - 不改变现有 invoke_stdio 实现 (向后兼容)

11 POC service 覆盖 5 Domain (memory / governance / analysis / persona / capability).
"""
from __future__ import annotations

import importlib
import json
import logging
import re
import select
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from agora.legacy_compat import (
    CANONICAL_PERSONA_BRIDGE_URI_PREFIX,
    LEGACY_PERSONA_BRIDGE_SERVICE,
    LEGACY_PERSONA_BRIDGE_URI_PREFIX,
)

_log = logging.getLogger(__name__)

# ── stdio 协议默认超时 (秒) ──────────────────────────
_STDIO_TIMEOUT_DEFAULT = 5.0

# ── 4 段标准 (W1 北星 → P45 扩展域名) ──────────────
# P45: governance→omo, capability→forge, 新增 meta/ecos/agora
BOS_URI_PATTERN = re.compile(
    r"^bos://(?P<domain>memory|governance|omo|analysis|persona|capability|forge|meta|ecos|agora)"
    r"/(?P<package>[a-z][a-z0-9-]+)/(?P<action>[a-z][a-z0-9-]+)$"
)

_LEGACY_BOS_URI_ALIASES = {
    f"{LEGACY_PERSONA_BRIDGE_URI_PREFIX}recall-entity": f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall-entity",
    f"{LEGACY_PERSONA_BRIDGE_URI_PREFIX}recall": f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall",
    f"{LEGACY_PERSONA_BRIDGE_URI_PREFIX}sync": f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}sync",
}

# ── 路径常量 ────────────────────────────────────────
KAIRON_ROOT = Path("/Users/xiamingxing/Workspace/projects/kairon")
METAOS_ROOT = Path("/Users/xiamingxing/Workspace/projects/metaos")
OMOSTATION_ROOT = Path("/Users/xiamingxing/Workspace")

# ── 类型 ────────────────────────────────────────────
Transport = Literal["stdio", "internal", "http"]


@dataclass
class BosService:
    """BOS 服务描述 — 怎么调用一个 URI."""

    uri: str
    domain: str
    package: str
    action: str
    transport: Transport = "stdio"
    # stdio: command 列表 (subprocess.Popen 用)
    command: list[str] = field(default_factory=list)
    # internal: import path + func
    module_path: str = ""
    func_name: str = ""
    # http: URL
    http_url: str = ""
    # 描述
    description: str = ""


def _with_uv_package(service: BosService) -> list[str]:
    """Normalize legacy ``uv run --directory ...`` commands for workspace packages.

    Older POC entries assumed the repo root environment exposed all package modules.
    The current kairon layout does not guarantee that. Inject ``--package <name>``
    when the command is a workspace ``uv run`` and no package is specified yet.
    """
    cmd = list(service.command)
    if len(cmd) < 2 or cmd[0] != "uv" or cmd[1] != "run":
        return cmd
    if "--package" in cmd:
        return cmd
    if "--directory" not in cmd:
        return cmd
    if not service.package:
        return cmd
    return ["uv", "run", "--package", service.package, *cmd[2:]]


def normalize_bos_uri(uri: str) -> str:
    """Map legacy BOS URIs onto their canonical compatibility URI."""
    return _LEGACY_BOS_URI_ALIASES.get(uri, uri)


# ── 5 Domain 5 包 POC service registry (11 总) ──────
# 命名规范: python -m <package> serve --action <action>
# 实际 stdio 协议: stdin JSON 行 → stdout JSON 行 (POC 简化版)
POC_SERVICES: dict[str, BosService] = {
    # Memory (2)
    "bos://memory/kos/search": BosService(
        uri="bos://memory/kos/search",
        domain="memory",
        package="kos",
        action="search",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "kos", "serve", "--action", "search",
        ],
        description="KOS 跨域语义搜索 (POC stdio)",
    ),
    "bos://memory/kronos/ingest": BosService(
        uri="bos://memory/kronos/ingest",
        domain="memory",
        package="kronos",
        action="ingest",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "kronos", "serve", "--action", "ingest",
        ],
        description="Kronos 知识摄入 (POC stdio)",
    ),
    # Governance (4)
    "bos://governance/omo/audit": BosService(
        uri="bos://governance/omo/audit",
        domain="governance",
        package="omo",
        action="audit",
        transport="internal",
        module_path="omo.omo_audit",
        func_name="run_governance_audit",
        description="OMO 治理审计 (internal — 同进程 importlib)",
    ),
    "bos://governance/metaos/gate": BosService(
        uri="bos://governance/metaos/gate",
        domain="governance",
        package="metaos",
        action="gate",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(METAOS_ROOT),
            "python", "-m", "metaos", "serve", "--action", "gate",
        ],
        description="MetaOS 门控检查 (POC stdio)",
    ),
    "bos://governance/sot-bridge/register": BosService(
        uri="bos://governance/sot-bridge/register",
        domain="governance",
        package="sot-bridge",
        action="register",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "sot_bridge", "serve", "--action", "register",
        ],
        description="SOT-Bridge 注册 (POC stdio)",
    ),
    "bos://governance/protocols-layer/trigger": BosService(
        uri="bos://governance/protocols-layer/trigger",
        domain="governance",
        package="protocols-layer",
        action="trigger",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "protocols_layer", "serve", "--action", "trigger",
        ],
        description="Protocols-Layer 触发 (POC stdio)",
    ),
    # Analysis (12 POC — P34-W5 补 minerva.draft/audit, codeanalyze.report/lint, iris.connect/transform/validate, ontoderive.audit/fact-check)
    "bos://analysis/minerva/research": BosService(
        uri="bos://analysis/minerva/research",
        domain="analysis",
        package="minerva",
        action="research",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "minerva", "serve", "--action", "research",
        ],
        description="Minerva 深度研究 (POC stdio)",
    ),
    "bos://analysis/minerva/draft": BosService(
        uri="bos://analysis/minerva/draft",
        domain="analysis",
        package="minerva",
        action="draft",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "minerva", "serve", "--action", "draft",
        ],
        description="Minerva 草稿生成 (POC stdio)",
    ),
    "bos://analysis/minerva/audit": BosService(
        uri="bos://analysis/minerva/audit",
        domain="analysis",
        package="minerva",
        action="audit",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "minerva", "serve", "--action", "audit",
        ],
        description="Minerva 审计 (POC stdio)",
    ),
    "bos://analysis/ontoderive/derive": BosService(
        uri="bos://analysis/ontoderive/derive",
        domain="analysis",
        package="ontoderive",
        action="derive",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "ontoderive", "serve", "--action", "derive",
        ],
        description="Ontoderive 事实推导 (POC stdio)",
    ),
    "bos://analysis/ontoderive/audit": BosService(
        uri="bos://analysis/ontoderive/audit",
        domain="analysis",
        package="ontoderive",
        action="audit",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "ontoderive", "serve", "--action", "audit",
        ],
        description="Ontoderive 审计 (POC stdio)",
    ),
    "bos://analysis/ontoderive/fact-check": BosService(
        uri="bos://analysis/ontoderive/fact-check",
        domain="analysis",
        package="ontoderive",
        action="fact-check",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "ontoderive", "serve", "--action", "fact-check",
        ],
        description="Ontoderive 事实校验 (POC stdio)",
    ),
    "bos://analysis/codeanalyze/scan": BosService(
        uri="bos://analysis/codeanalyze/scan",
        domain="analysis",
        package="codeanalyze",
        action="scan",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "codeanalyze", "serve", "--action", "scan",
        ],
        description="CodeAnalyze 代码扫描 (POC stdio)",
    ),
    "bos://analysis/codeanalyze/report": BosService(
        uri="bos://analysis/codeanalyze/report",
        domain="analysis",
        package="codeanalyze",
        action="report",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "codeanalyze", "serve", "--action", "report",
        ],
        description="CodeAnalyze 分析报告 (POC stdio)",
    ),
    "bos://analysis/codeanalyze/lint": BosService(
        uri="bos://analysis/codeanalyze/lint",
        domain="analysis",
        package="codeanalyze",
        action="lint",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "codeanalyze", "serve", "--action", "lint",
        ],
        description="CodeAnalyze Lint (POC stdio)",
    ),
    "bos://analysis/iris/connect": BosService(
        uri="bos://analysis/iris/connect",
        domain="analysis",
        package="iris",
        action="connect",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "iris", "serve", "--action", "connect",
        ],
        description="Iris 连接 (POC stdio)",
    ),
    "bos://analysis/iris/transform": BosService(
        uri="bos://analysis/iris/transform",
        domain="analysis",
        package="iris",
        action="transform",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "iris", "serve", "--action", "transform",
        ],
        description="Iris 数据转换 (POC stdio)",
    ),
    "bos://analysis/iris/validate": BosService(
        uri="bos://analysis/iris/validate",
        domain="analysis",
        package="iris",
        action="validate",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "iris", "serve", "--action", "validate",
        ],
        description="Iris 数据校验 (POC stdio)",
    ),
    # Persona (1 POC)
    "bos://persona/health-profile/summary": BosService(
        uri="bos://persona/health-profile/summary",
        domain="persona",
        package="health-profile",
        action="summary",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "health_profile", "serve", "--action", "summary",
        ],
        description="Health-Profile 健康摘要 (POC stdio)",
    ),
    # Capability (1 POC)
    "bos://capability/forge/register-tool": BosService(
        uri="bos://capability/forge/register-tool",
        domain="capability",
        package="forge",
        action="register-tool",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "forge", "serve", "--action", "register-tool",
        ],
        description="Forge 工具注册 (POC stdio)",
    ),
    # P36-W1 跨域 GAP 补 5 条 (P35-W0 spec 注册但未在 resolver)
    # Note: sharedbrain-bridge / sot-bridge are legacy BOS compatibility names.
    # They no longer correspond to live installable packages in the current
    # kairon tree, but tests and downstream routing still depend on the URI layer.
    f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall-entity": BosService(
        uri=f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall-entity",
        domain="persona",
        package=LEGACY_PERSONA_BRIDGE_SERVICE,
        action="recall-entity",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "sot_bridge.sharedbrain_bridge", "serve", "--action", "recall-entity",
        ],
        description="Legacy persona bridge entity recall (canonical compatibility URI, P36-W1 补, POC stdio)",
    ),
    "bos://persona/health-profile/alert": BosService(
        uri="bos://persona/health-profile/alert",
        domain="persona",
        package="health-profile",
        action="alert",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "health_profile", "serve", "--action", "alert",
        ],
        description="Health-Profile 健康告警 (P36-W1 补, POC stdio)",
    ),
    "bos://capability/forge/exec-tool": BosService(
        uri="bos://capability/forge/exec-tool",
        domain="capability",
        package="forge",
        action="exec-tool",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "forge", "serve", "--action", "exec-tool",
        ],
        description="Forge 工具执行 (P36-W1 补, POC stdio)",
    ),
    "bos://capability/forge/list-tools": BosService(
        uri="bos://capability/forge/list-tools",
        domain="capability",
        package="forge",
        action="list-tools",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "forge", "serve", "--action", "list-tools",
        ],
        description="Forge 工具列表 (P36-W1 补, POC stdio)",
    ),
    "bos://governance/omo/inspect": BosService(
        uri="bos://governance/omo/inspect",
        domain="governance",
        package="omo",
        action="inspect",
        transport="internal",
        module_path="omo.omo_inspect",
        func_name="run_full_inspection",
        description="OMO 系统检查 (P36-W1 补, internal 同进程)",
    ),
    # ── P45-W0 战役 1: 3 个高 ROI GAP URI 实施 (P44-W2 评估) ──
    f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall": BosService(
        uri=f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall",
        domain="persona",
        package=LEGACY_PERSONA_BRIDGE_SERVICE,
        action="recall",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "sot_bridge.sharedbrain_bridge", "serve", "--action", "recall",
        ],
        description="Legacy persona bridge semantic recall (canonical compatibility URI, P45-W0, POC stdio, recall-entity 的泛化版)",
    ),
    "bos://capability/forge/discover": BosService(
        uri="bos://capability/forge/discover",
        domain="capability",
        package="forge",
        action="discover",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "forge", "serve", "--action", "discover",
        ],
        description="Forge 工具发现 (P45-W0, POC stdio, LLM 工具选择关键)",
    ),
    "bos://memory/kos/ingest": BosService(
        uri="bos://memory/kos/ingest",
        domain="memory",
        package="kos",
        action="ingest",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "kos", "serve", "--action", "ingest",
        ],
        description="KOS 实体写入 (P45-W0, POC stdio, search 的对偶)",
    ),
    # ── P45-W1 战役 1: 2 个 kronos GAP URI (P44-W2 评估) ──
    "bos://memory/kronos/query": BosService(
        uri="bos://memory/kronos/query",
        domain="memory",
        package="kronos",
        action="query",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "kronos", "serve", "--action", "query",
        ],
        description="KRONOS 时间序列查询 (P45-W1, POC stdio, ingest 的对偶)",
    ),
    "bos://memory/kronos/schedule": BosService(
        uri="bos://memory/kronos/schedule",
        domain="memory",
        package="kronos",
        action="schedule",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "kronos", "serve", "--action", "schedule",
        ],
        description="KRONOS 调度任务 (P45-W1, POC stdio)",
    ),
    # ── P45-W2 战役 1: 2 个 governance GAP URI (P44-W2 评估, 跳 omo/sync 复杂度 5) ──
    "bos://governance/metaos/register": BosService(
        uri="bos://governance/metaos/register",
        domain="governance",
        package="metaos",
        action="register",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(METAOS_ROOT),
            "python", "-m", "metaos", "serve", "--action", "register",
        ],
        description="MetaOS 包注册 (P45-W2, POC stdio, gate 的对偶)",
    ),
    "bos://governance/sot-bridge/query": BosService(
        uri="bos://governance/sot-bridge/query",
        domain="governance",
        package="sot-bridge",
        action="query",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "sot_bridge", "serve", "--action", "query",
        ],
        description="SOT-Bridge 跨系统查询 (legacy compatibility URI, P45-W2, POC stdio, register 的对偶)",
    ),
    # ── P45-W3 战役 1: 3 个 persona GAP URI (P44-W2 评估) ──
    "bos://persona/core-models/schema": BosService(
        uri="bos://persona/core-models/schema",
        domain="persona",
        package="core-models",
        action="schema",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "core_models", "serve", "--action", "schema",
        ],
        description="core-models schema (P45-W3, POC stdio)",
    ),
    "bos://persona/core-models/validate": BosService(
        uri="bos://persona/core-models/validate",
        domain="persona",
        package="core-models",
        action="validate",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "core_models", "serve", "--action", "validate",
        ],
        description="core-models 验证 (P45-W3, POC stdio, schema 的对偶)",
    ),
    f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}sync": BosService(
        uri=f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}sync",
        domain="persona",
        package=LEGACY_PERSONA_BRIDGE_SERVICE,
        action="sync",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(KAIRON_ROOT),
            "python", "-m", "sot_bridge.sharedbrain_bridge", "serve", "--action", "sync",
        ],
        description="Legacy persona bridge sync (canonical compatibility URI, P45-W3, POC stdio, recall-entity 的对偶)",
    ),
    # ── P48-W2 omo/sync 真重构 (stdio transport, 替代 P47 internal) ──
    "bos://governance/omo/sync": BosService(
        uri="bos://governance/omo/sync",
        domain="governance",
        package="omo",
        action="sync",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(OMOSTATION_ROOT / "projects" / "omo"),
            "python", "-m", "omo", "serve",
        ],
        description="OMO 状态同步 (P48-W2 真重构, stdio transport 跨进程, 替代 P47 internal)",
    ),
    # ── P46 战役 2: 4 个 agent-runtime URI 跨项目 spawn runtime (P44-W2 评估) ──
    "bos://capability/agent-runtime/agent-list": BosService(
        uri="bos://capability/agent-runtime/agent-list",
        domain="capability",
        package="agent-runtime",
        action="agent-list",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(OMOSTATION_ROOT / "projects" / "runtime"),
            "python", "-m", "runtime.executor.agent_hub", "serve", "--action", "agent-list",
        ],
        description="Agent-runtime agent-list (P46, POC stdio, 跨项目 spawn runtime, 待 runtime serve dispatcher 适配)",
    ),
    "bos://capability/agent-runtime/chat": BosService(
        uri="bos://capability/agent-runtime/chat",
        domain="capability",
        package="agent-runtime",
        action="chat",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(OMOSTATION_ROOT / "projects" / "runtime"),
            "python", "-m", "runtime.executor.agent_runner", "serve", "--action", "chat",
        ],
        description="Agent-runtime chat (P46, POC stdio, 跨项目 spawn runtime, P39-W1 卫健委可能用)",
    ),
    "bos://capability/agent-runtime/run-task": BosService(
        uri="bos://capability/agent-runtime/run-task",
        domain="capability",
        package="agent-runtime",
        action="run-task",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(OMOSTATION_ROOT / "projects" / "runtime"),
            "python", "-m", "runtime.executor.agent_executor", "serve", "--action", "run-task",
        ],
        description="Agent-runtime run-task (P46, POC stdio, 跨项目 spawn runtime)",
    ),
    "bos://capability/agent-runtime/task-status": BosService(
        uri="bos://capability/agent-runtime/task-status",
        domain="capability",
        package="agent-runtime",
        action="task-status",
        transport="stdio",
        command=[
            "uv", "run", "--directory", str(OMOSTATION_ROOT / "projects" / "runtime"),
            "python", "-m", "runtime.executor.agent_hub", "serve", "--action", "task-status",
        ],
        description="Agent-runtime task-status (P46, POC stdio, 跨项目 spawn runtime)",
    ),
}


@dataclass
class ProcessPool:
    """BOS stdio 进程池 — 持久后台, 按需调用.

    设计:
      - 懒加载: 第一次调用时 spawn, 后续复用
      - 轻量清理: 提供 shutdown() 优雅终止
      - 持久 stdio: spawn 后保持 stdin/stdout 打开, 持续 serve (P34-W1)
      - request_id 自增: 每次调用分配唯一 request_id 跟踪响应
    """

    processes: dict[str, subprocess.Popen] = field(default_factory=dict)
    # 跟踪曾经 spawn 过的 URI (P35-W1), 让 respawn_dead 知道哪些 URI 应该被检查
    seen_uris: set[str] = field(default_factory=set)
    request_id: int = 0

    def _next_id(self) -> str:
        """生成唯一 request_id (req-<seq>-<rand>)."""
        self.request_id += 1
        return f"req-{self.request_id}-{uuid.uuid4().hex[:8]}"

    def get_or_spawn(self, service: BosService, force_respawn: bool = False) -> subprocess.Popen:
        """懒加载 spawn + 自动 respawn 死进程 (P35-W1 升级).

        Args:
            service: BOS 服务描述
            force_respawn: 强制先 kill 旧进程再 spawn 新进程

        Returns:
            subprocess.Popen: spawn 后的进程句柄
        """
        # 强制 respawn: 先 kill 旧进程
        if force_respawn and service.uri in self.processes:
            old_proc = self.processes.pop(service.uri)
            if old_proc.poll() is None:
                old_proc.terminate()
                try:
                    old_proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    old_proc.kill()
                    old_proc.wait()

        # 懒加载 / 死进程自动 respawn
        if service.uri not in self.processes or not self.is_alive(service.uri):
            # 死进程清理 (is_alive 已处理, 此处保险)
            if service.uri in self.processes and not self.is_alive(service.uri):
                self.processes.pop(service.uri, None)
            command = _with_uv_package(service)
            self.processes[service.uri] = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(KAIRON_ROOT),
                bufsize=0,  # unbuffered for stdio JSON 协议
            )
            # 记录: 此 URI 曾经 spawn 过 (供 respawn_dead 使用)
            self.seen_uris.add(service.uri)
            _log.info(
                "Spawned BOS service: %s (pid=%d, command=%s)",
                service.uri,
                self.processes[service.uri].pid,
                command,
            )
        return self.processes[service.uri]

    def is_alive(self, uri: str) -> bool:
        """检查进程是否 alive + 自动清理死进程 (P35-W1 升级).

        Returns:
            bool: 进程存在且 alive 时为 True
        """
        proc = self.processes.get(uri)
        if proc is None:
            return False
        if proc.poll() is not None:
            # 进程已死, 清理 (下次调用会 respawn)
            self.processes.pop(uri, None)
            return False
        return True

    def respawn_dead(self) -> list[str]:
        """批量 respawn 死进程 (P35-W1 战役 4).

        策略: 遍历 seen_uris (曾经 spawn 过的 URI), 对死进程重新 spawn.
        这样不受 is_alive 自动清理影响 — 已从池清理的 URI 仍能被重新 spawn,
        仍留在池中的死进程也能被重建.

        Returns:
            list[str]: 被 respawn 的 URI 列表
        """
        respawned: list[str] = []
        # 迭代 seen_uris 快照 (避免迭代中修改)
        for uri in list(self.seen_uris):
            proc = self.processes.get(uri)
            is_dead = proc is None or proc.poll() is not None
            if not is_dead:
                continue
            # 找 service 重建
            service = POC_SERVICES.get(uri)
            if service is None:
                # 不在注册表: 清理 tracking
                self.seen_uris.discard(uri)
                self.processes.pop(uri, None)
                continue
            # 清理 + 重建
            if proc is not None:
                self.processes.pop(uri, None)
            self.get_or_spawn(service)
            respawned.append(uri)
            _log.warning("Respawned process: %s (new pid=%d)", uri, self.processes[uri].pid)
        return respawned

    def shutdown(self, uri: str | None = None) -> int:
        """关闭一个或全部进程. 返回关闭数量."""
        if uri is None:
            count = 0
            for u in list(self.processes.keys()):
                count += self.shutdown(u)
            # 清空 seen_uris 跟踪 (P35-W1)
            self.seen_uris.clear()
            return count
        proc = self.processes.pop(uri, None)
        # 单个 shutdown 不清 seen_uris (允许未来 respawn)
        if proc is None:
            return 0
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        return 1

    def status(self) -> dict[str, bool]:
        """全部 URI → alive 状态."""
        return {uri: self.is_alive(uri) for uri in self.processes}


# 全局进程池 (单例)
_pool = ProcessPool()


def get_pool() -> ProcessPool:
    """获取全局进程池."""
    return _pool


# ── 解析 + 调用 ─────────────────────────────────────
def parse_bos_uri(uri: str) -> dict[str, str]:
    """解析 BOS URI. 抛 ValueError 当格式错."""
    normalized = normalize_bos_uri(uri)
    m = BOS_URI_PATTERN.match(normalized)
    if not m:
        raise ValueError(f"Invalid BOS URI: {uri!r} (expected bos://<domain>/<package>/<action>)")
    return m.groupdict()


def _call_internal(service: BosService, *args: Any, **kwargs: Any) -> dict:
    """internal transport: 同进程 importlib 调用."""
    try:
        mod = importlib.import_module(service.module_path)
        func = getattr(mod, service.func_name)
        result = func(*args, **kwargs)
    except ImportError as exc:
        return {
            "uri": service.uri,
            "transport": "internal",
            "status": "error",
            "error": f"import_failed: {exc}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "uri": service.uri,
            "transport": "internal",
            "status": "error",
            "error": f"call_failed: {exc}",
        }
    # dataclass 兼容
    if hasattr(result, "__dataclass_fields__"):
        result_repr = {k: str(v) for k, v in result.__dict__.items()}
    elif isinstance(result, (dict, list, str, int, float, bool, type(None))):
        result_repr = result
    else:
        result_repr = repr(result)
    return {
        "uri": service.uri,
        "transport": "internal",
        "status": "ok",
        "result_type": type(result).__name__,
        "result": result_repr,
    }


def _call_stdio(service: BosService, *args: Any, request_uri: str | None = None, **kwargs: Any) -> dict:
    """stdio transport: 真 stdio JSON 协议 (P34-W1 升级).

    流程:
      1. spawn kairon 子进程 (Popen, bufsize=0 unbuffered)
      2. 写 JSON 请求到 stdin: {"request_id", "action", "args"}
      3. 读一行 JSON 响应从 stdout: {"status", "result"|"error", ...}
      4. 5s 超时控制 (select)
      5. 进程持久: 后续调用复用 (不关闭)

    协议格式 (与 kairon __main__.py 一致):
      请求: {"request_id": "req-N-xxx", "action": "<name>", "args": <list>}
      响应: {"status": "ok|error", "service": "<name>", "action": "<name>",
             "request_id": "<id>", "result": {...} | "error": "..."}

    返回字段: 包装 invoke_stdio 响应, 加 transport + 兼容 alive_at_spawn 字段.
    """
    response = invoke_stdio(request_uri or service.uri, service.action, args, kwargs, timeout=_STDIO_TIMEOUT_DEFAULT)
    # 包装: 补 transport 字段 + alive_at_spawn (兼容 P33 测试)
    response["transport"] = "stdio"
    if response.get("status") == "ok":
        response["alive_at_spawn"] = True
        response["command"] = _with_uv_package(service)
    return response


def invoke_stdio(
    uri: str,
    action: str,
    args: list | None = None,
    kwargs: dict | None = None,
    timeout: float = _STDIO_TIMEOUT_DEFAULT,
) -> dict:
    """通过 stdio JSON 协议调用 BOS 服务 (P34-W1 主入口).

    协议:
      写一行 JSON 到 stdin: {"request_id": "req-N-xxx", "action": "...", "args": [...]}
      从 stdout 读一行 JSON: {"status": "ok|error", "result": {...} | "error": "..."}

    Args:
        uri: bos://<domain>/<package>/<action>
        action: 子进程的 action 名 (从 URI 解析)
        args: 位置参数列表
        kwargs: 关键字参数字典
        timeout: 超时秒数 (默认 5.0)

    Returns:
        dict: 含 status + result/error + request_id + pid 等字段
    """
    canonical_uri = normalize_bos_uri(uri)
    service = POC_SERVICES.get(canonical_uri)
    if service is None:
        # 提供类似 URI 推荐
        suggestions = []
        from agora.mcp.bos_router import bos_router as _br
        known = _br.list_all()
        uri_parts = uri.strip("/").split("/")
        for r in known:
            known_uri = r["prefix"].strip("/")
            if len(uri_parts) >= 2 and any(p in known_uri for p in uri_parts):
                suggestions.append(known_uri + "/")
        hint = ""
        if suggestions:
            hint = f" Did you mean: {', '.join(suggestions[:5])}?"
        return {
            "uri": uri,
            "status": "error",
            "error": f"unknown_bos_uri: {uri} (registered: {len(POC_SERVICES)})",
            "hint": hint.strip(),
        }
    if service.transport != "stdio":
        return {
            "uri": uri,
            "status": "error",
            "error": f"not_stdio_transport: {service.transport}",
        }

    pool = get_pool()
    try:
        # 双重保险: is_alive 已自动清理, get_or_spawn 再保险一次
        if canonical_uri in pool.processes and not pool.is_alive(canonical_uri):
            _log.warning("Process dead on invoke, will respawn: %s", canonical_uri)
        proc = pool.get_or_spawn(service)
    except FileNotFoundError as exc:
        return {
            "uri": uri,
            "status": "error",
            "error": f"command_not_found: {exc}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "uri": uri,
            "status": "error",
            "error": f"spawn_failed: {exc}",
        }

    if not pool.is_alive(canonical_uri):
        # 最后兜底: 自动 respawn (P35-W1 升级)
        try:
            proc = pool.get_or_spawn(service, force_respawn=True)
        except Exception as exc:  # noqa: BLE001
            return {
                "uri": uri,
                "status": "error",
                "error": f"respawn_failed: {exc}",
            }
        if not pool.is_alive(canonical_uri):
            return {
                "uri": uri,
                "status": "error",
                "error": f"process_still_dead_after_respawn: pid={proc.pid}",
            }

    # 构造请求
    request_id = pool._next_id()
    request = {
        "request_id": request_id,
        "action": action,
        "args": list(args) if args else [],
    }
    if kwargs:
        request["kwargs"] = kwargs
    request_line = json.dumps(request, ensure_ascii=False) + "\n"

    try:
        # 写请求
        proc.stdin.write(request_line.encode("utf-8"))
        proc.stdin.flush()

        # 读响应 (select 避免阻塞)
        ready, _, _ = select.select([proc.stdout], [], [], timeout)
        if not ready:
            return {
                "uri": uri,
                "status": "error",
                "error": f"timeout_after_{timeout}s",
                "request_id": request_id,
                "pid": proc.pid,
            }

        response_line = proc.stdout.readline()
        if not response_line:
            return {
                "uri": uri,
                "status": "error",
                "error": "eof_no_response",
                "request_id": request_id,
                "pid": proc.pid,
            }

        response = json.loads(response_line.decode("utf-8"))
        response["uri"] = uri
        response["canonical_uri"] = canonical_uri
        response["request_id"] = response.get("request_id", request_id)
        response["pid"] = proc.pid
        return response

    except BrokenPipeError as exc:
        return {
            "uri": uri,
            "status": "error",
            "error": f"broken_pipe: {exc}",
            "request_id": request_id,
        }
    except OSError as exc:
        return {
            "uri": uri,
            "status": "error",
            "error": f"stdio_io_error: {exc}",
            "request_id": request_id,
        }
    except json.JSONDecodeError as exc:
        return {
            "uri": uri,
            "status": "error",
            "error": f"json_decode_error: {exc}",
            "request_id": request_id,
        }


# ── Protocol Adapter (P46 W2) ───────────────────────

class StdioAdapter:
    """stdio 协议适配器 — 封装 invoke_stdio 为统一接口。

    用法:
        adapter = StdioAdapter(timeout=5.0)
        result = adapter.call("bos://memory/kos/search", {"query": "..."})

    设计意图: 渐进迁移到标准 MCP stdio JSON-RPC 2.0 协议。
    当前底层仍使用自定义简化协议，但通过此适配器隔离变化。
    """

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    def call(self, uri: str, action: str, args: list | None = None, kwargs: dict | None = None) -> dict:
        """调用 stdio 子进程。

        Args:
            uri: bos://domain/package/action
            action: 子进程 action 名
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            dict 含 status + result/error
        """
        return invoke_stdio(
            uri=uri,
            action=action,
            args=args or [],
            kwargs=kwargs or {},
            timeout=self.timeout,
        )

    def health_check(self, uri: str) -> bool:
        """检查 URI 对应的子进程是否存活 (read-only, 不 force respawn)."""
        service = POC_SERVICES.get(uri)
        if not service:
            return False
        pool = get_pool()
        proc = pool.get_or_spawn(service)  # 默认 force_respawn=False
        return proc is not None and proc.poll() is None


def get_stdio_adapter(timeout: float = 5.0) -> StdioAdapter:
    """获取 stdio 适配器实例。"""
    return StdioAdapter(timeout=timeout)


async def resolve_bos_uri(uri: str, *args: Any, **kwargs: Any) -> dict:
    """解析 BOS URI 到实际调用 (主入口, async 兼容)."""
    parsed = parse_bos_uri(uri)
    canonical_uri = normalize_bos_uri(uri)
    service = POC_SERVICES.get(canonical_uri)
    if service is None:
        return {
            "uri": uri,
            "canonical_uri": canonical_uri,
            "parsed": parsed,
            "status": "error",
            "error": f"unknown_bos_uri: {uri} (registered: {len(POC_SERVICES)})",
        }
    if service.transport == "internal":
        # internal 在事件循环内同步执行 (omo 同进程)
        return _call_internal(service, *args, **kwargs)
    if service.transport == "stdio":
        result = _call_stdio(service, *args, request_uri=uri, **kwargs)
        result.setdefault("uri", uri)
        result.setdefault("canonical_uri", canonical_uri)
        return result
    return {
        "uri": uri,
        "status": "error",
        "error": f"unsupported_transport: {service.transport}",
    }


def list_services() -> list[dict]:
    """列出所有 POC services + 实时状态 + PID (P34-W1 升级含 pid)."""
    pool = get_pool()
    out = []
    for uri, svc in POC_SERVICES.items():
        proc = pool.processes.get(uri) if svc.transport == "stdio" else None
        out.append({
            "uri": uri,
            "domain": svc.domain,
            "package": svc.package,
            "action": svc.action,
            "transport": svc.transport,
            "alive": pool.is_alive(uri) if svc.transport == "stdio" else None,
            "pid": proc.pid if proc and proc.pid else None,
            "description": svc.description,
        })
    return out


def get_service(uri: str) -> BosService | None:
    """查询单个 service (无副作用)."""
    return POC_SERVICES.get(normalize_bos_uri(uri))


def list_domains() -> dict[str, list[str]]:
    """按 domain 聚合 URI."""
    grouped: dict[str, list[str]] = {}
    for uri, svc in POC_SERVICES.items():
        grouped.setdefault(svc.domain, []).append(uri)
    return grouped


# ── 协议健康自检 (P33-W4 战役 1 自带) ─────────────
def protocol_self_check() -> dict:
    """自检: 报告注册表 + 解析器 + 池状态."""
    return {
        "status": "ok",
        "total_services": len(POC_SERVICES),
        "domains": list(list_domains().keys()),
        "by_transport": {
            t: sum(1 for s in POC_SERVICES.values() if s.transport == t)
            for t in ("stdio", "internal", "http")
        },
        "active_processes": len(get_pool().processes),
        "kairon_root": str(KAIRON_ROOT),
        "metaos_root": str(METAOS_ROOT),
    }


# Re-export 关键 API
__all__ = (
    "BOS_URI_PATTERN",
    "BosService",
    "ProcessPool",
    "KAIRON_ROOT",
    "normalize_bos_uri",
    "METAOS_ROOT",
    "POC_SERVICES",
    "get_pool",
    "parse_bos_uri",
    "resolve_bos_uri",
    "invoke_stdio",
    "list_services",
    "list_domains",
    "get_service",
    "protocol_self_check",
)


if __name__ == "__main__":
    # CLI 自检模式: python -m agora.mcp.bos_resolver self-check
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "self-check":
        print(json.dumps(protocol_self_check(), indent=2, ensure_ascii=False))
    else:
        # 默认: 打印所有 services
        for svc in list_services():
            print(json.dumps(svc, ensure_ascii=False))
