#!/usr/bin/env python3
"""GaC Check: ADR-0457 宿主与主仓单测环境零污染卫生守卫.

检查项:
  1. 宿主生产卡片目录 ~/.local/share/omostation/cards/ 无测试假卡片
  2. 主仓任务中心 .omo/_truth/task-center/dispatches/ 无单测残留任务
  3. 生产夜巡报告 ~/.local/share/omostation/patrol/night-patrol-latest.json 无模拟电源/模拟跑测数据
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def check_host_hygiene() -> tuple[bool, list[str]]:
    violations: list[str] = []

    # 1. 检查生产卡片目录
    prod_cards_dir = Path.home() / ".local/share/omostation/cards"
    if prod_cards_dir.exists():
        for card_file in prod_cards_dir.glob("*.json"):
            try:
                data = json.loads(card_file.read_text(encoding="utf-8"))
                # 检查卡片是否含有单测残留特征
                summary = str(data.get("summary", "")).lower()
                title = str(data.get("title", "")).lower()
                task_id = str(data.get("task_id", "")).lower()
                agent = str(data.get("agent", "")).lower()
                fname = card_file.name.lower()

                has_test_signature = (
                    "test" in fname
                    or "mock" in fname
                    or "chaos" in fname
                    or "leak" in fname
                    or "test" in task_id
                    or "测试" in str(data.get("title", ""))
                    or "test" in title
                    or "test" in summary
                    or "mock" in summary
                    or "test" in agent
                )

                if has_test_signature:
                    # 排除合法的非测试文件 (但合法文件绝不应含有 test/mock/chaos/leak)
                    violations.append(f"Production card pollution detected: {card_file.name} (title='{data.get('title', '')}')")
            except Exception as e:
                violations.append(f"Invalid card JSON in production: {card_file.name} ({e})")

    # 2. 检查主仓任务中心
    dispatches_dir = ROOT / ".omo/_truth/task-center/dispatches"
    if dispatches_dir.exists():
        dispatches = list(dispatches_dir.glob("*.yaml")) + list(dispatches_dir.glob("*.json"))
        for d in dispatches:
            violations.append(f"Task center dispatches not clean: {d.name}")

    # 3. 检查夜巡报告真实性
    patrol_file = Path.home() / ".local/share/omostation/patrol/night-patrol-latest.json"
    if patrol_file.exists():
        try:
            p_data = json.loads(patrol_file.read_text(encoding="utf-8"))
            power_desc = str(p_data.get("power_status", ""))
            if "(模拟)" in power_desc or "模拟" in power_desc:
                violations.append(f"Production night patrol contains simulated power status: '{power_desc}'")
        except Exception as e:
            violations.append(f"Failed to parse night patrol report: {e}")

    return len(violations) == 0, violations


def main() -> int:
    ok, violations = check_host_hygiene()
    if ok:
        print("✅ ADR-0457 Host & Workspace Zero-Pollution Hygiene: PASS")
        return 0
    else:
        print("❌ ADR-0457 Host & Workspace Zero-Pollution Hygiene: VIOLATION DETECTED")
        for v in violations:
            print(f"  - {v}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
