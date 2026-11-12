#!/usr/bin/env python3
"""根常量深度扫描器 — 检测 `bin/**` 里「根常量少算一级」的路径缺陷。

用法:
  python3 bin/gac/path-dependency-scan.py            # 扫描 bin/**, 有命中 exit 1
  python3 bin/gac/path-dependency-scan.py --json
  python3 bin/gac/path-dependency-scan.py --path bin/gac

## 判据

`bin/<subdir>/x.py` 里这样的写法:

    REPO = Path(__file__).resolve().parents[1]
    REPO / ".omo" / "state" / ...

`parents[1]` 是 `<root>/bin`，不是 workspace 根（`parents[2]` 才是）。于是
`REPO / ".omo" / ...` 全部落到 `<root>/bin/.omo/` —— 2026-11-13 实测那里真有
脚本写出的状态文件，且写入方与读取方用不同的根（一个 `parents[1]`、一个 marker
探测），**两边各自自洽、永不相交、没有任何一侧报错**。

所以判据是两条同时成立:
1. 某个模块级常量由 `Path(__file__).resolve().parents[K]`（或 N 个链式 `.parent`，
   等价 `parents[N-1]`）定义；
2. 该常量随后被 `/` 拼上**根相对 marker**（`.omo` / `docs` / `projects` /
   `tests` / `runtime` / `config` / `kos` / `scripts` / `bin` / 根级文档）。

命中即 `K != 该文件到 workspace 根的层数`。

**为什么不用「出现 `parents[1]` 就报」**：本文件的前身正是那么做的，还额外把
`"bin"` / `'bin'` 字符串字面量也算命中 —— 读数 219 个文件、恒红、于是永远不会被
接进门禁（实测它当时零调用点）。`bin/gac/x.py` 里 `parents[1] / "lib"` 是**正确的**
（`bin/lib`），`bin/ssot/x.py` 里 `parents[1] / "ssot"` 也是正确的 —— blanket
匹配把合法写法一起报，判据就废了。精确判据在 2026-11-13 的 main 上读数 **0**。

SSOT: 本文件即判据；用例 `tests/unit/test_bin_root_constant_depth.py`（自证 + 反过宽）。
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
BIN_DIR = WORKSPACE / "bin"

# 根相对 marker: 这些前缀只会出现在「workspace 根」之下的路径里。
# 不含 `lib` / `ssot` / `gac` 等 —— 那些是 `bin/` 的相对子目录, 是合法用法。
ROOT_MARKERS = frozenset(
    {
        ".omo",
        "docs",
        "projects",
        "tests",
        "runtime",
        "config",
        "kos",
        "scripts",
        "bin",
        "Makefile",
        "ARCHITECTURE.md",
        "AGENTS.md",
        "CLAUDE.md",
        "GOVERNANCE.md",
        "README.md",
    }
)

# 归档面是休眠代码, 不参与判据 (改了也不该拦门禁)。
EXCLUDED_PARTS = frozenset({"__pycache__", "_archive"})


def resolve_root_k(expr: ast.expr) -> int | None:
    """若 expr 等价于 `Path(__file__).resolve().parents[K]` 则返回 K, 否则 None。

    也接受 N 个链式 `.parent` —— 语义是 `parents[N-1]`（`.parent` 一次是文件所在目录）。
    """
    node = expr
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "parents"
    ):
        sl = node.slice
        if not (isinstance(sl, ast.Constant) and isinstance(sl.value, int)):
            return None
        k = sl.value
        node = node.value.value
    else:
        k = -1
        cur = node
        while isinstance(cur, ast.Attribute) and cur.attr == "parent":
            k += 1
            cur = cur.value
        if k < 0:
            return None
        node = cur

    # 剥掉 `.resolve()`
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "resolve":
        node = node.func.value
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Path"
        and node.args
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "__file__"
    ):
        return k
    return None


def _display_path(py: Path, base: Path) -> str:
    """优先相对 `base`，跨树（合成样本）时退化为绝对路径而不是抛错。"""
    try:
        return str(py.relative_to(base))
    except ValueError:
        return str(py)


def scan(root: Path = BIN_DIR, markers: frozenset[str] = ROOT_MARKERS) -> list[dict]:
    """扫描 `root` 下所有 `*.py`, 返回根深度算错的站点列表。

    `file` 字段相对 `root.parent`（即扫描根的父目录，例如 `<ws>/bin` → `bin/gac/x.py`），
    这样同一把尺既能扫真实检出、也能扫测试注入的合成树。
    """
    hits: list[dict] = []
    display_base = root.parent
    for py in sorted(root.rglob("*.py")):
        if EXCLUDED_PARTS & set(py.parts):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue

        # 只取**模块级**赋值 —— 函数/循环里的同名变量会让 blanket 匹配误报。
        depths: dict[str, int] = {}
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                k = resolve_root_k(node.value)
                if k is not None:
                    depths[node.targets[0].id] = k
        if not depths:
            continue

        required = len(py.relative_to(root).parts)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
                continue
            left, right = node.left, node.right
            if not (
                isinstance(left, ast.Name)
                and left.id in depths
                and isinstance(right, ast.Constant)
                and isinstance(right.value, str)
            ):
                continue
            if right.value.split("/")[0] not in markers:
                continue
            found = depths[left.id]
            if found != required:
                hits.append(
                    {
                        "file": _display_path(py, display_base),
                        "line": node.lineno,
                        "constant": left.id,
                        "found_k": found,
                        "required_k": required,
                        "joined": right.value,
                    }
                )
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="根常量深度扫描器 (根少算一级 → 路径落 `<root>/bin/...`)")
    parser.add_argument("--path", default=str(BIN_DIR), help="要扫描的根目录 (默认 bin)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"ERROR: 扫描目录不存在: {root}", file=sys.stderr)
        return 2

    hits = scan(root)
    if args.json:
        print(json.dumps({"root": str(root), "hits": hits}, ensure_ascii=False, indent=2))
    else:
        if not hits:
            print(f"✅ 未发现根常量深度错误（扫描 {root} 下 {len(list(root.rglob('*.py')))} 个 .py）")
            return 0
        print(f"🔴 发现 {len(hits)} 处根常量深度错误:")
        for h in hits[:40]:
            print(
                f"  {h['file']}:{h['line']}  {h['constant']} = parents[{h['found_k']}] "
                f"(应为 parents[{h['required_k']}])  → / {h['joined']}"
            )
        if len(hits) > 40:
            print(f"  ... 及其他 {len(hits) - 40} 处")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
