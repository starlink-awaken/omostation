"""cockpit.commands.root_bin — 根 bin/ 薄委派命令组 (Phase B5).

flat 组: 每个脚本一条 DelegatedSpec, --help 由下游 CLI 透传.
源脚本: workspace 根 ``bin/*.py`` (commit-assist / ssot / 工具审计 / 治理检查等).
"""

from __future__ import annotations

from cockpit.commands.delegation import DelegatedSpec

SPECS: list[DelegatedSpec] = [
    DelegatedSpec(
        name="commit-assist",
        summary="LLM 辅助生成 Conventional Commits 提交信息 (aetherforge → ollama → heuristic)",
        category="🧰 工具集 (Utilities)",
        target=("python3", "<ws>/bin/commit-assist.py"),
        arg_attr="commit_assist_args",
        example="--dry-run",
    ),
    DelegatedSpec(
        name="health-ssot",
        summary="校验 health_score SSOT 引用与时效",
        category="🧰 工具集 (Utilities)",
        target=("python3", "<ws>/bin/check_health_ssot.py"),
        arg_attr="health_ssot_args",
        example="--warn-only",
    ),
    DelegatedSpec(
        name="cockpit-readiness",
        summary="P65 cockpit readiness 汇总 (委派 governance-dashboard --readiness-summary)",
        category="🧰 工具集 (Utilities)",
        target=("python3", "<ws>/bin/cockpit-readiness.py"),
        arg_attr="cockpit_readiness_args",
        example="--format json",
    ),
    DelegatedSpec(
        name="compass-radar",
        summary="调 c2g 真审计并写 health SSOT",
        category="🧰 工具集 (Utilities)",
        target=("python3", "<ws>/bin/compass_radar.py"),
        arg_attr="compass_radar_args",
        example="--dry-run",
    ),
    DelegatedSpec(
        name="delegation-preflight",
        summary="会话启动前检查 subagent 委托基础设施",
        category="🧰 工具集 (Utilities)",
        target=("python3", "<ws>/bin/delegation-preflight.py"),
        arg_attr="delegation_preflight_args",
        example="--json",
    ),
    DelegatedSpec(
        name="scheduler-compile",
        summary="编译/校验定时任务 (crontab 生成)",
        category="🧰 工具集 (Utilities)",
        target=("python3", "<ws>/bin/scheduler-compile.py"),
        arg_attr="scheduler_compile_args",
        example="--check",
    ),
    DelegatedSpec(
        name="ssot-watcher",
        summary="SSOT 变更追踪与自动化 (status/log/preview/sync)",
        category="🧰 工具集 (Utilities)",
        target=("python3", "<ws>/bin/ssot-watcher.py"),
        arg_attr="ssot_watcher_args",
        example="status",
    ),
    DelegatedSpec(
        name="tool-registry-audit",
        summary="bin/scripts 工具注册表审计 (快照对比 / emit / strict)",
        category="🧰 工具集 (Utilities)",
        target=("python3", "<ws>/bin/tool-registry-audit.py"),
        arg_attr="tool_registry_audit_args",
        example="--scope bin --strict",
    ),
    DelegatedSpec(
        name="submodule-gitlink-check",
        summary="检查 submodule gitlink 指针与远端一致性",
        category="🧰 工具集 (Utilities)",
        target=("python3", "<ws>/bin/submodule-gitlink-check.py"),
        arg_attr="submodule_gitlink_check_args",
        example="",
    ),
    DelegatedSpec(
        name="layer-dependency-check",
        summary="分层依赖检查器 (layer contract 校验)",
        category="🧰 工具集 (Utilities)",
        target=("python3", "<ws>/bin/layer-dependency-check.py"),
        arg_attr="layer_dependency_check_args",
        example="--project cockpit --json",
    ),
    DelegatedSpec(
        name="change-lane-check",
        summary="检查 staged/unstaged 变更的车道 (lane) 合规性",
        category="🧰 工具集 (Utilities)",
        target=("python3", "<ws>/bin/change-lane-check.py"),
        arg_attr="change_lane_check_args",
        example="--staged --json",
    ),
    DelegatedSpec(
        name="delegation-alias-check",
        summary="opencode ↔ omlx 网关模型别名双向交叉检查",
        category="🧰 工具集 (Utilities)",
        target=("python3", "<ws>/bin/delegation-alias-check.py"),
        arg_attr="delegation_alias_check_args",
        example="--json",
    ),
]
