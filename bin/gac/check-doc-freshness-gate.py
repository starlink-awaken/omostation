#!/usr/bin/env python3
"""CR-X2-DOC-FRESHNESS-GATE — 文档新鲜度检查. 检查 docs/ 下 md 文件是否在 90 天内更新过."""

import subprocess, sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
STALE_DAYS = 90

def main() -> int:
    cutoff = datetime.now(UTC) - timedelta(days=STALE_DAYS)
    stale = []
    for d in ["docs"]:
        target = WORKSPACE / d
        if not target.exists():
            continue
        r = subprocess.run(["git", "-C", str(WORKSPACE), "ls-files", f"{d}/**/*.md"], capture_output=True, text=True, timeout=10)
        for f in r.stdout.strip().split("\n"):
            if not f:
                continue
            try:
                lr = subprocess.run(["git", "-C", str(WORKSPACE), "log", "-1", "--format=%ct", f], capture_output=True, text=True, timeout=5)
                ts = lr.stdout.strip()
                if ts and datetime.fromtimestamp(int(ts), tz=UTC) < cutoff:
                    stale.append(f)
            except (ValueError, OSError, subprocess.TimeoutExpired):
                pass
    if stale:
        print(f"WARN {len(stale)} 个文档超过 {STALE_DAYS} 天未更新:")
        for f in stale[:20]:
            print(f"  - {f}")
    else:
        print("OK 所有文档均在 90 天内更新")
    return 0

if __name__ == "__main__":
    sys.exit(main())
