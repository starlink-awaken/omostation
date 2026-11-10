#!/usr/bin/env python3
"""CR-X2-PROJECT-HEALTH-FRESHNESS: 检查项目健康分新鲜度.

项目健康分 (system.yaml health_score) 必须定期更新.
检查 health_score 的 last_updated 时间戳是否在合理范围内.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from repo_root import state_file_read  # noqa: E402

# 健康分新鲜度阈值 (小时)
FRESHNESS_THRESHOLD_HOURS = 48


def main() -> int:
    # 读 state 根那份（写者已翻过去），检出快照兜底 —— 解析放在调用时，不冻在 import。
    system_yaml = state_file_read(".omo/state/system.yaml", root=REPO_ROOT)
    if not system_yaml.exists():
        # 缺席 ≠ 通过: 这份文件是 gitignored 运行态, 干净检出里按构造不存在,
        # 旧实现印「OK」会把「判不了」洗成「健康」。
        print(f"WARN 未发现 system.yaml ({system_yaml}) — 无法判定健康分新鲜度")
        return 0

    try:
        import yaml

        data = yaml.safe_load(system_yaml.read_text(encoding="utf-8"))
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
        print("WARN 未找到健康分数据 — 无法判定新鲜度")
        return 0

    if last_updated is None:
        print(f"WARN 健康分 {health_score} 但缺少更新时间戳")
        return 0

    # 阈值比较 —— 原实现漏掉的正是这一步: FRESHNESS_THRESHOLD_HOURS 此前是
    # **死常量**。而补上 `isinstance(str)` 之后仍会空转: YAML 会把 ISO 时间戳
    # 解析成 datetime 而非字符串, 于是真实数据照样落到末尾的「OK 新鲜度正常」
    # （本文件的 test_stale_health_score_is_reported 就是抓这一层）。
    if isinstance(last_updated, (str, datetime)):
        if isinstance(last_updated, str):
            try:
                stamp = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            except ValueError:
                print(f"WARN 健康分 {health_score} 的更新时间戳无法解析: {last_updated!r}")
                return 0
        else:
            stamp = last_updated
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        age_hours = (datetime.now(UTC) - stamp).total_seconds() / 3600
        if age_hours > FRESHNESS_THRESHOLD_HOURS:
            print(f"STALE 健康分 {health_score} 已 {age_hours:.1f}h 未更新 "
                  f"(阈值 {FRESHNESS_THRESHOLD_HOURS}h, 更新于 {last_updated})")
        else:
            print(f"OK 健康分 {health_score} 新鲜度正常 ({age_hours:.1f}h)")
        return 0

    print(f"OK 健康分 {health_score} 新鲜度正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
