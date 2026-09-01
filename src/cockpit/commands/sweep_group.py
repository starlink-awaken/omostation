"""cockpit.commands.sweep_group — bin/sweep 代码质量工具链薄委派 (Phase B3).

flat 组: 每个脚本一条 DelegatedSpec, --help 由下游 CLI 透传.
源脚本契约见 workspace `bin/sweep/README.md` (ADR-0367 / ADR-0373).
"""

from __future__ import annotations

from cockpit.commands.delegation import DelegatedSpec

SPECS: list[DelegatedSpec] = [
    DelegatedSpec(
        name="sweep-ruff",
        summary="对指定路径执行有界 ruff 安全修复循环（默认 3 轮收敛）",
        category="🧹 代码质量 (Code Quality)",
        target=("python3", "<ws>/bin/sweep/ruff.py"),
        arg_attr="sweep_ruff_args",
        example="cockpit sweep-ruff projects/kairon --max-rounds 1",
    ),
    DelegatedSpec(
        name="sweep-pyright",
        summary="从 pyright JSON 诊断报告施加显式抑制（支持 --package 过滤与 --dry-run）",
        category="🧹 代码质量 (Code Quality)",
        target=("python3", "<ws>/bin/sweep/pyright.py"),
        arg_attr="sweep_pyright_args",
        example="cockpit sweep-pyright /tmp/pyright.json --package kairon --dry-run",
    ),
    DelegatedSpec(
        name="sweep-scan",
        summary="全仓或 diff 模式 pyright 扫描并归档抑制指标报告到 .omo/_knowledge/sweeps/",
        category="🧹 代码质量 (Code Quality)",
        target=("python3", "<ws>/bin/sweep/scan.py"),
        arg_attr="sweep_scan_args",
        example="cockpit sweep-scan --diff-mode --strict",
    ),
    DelegatedSpec(
        name="sweep-nested-with",
        summary="合并可证明安全的嵌套 with 语句（SIM117 结构改写，AST 解析兜底）",
        category="🧹 代码质量 (Code Quality)",
        target=("python3", "<ws>/bin/sweep/nested-with.py"),
        arg_attr="sweep_nested_with_args",
        example="cockpit sweep-nested-with projects/kairon --dry-run",
    ),
]
