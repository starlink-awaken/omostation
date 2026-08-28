#!/usr/bin/env python3
"""~/Documents/_inbox 目录多域文件扫描器"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

def scan_inbox(inbox_root: Path | None = None) -> list[dict]:
    root = inbox_root or Path("/Users/xiamingxing/Documents/_inbox")
    events = []
    if not root.exists():
        return events
    for path in root.rglob("*"):
        if path.is_file() and not path.name.startswith("."):
            events.append({
                "entity_id": f"evt-{uuid.uuid4().hex[:8]}",
                "domain": "p1_health" if "health" in str(path) else "p0_work",
                "source": "local_file",
                "file_path": str(path),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
    return events

if __name__ == "__main__":
    print(json.dumps(scan_inbox(), ensure_ascii=False, indent=2))
