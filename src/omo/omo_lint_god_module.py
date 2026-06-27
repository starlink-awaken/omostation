"""omo_lint_god_module — 单文件行数硬规则 (TASK-F7114ABA 锁定).

任务: TASK-F7114ABA P1 GodModule 治本.
机制: 扫 projects/*/src/**/*.py 单文件行数, 超过阈值:
  - 600L: warn (软引导拆解, 与现有 P101 yaml-bypass 一致)
  - 800L: error (硬规则, pre-commit/CI 挂红, 强制拆解)

豁免:
  - 显式 allowlist (历史合理大文件, 例: Pydantic schema 列表)
  - tests/ (测试文件可以超)
  - 本 lint 自身 (元治理递归)

向后兼容 (P101 模式):
  omo_lint.py 通过 `from .omo_lint_god_module import (...)` re-export,
  保持 `from omo.omo_lint import cmd_lint_god_module` 不破.
"""

from __future__ import annotations

from pathlib import Path

OMO_SRC = Path(__file__).resolve().parent
WORKSPACE_ROOT = OMO_SRC.parents[3]  # /Users/xiamingxing/Workspace

# 阈值 (L0:X4 锁定, TASK-F7114ABA deliverable: "单文件>800L 触发 lint-error 硬规则")
WARN_LOC = 600
ERROR_LOC = 800

# 豁免: 显式 allowlist (历史合理大文件, 需在 ADR 记录理由)
# 当前为空 — 任何 >800L 文件应主动拆分, 不入豁免.
GOD_MODULE_ALLOWLIST: set[str] = set()

# 不扫的目录 (测试/数据迁移脚本可超)
EXCLUDE_DIR_PARTS: tuple[str, ...] = (
    "tests",
    "test_",
    "__pycache__",
    ".venv",
    "node_modules",
    "_archive",
    "demo",
    "fixtures",
)


def _collect_python_files(workspace_root: Path) -> list[Path]:
    """扫所有 projects/*/src/**/*.py + bin/*.py."""
    files: list[Path] = []
    for src_root in workspace_root.glob("projects/*/src"):
        if not src_root.is_dir():
            continue
        files.extend(src_root.rglob("*.py"))
    # bin/ 是 workspace-level tools (例 ssot-guardian)
    bin_dir = workspace_root / "bin"
    if bin_dir.is_dir():
        files.extend(p for p in bin_dir.glob("*.py"))
    return files


def _is_excluded(path: Path) -> bool:
    parts = path.parts
    return any(part in EXCLUDE_DIR_PARTS for part in parts)


def _line_count(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    # 物理行数 (与 wc -l 一致); blank-only 文件不算 0 而是其真实行数 (罕见)
    return sum(1 for _ in text.splitlines())


def check_god_module(workspace_root: str = ".") -> dict:
    """扫所有 python 文件, 报告 warn (>600L) + error (>800L).

    Returns:
        dict with keys: warn_files, error_files, total_scanned, by_module.
    """
    root = Path(workspace_root).resolve()
    files = _collect_python_files(root)
    files = [f for f in files if not _is_excluded(f)]

    warn_files: list[tuple[Path, int]] = []
    error_files: list[tuple[Path, int]] = []
    by_module: dict[str, int] = {}  # module_name → max LOC

    for path in files:
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        # 转 module name 形式 (workspace.brain.kairon.path)
        rel_str = str(rel).replace("/", ".").replace(".py", "")
        if path.name == "__init__.py":
            continue
        loc = _line_count(path)
        if loc == 0:
            continue

        module_key = rel_str
        by_module[module_key] = max(by_module.get(module_key, 0), loc)

        if str(rel) in GOD_MODULE_ALLOWLIST:
            continue
        if loc > ERROR_LOC:
            error_files.append((path, loc))
        elif loc > WARN_LOC:
            warn_files.append((path, loc))

    return {
        "total_scanned": len(files),
        "warn_files": sorted(warn_files, key=lambda x: -x[1]),
        "error_files": sorted(error_files, key=lambda x: -x[1]),
        "by_module": by_module,
        "warn_threshold": WARN_LOC,
        "error_threshold": ERROR_LOC,
    }


def cmd_lint_god_module(workspace_root: str = ".") -> int:
    """omo lint god-module — 单文件 LOC 硬规则 (TASK-F7114ABA 锁定)."""
    if workspace_root == ".":
        # 默认从 find_omo_dir 找 workspace 根 (cd projects/omo 调用也能解析到 /Users/...)
        root = WORKSPACE_ROOT
    else:
        root = Path(workspace_root).resolve()
    report = check_god_module(str(root))
    warn_n = len(report["warn_files"])
    error_n = len(report["error_files"])
    total = report["total_scanned"]

    print(
        f"=== god-module lint (warn>{report['warn_threshold']}L, "
        f"error>{report['error_threshold']}L) ==="
    )
    print(f"  扫文件: {total}")
    print(f"  warn (>600L): {warn_n}")
    print(f"  error (>800L): {error_n}")

    if error_n:
        print("\n--- error (硬规则, 必须拆解) ---")
        for path, loc in report["error_files"]:
            print(f"  🔴 {path}: {loc}L (>{report['error_threshold']})")
        print(
            f"\n❌ GATE FAIL: {error_n} 个文件 >{report['error_threshold']}L. "
            f"治本: 用 omo-srp-refactor skill 渐进拆解."
        )
        return 1

    if warn_n:
        print("\n--- warn (软引导) ---")
        for path, loc in report["warn_files"][:10]:  # 限制 10 行输出
            print(f"  🟡 {path}: {loc}L (>{report['warn_threshold']})")
        if warn_n > 10:
            print(f"  ... ({warn_n - 10} more)")

    print(
        f"✅ GATE PASS: 0 文件 >{report['error_threshold']}L, "
        f"{warn_n} 文件在 {report['warn_threshold']}-{report['error_threshold']}L 区间."
    )
    return 0


__all__ = [
    "WARN_LOC",
    "ERROR_LOC",
    "GOD_MODULE_ALLOWLIST",
    "check_god_module",
    "cmd_lint_god_module",
]
