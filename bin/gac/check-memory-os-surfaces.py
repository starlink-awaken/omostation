#!/usr/bin/env python3
"""CR-X4-MEMORY-OS-SURFACE-INTEGRITY: 检查 memory-os surface 一致性.

memory-os 新增 phase 必须注册 surface (bin/gac/ 或 .omo/standards/),
禁止无治理覆盖的新 phase.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 已知的 memory-os surface 注册文件
SURFACE_REGISTRIES = [
    REPO_ROOT / "bin" / "gac",
    REPO_ROOT / ".omo" / "standards",
    REPO_ROOT / ".omo" / "_truth" / "registry",
]


def main() -> int:
    # 查找所有 memory-os 相关的文件
    memory_os_files = []
    for f in sorted(REPO_ROOT.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(REPO_ROOT)
        if ".venv" in rel.parts or "__pycache__" in rel.parts or ".git" in rel.parts:
            continue
        name = f.name.lower()
        if "memory-os" in name or "memory_os" in name:
            memory_os_files.append(rel)

    if not memory_os_files:
        print("OK 未发现 memory-os 相关文件")
        return 0

    # 检查是否有对应的 surface 注册
    missing_surfaces = []
    for rel in memory_os_files:
        # 检查是否在 surface 注册目录中
        in_registry = any(
            str(rel).startswith(str(reg.relative_to(REPO_ROOT)))
            for reg in SURFACE_REGISTRIES
        )
        # 检查是否是 docs/ 下的文档 (允许)
        is_doc = str(rel).startswith("docs/")
        # 检查是否是 generated 文件
        is_generated = str(rel).startswith("docs/generated/")

        if not in_registry and not is_doc and not is_generated:
            missing_surfaces.append(str(rel))

    if missing_surfaces:
        print(f"WARN 发现 {len(missing_surfaces)} 个 memory-os 文件无 surface 注册:")
        for v in missing_surfaces:
            print(f"  - {v}")
        print("  建议: 将新 phase 注册到 bin/gac/ 或 .omo/standards/")
        return 0  # advisory only

    print("OK 所有 memory-os 文件已注册 surface")
    return 0


if __name__ == "__main__":
    sys.exit(main())
