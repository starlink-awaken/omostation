#!/usr/bin/env python3
"""Lighthouse CI 采集 stub.

待真实接入后替换为实际 lighthouse-ci 采集逻辑。
当前输出占位数据，使 perception-coverage 可计算 partial 覆盖。
"""
import json
import sys

result = {
    "status": "stub",
    "performance": 0,
    "accessibility": 0,
    "best_practices": 0,
    "seo": 0,
    "note": "lighthouse-ci 未配置，待接入"
}
print(json.dumps(result, ensure_ascii=False))
sys.exit(0)
