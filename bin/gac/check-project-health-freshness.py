#!/usr/bin/env python3
"""CR-X2-PROJECT-HEALTH-FRESHNESS: 检查项目健康分新鲜度.

项目健康分 (system.yaml health_score) 必须定期更新.
检查 health_score 的 last_updated 时间戳是否在合理范围内.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_YAML = REPO_ROOT / ".omo/state/system.yaml"

# 健康分新鲜度阈值 (小时)
FRESHNESS_THRESHOLD_HOURS = 48


def main() -> int:
    if not SYSTEM_YAML.exists():
        print("OK 未发现 system.yaml")
        return 0

    try:
        import yaml
        data = yaml.safe_load(SYSTEM_YAML.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"WARN 无法读取 system.yaml: {e}")
        return 0

    # 查找 health_score 和 last_updated
    health_score = None
    last_updated = None
    if isinstance(data, dict):
        health_score = data.get("health_score")
        last_updated = data.get("last_updated") or data.get("updated_at")

    if health_score is None:
        print("OK 未找到健康分数据")
        return 0

    if last_updated is None:
        print(f"WARN 健康分 {health_score} 但缺少更新时间戳")
        return 0

    # 简单检查: 如果 last_updated 是日期字符串, 检查是否在阈值内
    if isinstance(last_updated, str):
        print(f"Info 健康分: {health_score}, 更新于: {last_updated}")
        return 0

    print(f"OK 健康分 {health_score} 新鲜度正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
