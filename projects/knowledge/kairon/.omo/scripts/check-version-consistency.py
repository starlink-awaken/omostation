#!/usr/bin/env python3
"""
Kairon 版本一致性检查器

扫描各包的 pyproject.toml 声明的版本与其源码中 __version__ 是否一致。
支持 hatch 动态版本 ([tool.hatch.version] path)。

用法:
    python3 .omo/scripts/check-version-consistency.py [packages/目录]

返回码:
    0  = 全部一致（或 SKIP 包）
    1  = 存在不一致
"""

import re
import sys
import tomllib
from pathlib import Path

PACKAGES_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("packages")
IGNORE_PKGS: set[str] = set()  # 显式忽略的包


def find_init_version(pkg_dir: Path, pkg_name: str) -> str | None:
    """在包的 src/ 目录下寻找 __init__.py 中的 __version__ 定义。"""
    src_dir = pkg_dir / "src"
    if not src_dir.is_dir():
        return None

    # 遍历 src/ 下的一级子目录（模块目录）
    for entry in sorted(src_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("__"):
            continue
        init = entry / "__init__.py"
        if init.is_file():
            content = init.read_text(encoding="utf-8")
            for line in content.splitlines():
                m = re.match(r'^__version__\s*=\s*["\']([^"\']+)["\']', line)
                if m:
                    return m.group(1)
    return None


def get_pyproject_version(pkg_dir: Path) -> str | None:
    """从 pyproject.toml 读取版本。"""
    pyproject_file = pkg_dir / "pyproject.toml"
    if not pyproject_file.is_file():
        return None

    with open(pyproject_file, "rb") as f:
        data = tomllib.load(f)

    # 直接声明 version
    project = data.get("project", {})
    if "version" in project:
        return str(project["version"])

    # Hatch 动态版本
    hatch = data.get("tool", {}).get("hatch", {})
    if "version" in hatch:
        path_rel = hatch["version"].get("path", "")
        if path_rel:
            path_abs = pkg_dir / path_rel
            if path_abs.is_file():
                content = path_abs.read_text(encoding="utf-8").strip()
                return content

    # 如果 version 是动态的 (dynamic = ["version"])
    dynamic = project.get("dynamic", [])
    if "version" in dynamic:
        return "<dynamic>"

    return None


def format_result(pkg_name: str, pyproject_ver: str | None, init_ver: str | None) -> str:
    """格式化单个包的版本结果。"""
    status = "✓" if (pyproject_ver and init_ver and pyproject_ver == init_ver) else "✗"
    parts = [
        f"{status} {pkg_name:25s}",
        f"pyproject: {pyproject_ver or 'N/A':15s}",
        f"__init__: {init_ver or 'N/A':15s}",
    ]
    if init_ver is None:
        parts.append("(src/ 中无 __version__)")
    elif pyproject_ver is None:
        parts.append("(pyproject.toml 中无 version)")
    elif pyproject_ver != init_ver:
        parts.append("⚠ MISMATCH")
    return "  ".join(parts)


def main() -> int:
    errors = 0
    total = 0
    skipped = 0

    pkg_dirs = sorted(d for d in PACKAGES_DIR.iterdir() if d.is_dir() and not d.name.startswith("."))

    print("=" * 72)
    print(f"Kairon 版本一致性检查 — {PACKAGES_DIR.resolve()}")
    print(f"总计 {len(pkg_dirs)} 个包")
    print("=" * 72)
    print()

    for pkg_dir in pkg_dirs:
        pkg_name = pkg_dir.name

        if pkg_name in IGNORE_PKGS:
            skipped += 1
            continue

        total += 1

        pyproject_ver = get_pyproject_version(pkg_dir)
        init_ver = find_init_version(pkg_dir, pkg_name)

        line = format_result(pkg_name, pyproject_ver, init_ver)
        print(line)

        if pyproject_ver and init_ver and pyproject_ver != init_ver:
            errors += 1

    print()
    print("=" * 72)
    print(f"结果: {total} 检查, {errors} 不一致, {skipped} 跳过")
    if errors:
        print("状态: ❌ 未通过")
    else:
        print("状态: ✅ 全部一致")
    print("=" * 72)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
