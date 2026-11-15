"""每个 `gac-worktree.sh <子命令>` 的调用点都必须落在真实存在的派发分支上。

契约来源：2026-09-28 的 PR #4513（`23417b502`）把 `gac-worktree.sh` 派发 `case` 里的
`guard-submodules)` **替换**成 `release-diagnose)`（不是新增）。此后
`.githooks/post-checkout` 的 `guard-submodules --fix` 一直落进 `*)` 打用法再
`exit 1`，被 `|| true` 吞掉 —— 守卫空转 7 周（2026-11-16 #5373 修复）。

为什么现有测试没拦住: `tests/unit/test_gac_guard_submodules.py` 的用例从生产脚本
**抽取函数体直接调**，绕过了 CLI 派发。本文件是**静态接线检查**: 扫全仓调用点,
断言子命令在派发 `case` 里存在 —— 它不需要运行守卫, 只问「这个入口还在不在」。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "gac-worktree.sh"

SCAN_ROOTS = (
    ".githooks",
    "bin",
    "lib",
    "tests",
    "Makefile",
    ".omo/cron/registry.yaml",
    "projects/omo/src",
    ".github/workflows",
)
SCAN_SUFFIXES = {".sh", ".py", ".yaml", ".yml"}

DISPATCH_RE = re.compile(r"^  ([a-z][a-z0-9-]*)\)", re.M)
INVOCATION_RE = re.compile(r"gac-worktree\.sh[\"']?\s+([a-z][a-z0-9-]*)")
# 「命令位置」标记。刻意**不写 `\bsh\b`** —— `gac-worktree.sh` 自己的 `.sh`
# 就满足 `\bsh\b`（点与空白都是词边界），于是每一条提及都会被判成调用点。
COMMAND_POSITION_RE = re.compile(r"(?:\bbash\b|\bpc_run_stage\b|\$\()")


def dispatched_subcommands(script_text: str) -> set[str]:
    return set(DISPATCH_RE.findall(script_text))


def _scan_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in SCAN_ROOTS:
        path = root / rel
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            # `.githooks/*` 没有后缀（post-checkout / pre-commit …），必须全收
            if rel == ".githooks":
                files.extend(p for p in path.rglob("*") if p.is_file())
            else:
                files.extend(p for p in path.rglob("*") if p.is_file() and p.suffix in SCAN_SUFFIXES)
    return files


def scan_invocations(root: Path = ROOT) -> list[tuple[str, int, str]]:
    """返回 (相对路径, 行号, 子命令) —— 只收**命令位置**上的提及。"""
    hits: list[tuple[str, int, str]] = []
    for path in _scan_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith(("#", "-", "*", "|", ">")):
                continue
            if not (COMMAND_POSITION_RE.search(line) or stripped.startswith("gac-worktree.sh")):
                continue
            for match in INVOCATION_RE.finditer(line):
                hits.append((str(path.relative_to(root)), lineno, match.group(1)))
    return hits


def test_all_invocations_use_dispatched_subcommands() -> None:
    dispatched = dispatched_subcommands(SCRIPT.read_text(encoding="utf-8"))
    assert dispatched, "派发表抽取失败 —— 检测器空转"
    bad = sorted({hit for hit in scan_invocations() if hit[2] not in dispatched})
    assert bad == [], "这些调用点指向不存在的子命令: " + "; ".join(f"{f}:{n} ({s})" for f, n, s in bad)


def test_detector_catches_undispatched_invocation(tmp_path: Path) -> None:
    """自证: 注入一个不存在的子命令，检测器必须报出来（否则它是空绿的）。"""
    fake_root = tmp_path / "repo"
    (fake_root / "bin" / "gac").mkdir(parents=True)
    (fake_root / "bin" / "gac" / "gac-worktree.sh").write_text(
        "case \"$1\" in\n  claim)\n    ;;\n  *)\n    echo usage\n    ;;\nesac\n",
        encoding="utf-8",
    )
    hook = fake_root / ".githooks"
    hook.mkdir()
    (hook / "post-checkout").write_text(
        'bash "$ROOT/bin/gac/gac-worktree.sh" guard-submodules --fix || true\n',
        encoding="utf-8",
    )
    (fake_root / "Makefile").write_text(
        "\tbash bin/gac/gac-worktree.sh cleanup\n", encoding="utf-8"
    )
    # 建议文本（非命令位置）里的提及不算调用点
    (fake_root / "README.md").write_text("跑 gac-worktree.sh no-such-subcommand 即可\n", encoding="utf-8")

    dispatched = dispatched_subcommands(
        (fake_root / "bin" / "gac" / "gac-worktree.sh").read_text(encoding="utf-8")
    )
    hits = scan_invocations(fake_root)
    subs = {sub for _f, _n, sub in hits}
    assert "cleanup" in subs, hits
    assert "guard-submodules" in subs, hits
    assert "no-such-subcommand" not in subs, "建议文本被误当成调用点"
    assert "guard-submodules" not in dispatched
