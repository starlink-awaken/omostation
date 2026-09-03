"""cockpit.commands.gac_group — gac nested 组薄委派 (Phase B1).

``cockpit gac <sub> [args...]`` 原样透传给 ``bin/gac/`` 下对应脚本;
裸 ``cockpit gac`` 保持原行为 (gac-healthcheck)。
"""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Callable
from pathlib import Path

from cockpit.commands import delegation

# 真实 workspace 根: delegation._WS_ROOT 在已安装布局下会误判 (算出 projects/),
# 这里锚定 workspace 根: commands/ 比 cli.py 深一层, 故 parents[5] ≡ cli.py parents[4].
_GAC_WS_ROOT = Path(__file__).resolve().parents[5]

# 子命令 → (target argv, 中文说明); <ws> 占位符由 delegation.resolve_target 解析
GAC_SUBCOMMANDS: dict[str, tuple[tuple[str, ...], str]] = {
    "drift": (
        ("python3", "<ws>/bin/gac/gac-drift.py"),
        "GaC drift 检测 (governance-checks.yaml 声明 vs 执行漂移)",
    ),
    "validate": (
        ("python3", "<ws>/bin/gac/gac-validate.py"),
        "GaC 规则注册表结构与元数据校验",
    ),
    "arch-drift": (
        ("python3", "<ws>/bin/gac/architecture-drift.py"),
        "架构漂移检测 (代码 vs ARCHITECTURE 声明)",
    ),
    "pre-pr": (
        ("python3", "<ws>/bin/gac/pre-pr-check.py"),
        "Pre-PR sanity checklist (提交前快速自检)",
    ),
    "ci-fast": (
        ("python3", "<ws>/bin/gac/ci-local-fast.py"),
        "本地快速 CI 门 (ruff/测试等, 保留生产者退出码)",
    ),
    "coverage": (
        ("python3", "<ws>/bin/gac/gac-coverage-lint.py"),
        "声明即执行覆盖率检查 (治理声明面 vs 执行面休眠)",
    ),
    "hygiene": (
        ("python3", "<ws>/bin/gac/gac-hygiene-check.py"),
        "工作区卫生检查 (GaC CR-HYG-01/02)",
    ),
    "readiness": (
        ("python3", "<ws>/bin/gac/governance-readiness.py"),
        "治理就绪度检查 (.omo 目录)",
    ),
}


def dispatch_gac_group(args: argparse.Namespace) -> int:
    """gac 组统一分发: 裸命令走 gac-healthcheck, 子命令透传下游脚本."""
    sub_name = getattr(args, "gac_command", None)
    if not sub_name:
        # 裸 `cockpit gac`: 复现 cli.py cmd_gac 原行为
        root = _GAC_WS_ROOT
        r = subprocess.run(
            ["python3", str(root / "bin" / "gac" / "gac-healthcheck.py")],
            capture_output=True,
            text=True,
            cwd=str(root),
        )
        print(r.stdout or r.stderr or "(无输出)")
        return 0 if r.returncode == 0 else 1
    target, desc = GAC_SUBCOMMANDS[sub_name]
    passthrough = list(getattr(args, "gac_pass_args", []) or [])
    # help 拦截: --help/-h/空参 → 壳层输出用法引导 (部分下游脚本误处理 --help
    # 会直接跑检查, 如 coverage/readiness); 统一壳层帮助保证一致性
    if not passthrough or passthrough[0] in ("--help", "-h"):
        print(f"用法: cockpit gac {sub_name} [args...]\n说明: {desc}\n下游: {' '.join(target)}")
        return 0
    resolved = [str(_GAC_WS_ROOT / a[len("<ws>/"):]) if a.startswith("<ws>/") else a for a in target]
    return subprocess.call(resolved + passthrough, env=delegation.clean_env())


def register(sub: argparse._SubParsersAction, workspace_parser: type[argparse.ArgumentParser]) -> dict[str, Callable[[argparse.Namespace], int]]:
    """挂载 gac 子命令 parser; 返回覆盖 cli.py cmd_gac 的组 handler."""
    gac_parser = sub.choices["gac"]
    gac_sub = gac_parser.add_subparsers(dest="gac_command")
    for name, (_, summary) in GAC_SUBCOMMANDS.items():
        p = gac_sub.add_parser(name, add_help=False, help=summary)
        p.add_argument(
            "gac_pass_args",
            nargs=argparse.REMAINDER,
            help="透传给下游脚本的参数 (空 = 显示下游 --help)",
        )
        p.set_defaults(gac_command=name)
    # 使 `cockpit gac drift --help` 前导 --help 被回收透传
    delegation.EXISTING_REMAINDER_DELEGATIONS.setdefault("gac", "gac_pass_args")
    return {"gac": dispatch_gac_group}
