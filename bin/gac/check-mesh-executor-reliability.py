#!/usr/bin/env python3
"""CR-X4-MESH-EXECUTOR-RELIABILITY: 检查 mesh executor 脚本可靠性.

mesh executor 脚本必须有: 超时控制 (timeout/retry), 错误处理 (try/except),
日志记录 (logging). 防止 iris→mesh 自动化管道无声失败.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 检查的目录
CHECK_DIRS = ["bin", "scripts"]

# 可靠性模式
REQUIRED_PATTERNS = {
    "error_handling": {
        "keywords": ["try:", "except", "try/except", "raise"],
        "label": "错误处理 (try/except)",
    },
    "timeout_control": {
        "keywords": ["timeout", "TIMEOUT", "retry", "RETRY", "socket.setdefaulttimeout"],
        "label": "超时控制 (timeout/retry)",
    },
    "logging": {
        "keywords": ["logging.", "logger.", "print(", "log."],
        "label": "日志记录 (logging/print)",
    },
}


def main() -> int:
    violations = []

    for check_dir in CHECK_DIRS:
        d = REPO_ROOT / check_dir
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if not f.is_file() or f.suffix not in (".py", ".sh"):
                continue
            rel = f.relative_to(REPO_ROOT)
            if ".venv" in rel.parts or "__pycache__" in rel.parts:
                continue

            # 只检查名字包含 mesh/executor/iris 的脚本
            name = f.name.lower()
            if not any(kw in name for kw in ["mesh", "executor", "iris", "dispatch"]):
                continue

            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            missing = []
            for key, pat in REQUIRED_PATTERNS.items():
                if not any(kw in text for kw in pat["keywords"]):
                    missing.append(pat["label"])

            if missing:
                violations.append(f"  {rel} — 缺少: {', '.join(missing)}")

    if violations:
        print(f"FAIL 发现 {len(violations)} 个脚本缺少可靠性模式:")
        for v in violations:
            print(v)
        return 1

    print("OK 所有 mesh 相关脚本具备基本可靠性模式")
    return 0


if __name__ == "__main__":
    sys.exit(main())
