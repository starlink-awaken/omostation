#!/usr/bin/env python3
"""GaC Check: ADR-0466 宿主与主仓单测环境零污染卫生守卫 (法条 2).

法条 2 要求「单测零公害」: 测试不得向宿主生产目录 (~/.local/share/omostation/)
或主仓数据面 (.omo/_truth/task-center/) 写入任何持久化文件。

检查项:
  1. 宿主生产卡片目录 ~/.local/share/omostation/cards/ —— 无「伪造执行」卡片
     (法条 1: 派发型卡片声称可签名却拿不出 diff 证据)
  2. 主仓任务中心 .omo/_truth/task-center/dispatches/ —— 无单测残留任务
     (按 objective/status 的测试特征判定; 正常生产派发任务对象不算)
  3. 生产夜巡报告 ~/.local/share/omostation/patrol/night-patrol-latest.json
     —— 无模拟电源/模拟跑测数据

判据与历史的关系: ADR-0466 §1 记录 2026-10-19 审查发现「常驻单测未隔离, 向宿主
目录倾倒 79 张假卡片」。那 79 张已于 2026-10-17 前后归档到
~/.local/share/omostation/cards_archive/, 并在 7 天保留期届满后 (2026-10-26) 由
bin/ops/purge-test-archive-7d.py 物理销毁 (2026-10-27, 两机各 79 张)。本检查判的是
**生产目录里是否又长出新的伪造卡片** —— 归档区的不再计入 (归档区只做逐条目保留期
管理, 归 ADR-0466 §4 生命周期, 不归本门禁)。

注意「诚实失败」不算污染: status=execution_failed + patch_ready=false + diff 键
存在且为空, 是 worker 忠实报告「worktree missing」的诚实失败记录 (法条 1 要求的
显式失败), 必须保留 —— 它不是伪造。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST_OMOSTATION = Path.home() / ".local/share/omostation"

# 单测残留的文本特征 (ADR-0466 描述的 test_resident_*.py 倾倒形态)
_TEST_MARKERS = ("test", "mock", "chaos", "leak", "测试", "pytest", "fixture")


def _is_forged_execution(card: dict) -> bool:
    """伪造执行 (法条 1): 派发型卡片声称可签名, 却拿不出任何 diff 证据。

    诚实失败 (status=execution_failed) 不算 —— 那正是法条 1 要求的「显式失败」。
    """
    if card.get("type") != "agora_task":
        return False
    if card.get("status") == "execution_failed":
        return False
    if str(card.get("diff", "") or "").strip():
        return False
    # 无 diff 证据: 要么 patch_ready 声称可签名, 要么连 diff 键都没有 (旧形态硬编码假 Diff)
    return card.get("patch_ready") is True or "diff" not in card


def _is_test_leftover(task: dict) -> bool:
    """主仓 dispatch 里的单测残留任务。

    正常生产派发 (status=worktree_ready / worktree_missing 等) 不算 —— 那是
    resident 自愈流程的真实任务对象。
    """
    blob = " ".join(
        str(task.get(k, ""))
        for k in ("objective", "title", "initiator", "target_agent", "notes", "tags")
    ).lower()
    if not any(marker in blob for marker in _TEST_MARKERS):
        return False
    # 有明确生产态且不是测试态 -> 放行
    status = str(task.get("status", ""))
    if status and "test" not in status:
        return False
    return True


def check_host_hygiene() -> tuple[bool, list[str]]:
    violations: list[str] = []

    # 1. 宿主生产卡片目录: 伪造执行
    prod_cards_dir = HOST_OMOSTATION / "cards"
    if prod_cards_dir.exists():
        for card_file in prod_cards_dir.glob("*.json"):
            try:
                card = json.loads(card_file.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                violations.append(f"Invalid card JSON in production: {card_file.name} ({exc})")
                continue
            if _is_forged_execution(card):
                violations.append(
                    f"Forged execution card in production: {card_file.name} "
                    f"(status={card.get('status')!r}, patch_ready={card.get('patch_ready')!r}, "
                    f"no diff evidence)"
                )

    # 2. 主仓任务中心: 单测残留
    dispatches_dir = ROOT / ".omo/_truth/task-center/dispatches"
    if dispatches_dir.exists():
        for path in list(dispatches_dir.glob("*.json")) + list(dispatches_dir.glob("*.yaml")):
            try:
                raw = path.read_text(encoding="utf-8")
                task = json.loads(raw) if path.suffix == ".json" else __import__("yaml").safe_load(raw)
            except Exception as exc:  # noqa: BLE001
                violations.append(f"Unreadable dispatch in task center: {path.name} ({exc})")
                continue
            if isinstance(task, dict) and _is_test_leftover(task):
                violations.append(f"Unit-test leftover task in task center: {path.name}")

    # 3. 夜巡报告真实性
    patrol_file = HOST_OMOSTATION / "patrol/night-patrol-latest.json"
    if patrol_file.exists():
        try:
            p_data = json.loads(patrol_file.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            violations.append(f"Failed to parse night patrol report: {exc}")
        else:
            power_desc = str(p_data.get("power_status", ""))
            if "模拟" in power_desc:
                violations.append(f"Production night patrol contains simulated power status: {power_desc!r}")

    return len(violations) == 0, violations


def main() -> int:
    ok, violations = check_host_hygiene()
    if ok:
        print("✅ ADR-0466 Host & Workspace Zero-Pollution Hygiene: PASS")
        return 0
    print("❌ ADR-0466 Host & Workspace Zero-Pollution Hygiene: VIOLATION DETECTED")
    for v in violations:
        print(f"  - {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
