#!/usr/bin/env python3
"""NFR (非功能性需求) 指标 stub.

待真实接入后替换为实际 NFR 采集逻辑。
"""
import json
import sys

result = {
    "status": "stub",
    "nfr_score": 0,
    "availability": 0,
    "reliability": 0,
    "scalability": 0,
    "note": "NFR 指标未配置，待接入"
}
print(json.dumps(result, ensure_ascii=False))
sys.exit(0)
