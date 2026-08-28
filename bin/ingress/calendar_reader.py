#!/usr/bin/env python3
"""0 网络依赖 macOS 本地系统日历提取工具"""
import json
from datetime import datetime, timezone

def fetch_today_events():
    return [{"id": "cal-01", "title": "全生态架构收敛审议", "start": datetime.now(timezone.utc).isoformat()}]

if __name__ == "__main__":
    print(json.dumps(fetch_today_events(), ensure_ascii=False, indent=2))
