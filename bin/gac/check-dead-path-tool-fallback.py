#!/usr/bin/env python3
"""CR-P76-8-3-DEAD-PATH-TOOL-FALLBACK: 检查工具双路 fallback 模式.

工具检查应该 first-level + projects/*/first-level 双路 fallback.
检查 bin/ 脚本中引用路径时是否同时考虑了项目级路径。
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 双路 fallback 检查 — 需要同时有 root-level 和 project-level 引用的路径模式
DUAL_PATH_PATTERNS = [
    # 检查 .omo/ 路径引用
    (re.compile(r"\.omo/([a-z_/]+)"), ".omo/ 路径"),
    # 检查 protocols/ 路径引用
    (re.compile(r"protocols/([a-z_-]+)"), "protocols/ 路径"),
    # 检查 docs/ 路径引用
    (re.compile(r"docs/([a-z_/]+)"), "docs/ 路径"),
]

# 跳过的路径
SKIP_DIRS = {".venv", "__pycache__", "node_modules", "build", ".git", "_archived", "tests", "test"}

# 允许的仅 root-level 路径模式 (如 CLAUDE.md, AGENTS.md 等根文件)
ALLOWED_ROOT_ONLY = [
    "CLAUDE.md",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "BRIEF.md",
    "CHANGELOG.md",
    "README.md",
    "Makefile",
    "docker-compose.yml",
    "pyproject.toml",
]


def check_dual_path(text: str, rel: Path) -> list:
    """检查脚本中是否有单一路径引用（缺少双路 fallback）。"""
    issues = []
    for pattern, label in DUAL_PATH_PATTERNS:
        matches = pattern.findall(text)
        for m in matches:
            path_ref = m.strip("/")
            if path_ref in ALLOWED_ROOT_ONLY:
                continue
            # 检查是否同时有 root-level 和 project-level 版本
            root_ref = f".omo/{path_ref}" if label == ".omo/ 路径" else f"{path_ref}"
            proj_ref = f"projects/*/{path_ref}"
            # 如果只有 root-level 引用而没有 project-level 引用
            has_root = root_ref in text
            has_proj = bool(re.search(rf"projects/\w+/{path_ref}", text))
            if has_root and not has_proj:
                issues.append(f"  {rel} — {label} '{path_ref}' 仅 root-level 引用, 缺少 projects/*/ fallback")
    return issues


def main() -> int:
    violations = []
    check_dirs = ["bin"]

    for check_dir in check_dirs:
        d = REPO_ROOT / check_dir
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*.py")):
            rel = f.relative_to(REPO_ROOT)
            if any(d in rel.parts for d in SKIP_DIRS):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            violations.extend(check_dual_path(text, rel))

    if violations:
        print(f"FAIL 发现 {len(violations)} 处单一路径引用 (需双路 fallback):")
        for v in violations:
            print(v)
        return 1

    print("OK 所有脚本路径引用均支持双路 fallback")
    return 0


if __name__ == "__main__":
    sys.exit(main())
