#!/usr/bin/env python3
"""CR-P76-7-5-RESOLVE-NOT-STUB: 检查物理未实现的 placeholder 是否已决议.

物理未实现的 placeholder 必须决议 (要么实现要么标 status), 不留隐含承诺.
检查 0 字节文件、TODO/FIXME/HACK/XXX 在非测试、非生成的治理代码中。
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 跳过目录
SKIP_DIRS = {".venv", "__pycache__", "node_modules", "build", ".git", "_archived", "tests", "test"}
# 治理代码路径 — 这些路径中的 TODO/FIXME 需要被标记
GOVERNED_PATTERNS = [
    re.compile(r"bin/gac/"),
    re.compile(r"bin/ssot/"),
    re.compile(r"bin/mof/"),
    re.compile(r"\.omo/_truth/"),
    re.compile(r"\.omo/standards/"),
    re.compile(r"\.omo/_knowledge/"),
    re.compile(r"\.github/workflows/"),
]

# 需要检查的 stub 模式
STUB_PATTERNS = [
    (re.compile(r"#\s*TODO\b", re.IGNORECASE), "TODO 注释"),
    (re.compile(r"#\s*FIXME\b", re.IGNORECASE), "FIXME 注释"),
    (re.compile(r"#\s*HACK\b", re.IGNORECASE), "HACK 注释"),
    (re.compile(r"#\s*XXX\b"), "XXX 注释"),
    (re.compile(r"#\s*placeholder", re.IGNORECASE), "placeholder 注释"),
    (re.compile(r"raise\s+NotImplementedError"), "NotImplementedError"),
    (re.compile(r"pass\s*#\s*TODO", re.IGNORECASE), "TODO pass"),
]


def is_governed_path(rel: Path) -> bool:
    """检查路径是否属于治理代码范围。"""
    rel_str = str(rel)
    return any(p.search(rel_str) for p in GOVERNED_PATTERNS)


def main() -> int:
    violations = []
    zero_byte_files = []

    # 检查 0 字节文件
    for py_file in sorted(REPO_ROOT.rglob("*.py")):
        rel = py_file.relative_to(REPO_ROOT)
        if any(d in rel.parts for d in SKIP_DIRS):
            continue
        if not is_governed_path(rel):
            continue
        try:
            if py_file.stat().st_size == 0:
                zero_byte_files.append(str(rel))
        except OSError:
            continue

    # 检查 stub 模式
    for py_file in sorted(REPO_ROOT.rglob("*.py")):
        rel = py_file.relative_to(REPO_ROOT)
        if any(d in rel.parts for d in SKIP_DIRS):
            continue
        if not is_governed_path(rel):
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for pattern, label in STUB_PATTERNS:
            for m in pattern.finditer(text):
                line_num = text[:m.start()].count("\n") + 1
                violations.append(f"  {rel}:{line_num} — {label}: {m.group()[:80]}")

    if zero_byte_files:
        print(f"FAIL 发现 {len(zero_byte_files)} 个 0 字节文件 (需显式内容):")
        for f in zero_byte_files:
            print(f"  - {f}")

    if violations:
        print(f"FAIL 发现 {len(violations)} 处未决议的 stub/placeholder:")
        for v in violations:
            print(v)

    if zero_byte_files or violations:
        return 1

    print("OK 未发现未决议的 stub/placeholder")
    return 0


if __name__ == "__main__":
    sys.exit(main())
