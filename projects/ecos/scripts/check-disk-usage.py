#!/usr/bin/env python3
"""
SharedDisk 空间监控 — ecos-daemon 健康检查插件

检查 /Volumes/SharedDisk 使用率, >95% 自动创建 DEBT 卡片。
"""
import json, sqlite3, subprocess, sys
from datetime import datetime
from pathlib import Path

MOUNT = "/Volumes/SharedDisk"
THRESHOLD = 95
CARDS_DB = Path.home() / "Workspace" / "data" / "cards" / "cards.db"

def get_usage() -> dict | None:
    try:
        r = subprocess.run(["df", MOUNT], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return None
        lines = r.stdout.strip().split("\n")
        if len(lines) < 2:
            return None
        parts = lines[1].split()
        if len(parts) < 5:
            return None
        used_pct = int(parts[4].rstrip("%"))
        total = int(parts[1]) * 512
        used = int(parts[2]) * 512
        free = int(parts[3]) * 512
        return {
            "mount": MOUNT,
            "total_gb": round(total / 1e9, 1),
            "used_gb": round(used / 1e9, 1),
            "free_gb": round(free / 1e9, 1),
            "used_pct": used_pct,
        }
    except Exception:
        return None

def create_debt_card(usage: dict) -> bool:
    if not CARDS_DB.exists():
        return False
    now = datetime.now()
    debt_id = f"DEBT-STORAGE-{now.strftime('%Y%m%d')}"
    conn = sqlite3.connect(str(CARDS_DB))
    try:
        conn.execute("""
            INSERT OR IGNORE INTO cards (id, type, status, title, domain, priority, summary, content, created_at, updated_at)
            VALUES (?, 'debt', 'identified', ?, 'infra', 'P1', ?, ?, ?, ?)
        """, (
            debt_id,
            f"SharedDisk 空间告警: {usage['used_pct']}%",
            f"SharedDisk 使用率 {usage['used_pct']}%, 仅剩 {usage['free_gb']}GiB",
            f"## 自动检测\n- 挂载: {MOUNT}\n- 容量: {usage['total_gb']}GiB\n- 已用: {usage['used_gb']}GiB ({usage['used_pct']}%)\n- 剩余: {usage['free_gb']}GiB\n- 阈值: >{THRESHOLD}%\n\n请清理以下目录:\n- 06_Downloads/ (临时文件)\n- 02_Edu_Library/ (可归档旧内容)",
            now.isoformat(),
            now.isoformat(),
        ))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def main():
    usage = get_usage()
    if not usage:
        print(f"⚠️  {MOUNT} 未挂载或不可达")
        # Not mounted — not an error, just skip
        return 0
    
    print(f"  SharedDisk: {usage['used_pct']}% ({usage['free_gb']}GiB free / {usage['total_gb']}GiB total)")
    
    if usage["used_pct"] >= THRESHOLD:
        created = create_debt_card(usage)
        status = "🔴 ALERT" if created else "⚠️  (card exists)"
        print(f"  {status}: {usage['used_pct']}% >= {THRESHOLD}%, {usage['free_gb']}GiB remaining")
        return 1
    
    print(f"  ✅ 正常 ({THRESHOLD - usage['used_pct']}% headroom)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
