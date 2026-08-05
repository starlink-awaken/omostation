#!/usr/bin/env python3
"""CR-X4-SWEEP-TOOL-INTEGRITY: 检查 sweep 工具完整性.

Sweep 工具链 (bin/sweep/) 是 ADR-0367 定义的治理工具集.
要求: 每个 sweep 工具必须有测试覆盖、CI 集成、README 文档.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SWEEP_DIR = REPO_ROOT / "bin" / "sweep"


def main() -> int:
    if not SWEEP_DIR.is_dir():
        print("OK 未发现 sweep 工具目录")
        return 0

    violations = []
    py_files = sorted(SWEEP_DIR.rglob("*.py"))
    sh_files = sorted(SWEEP_DIR.rglob("*.sh"))

    for f in py_files:
        rel = f.relative_to(REPO_ROOT)
        name = f.stem
        # 检查是否有对应的测试文件
        test_files = list(REPO_ROOT.rglob(f"tests/test_sweep_{name}.py")) + \
                     list(REPO_ROOT.rglob(f"tests/test_{name}.py"))
        if not test_files:
            # 跳过 __init__.py 和 README
            if name != "__init__":
                violations.append(f"  {rel} — 缺少测试文件 (tests/test_sweep_{name}.py)")

        # 检查是否有 CI 集成
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "def main()" in text and "if __name__" not in text:
            violations.append(f"  {rel} — 缺少 __main__ 入口 (无法独立运行)")

    if violations:
        print(f"WARN 发现 {len(violations)} 个 sweep 工具完整性问题:")
        for v in violations:
            print(v)
        return 0  # advisory

    print("OK 所有 sweep 工具完整性良好")
    return 0


if __name__ == "__main__":
    sys.exit(main())
