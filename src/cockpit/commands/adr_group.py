"""cockpit.commands.adr_group — adr flat 组薄委派 (Phase B2).

``cockpit adr-<tool> [args...]`` 原样透传给 ``bin/adr/`` 下对应脚本。
多数脚本以 cwd 相对路径定位 ``.omo/_knowledge/decisions``, 故 handler 在
workspace 根目录执行; next-adr-id 只建议不 claim (low risk), claim 需显式参数。
"""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Callable

from cockpit.commands import delegation
from cockpit.commands.delegation import DelegatedSpec

CATEGORY = "🛡️ 治理工具 (Governance Tools)"

SPECS: list[DelegatedSpec] = [
    DelegatedSpec(
        name="adr-coverage",
        summary="ADR 覆盖率校验: 编号连续性、frontmatter 完整性、INDEX.md 引用与重复编号检测",
        category=CATEGORY,
        target=("python3", "<ws>/bin/adr/adr-coverage.py"),
        arg_attr="adr_coverage_args",
        example="--strict",
    ),
    DelegatedSpec(
        name="adr-drift-check",
        summary="ADR 漂移检测: ADR 引用的 .omo 路径 / bin 工具 / ADR-XXXX 编号是否存在",
        category=CATEGORY,
        target=("python3", "<ws>/bin/adr/adr-drift-check.py"),
        arg_attr="adr_drift_check_args",
        example="--json",
    ),
    DelegatedSpec(
        name="adr-drift-classify",
        summary="ADR 漂移归类: 区分历史预期 (P28-P49 archived) 与新增待修 issue, 可出 markdown 报告",
        category=CATEGORY,
        target=("python3", "<ws>/bin/adr/adr-drift-classify.py"),
        arg_attr="adr_drift_classify_args",
        example="--report",
    ),
    DelegatedSpec(
        name="adr-drift-auto-fix",
        summary="ADR 漂移自动分类与修复建议 (TEMPLATE/ASPIRATIONAL/SUBDIR_MISSING/REAL_BUG/TYPO)",
        category=CATEGORY,
        target=("python3", "<ws>/bin/adr/adr-drift-auto-fix.py"),
        arg_attr="adr_drift_auto_fix_args",
        example="--json",
        risk="medium",
    ),
    DelegatedSpec(
        name="adr-drift-apply",
        summary="应用 ADR 漂移修复: 对 SUBDIR_MISSING 类型 touch 占位文件 (支持 --dry-run)",
        category=CATEGORY,
        target=("python3", "<ws>/bin/adr/adr-drift-apply.py"),
        arg_attr="adr_drift_apply_args",
        example="--dry-run",
        risk="medium",
    ),
    DelegatedSpec(
        name="adr-frontmatter-backfill",
        summary="补齐历史 ADR 的 id: ADR-NNNN frontmatter (幂等; --strict 可作 CI 门)",
        category=CATEGORY,
        target=("python3", "<ws>/bin/adr/adr-frontmatter-backfill.py"),
        arg_attr="adr_frontmatter_backfill_args",
        example="--dry-run",
        risk="medium",
    ),
    DelegatedSpec(
        name="adr-trend-insight",
        summary="ADR 趋势洞察: 数量增长曲线、引用健康度趋势、top modified 与 frontmatter 完整度",
        category=CATEGORY,
        target=("python3", "<ws>/bin/adr/adr-trend-insight.py"),
        arg_attr="adr_trend_insight_args",
        example="--json",
    ),
    DelegatedSpec(
        name="adr-next-id",
        summary="建议 (可用 --claim 原子认领) 下一个空闲 ADR 编号, flock 防并发双分配",
        category=CATEGORY,
        target=("python3", "<ws>/bin/adr/next-adr-id.py"),
        arg_attr="adr_next_id_args",
        example="--json",
    ),
]


def register(
    sub: object,
    workspace_parser: object,
) -> dict[str, Callable[[argparse.Namespace], int]]:
    """覆盖默认 handler: 组内脚本以 cwd 相对路径定位 .omo/, 须在 workspace 根执行."""
    root = str(delegation.workspace_root())
    handlers: dict[str, Callable[[argparse.Namespace], int]] = {}
    for spec in SPECS:
        def handler(ns: argparse.Namespace, _spec: DelegatedSpec = spec) -> int:
            passthrough = list(getattr(ns, _spec.arg_attr, []) or []) or ["--help"]
            return subprocess.call(
                delegation.resolve_target(_spec.target) + passthrough,
                cwd=root,
                env=delegation.clean_env(),
            )

        handler.__name__ = f"cmd_{spec.name.replace('-', '_')}"
        handler.__doc__ = f"薄委派 (cwd=ws) → {' '.join(spec.target)}"
        handlers[spec.name] = handler
    return handlers
