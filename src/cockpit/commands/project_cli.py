"""cockpit.commands.project_cli — 项目 CLI 薄委派 (Phase B4).

``cockpit <cmd> [args...]`` 原样透传给工作区内各项目 CLI;
不带参数时显示下游 CLI 真实 ``--help``。
"""

from __future__ import annotations

from cockpit.commands.delegation import DelegatedSpec

CATEGORY = "🔌 项目 CLI (Project CLIs)"

SPECS: list[DelegatedSpec] = [
    DelegatedSpec(
        name="metaos",
        summary="MetaOS CLI — 编排/治理层: 决策门控、免疫监控、路由、数字资产引擎",
        category=CATEGORY,
        target=("uv", "run", "--quiet", "--project", "<ws>/projects/metaos", "metaos"),
        arg_attr="metaos_args",
        example='plan "研究任务" --dry-run',
        maturity="beta",
        risk="low",
    ),
    DelegatedSpec(
        name="metaos-agent",
        summary="MetaOS provider agent 会话 — prepare/context/approve/reject 等门控会话管理",
        category=CATEGORY,
        target=("uv", "run", "--quiet", "--project", "<ws>/projects/metaos", "metaos-agent"),
        arg_attr="metaos_agent_args",
        example="prepare <session>",
        maturity="beta",
        risk="low",
    ),
    DelegatedSpec(
        name="l4-kernel",
        summary="L4 自我层管理面 — DomainManifest 校验、知识域登记、只读门禁、内容审计",
        category=CATEGORY,
        target=("uv", "run", "--quiet", "--project", "<ws>/projects/l4-kernel", "l4-kernel"),
        arg_attr="l4_kernel_args",
        example="contract validate <path>",
        maturity="beta",
        risk="low",
    ),
    DelegatedSpec(
        name="omlxc",
        summary="omlx 本地算力枢纽 CLI — daemon 状态、模型别名解析 (omlxcd daemon 不在此入口)",
        category=CATEGORY,
        target=("uv", "run", "--quiet", "--project", "<ws>/projects/omlxc", "omlxc"),
        arg_attr="omlxc_args",
        example="status",
        maturity="beta",
        risk="low",
    ),
    DelegatedSpec(
        name="mof-contract-lint",
        summary="BOS 服务契约校验 — 错误解释 (--explain) 与 URI 变更影响分析 (--impact)",
        category=CATEGORY,
        target=("mof-contract-lint",),
        arg_attr="mof_contract_lint_args",
        example="--explain CONTRACT-001",
        maturity="beta",
        risk="low",
    ),
    DelegatedSpec(
        name="mof-contract-agent",
        summary="BOS 契约分析与修复 — analyze (URI 影响) / diagnose (错误日志)",
        category=CATEGORY,
        target=("mof-contract-agent",),
        arg_attr="mof_contract_agent_args",
        example="analyze <uri>",
        maturity="beta",
        risk="low",
    ),
    DelegatedSpec(
        name="ecos-partition-lint",
        summary="ecos 分区导入边界 lint (ADR-0181) — 检查包内导入是否越过分区映射",
        category=CATEGORY,
        target=("ecos-partition-lint",),
        arg_attr="ecos_partition_lint_args",
        example="--json",
        maturity="beta",
        risk="low",
    ),
]
