#!/usr/bin/env python3
"""CR-RESIDENT-STATUS-01: resident daemon 水位活性 CI 校验.

resident 体系以 daemon byte_offset 水位判断活性 (cron --once 下无常驻进程,
进程退出属正常, 以水位文件 mtime 新鲜度为准). 与 omo resident status
(projects/omo/src/omo/resident/status.py) 共享同一阈值 STALE_THRESHOLD_SECONDS=1800.

rule: resident.daemon.tick_age_seconds <= 1800 or resident.never_ticked == true
- 无任何水位文件 → never_ticked=true (从未调度, 豁免阻塞, 报告为 advisory)
- 最旧水位 (min mtime) 年龄 > 30min → FAIL (degraded)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WATERMARKS = REPO / ".omo" / "_delivery" / "resident-orchestrator" / "watermarks"
SERVICES_REGISTRY = REPO / ".omo" / "_truth" / "registry" / "services.yaml"
STALE_THRESHOLD_SECONDS = 1800  # 30min, 与 status.py 对齐

# 只有这五个角色由 `omo.resident.cli daemon --once --role <role>` 驱动,
# 因此只有它们会推进 resident-<role>.json 水位
# (omo/resident/daemon.py 的 --role 解析: "sediment/decision/execute/monitor/heartbeat";
#  设置 projector+topic-filter)。signals/inbox/promote 走的是各自独立 CLI 入口,
#  从不进入 run_projector, 因此**不写水位** —— 拿它们判活性等于要求一个
#  永远不会更新的文件保持新鲜。
# 来源: projects/omo/src/omo/resident/daemon.py:516-519
DAEMON_TICKED_ROLES = frozenset(
    {"resident-sediment", "resident-decision", "resident-execute", "resident-monitor", "resident-heartbeat"}
)


def enabled_resident_roles() -> set[str] | None:
    """从 services.yaml 取 enabled=True 的 resident 角色名集合。

    返回 None 表示「读不到注册表」(缺文件/解析失败), 此时调用方应退回
    「全部水位都算在役」的旧行为, 而不是静默把全部角色豁免。

    角色 id 形如 `resident.decision`, 水位文件形如 `resident-decision.json`,
    故比对前把 `.` 换成 `-`。
    """
    try:
        import yaml  # 局部导入: 该脚本此前零 yaml 依赖
    except ImportError:
        return None
    try:
        docs = [d for d in yaml.safe_load_all(SERVICES_REGISTRY.read_text(encoding="utf-8")) if d]
    except (OSError, Exception):
        return None
    roles: set[str] = set()
    for doc in docs:
        services = doc.get("services") if isinstance(doc, dict) else None
        if isinstance(services, dict):
            iterable = [dict(v or {}, id=k) for k, v in services.items()]
        elif isinstance(services, list):
            iterable = services
        elif isinstance(doc, dict) and "id" in doc:
            iterable = [doc]
        else:
            continue
        for svc in iterable:
            sid = str(svc.get("id", ""))
            if sid.startswith("resident.") and svc.get("enabled"):
                roles.add(sid.replace(".", "-"))
    return roles or None


def _load_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def check_daemon_watermark() -> tuple[bool, str]:
    """CR-RESIDENT-STATUS-01: daemon 水位新鲜度 ≤30min 或从未 tick.

    daemon 水位 = 五类角色水位 (resident-{role}.json, 由 daemon --once --role 每 2min 推进).
    排除订阅层 resident-sub.json (subscribe 非 cron --once 触发的 daemon tick 证据,
    若混入会让健康体系被陈旧 sub 水位误判 degraded).

    只对 services.yaml 中 enabled=True 的角色判活性: 已停用角色的水位本就
    不再推进, 把它们计入 min(mtime) 会让健康的 daemon 被判 degraded
    (2026-10-06 实锤: decision/execute 水位 3s 前, 而三个 enabled=False 的
    角色停在 33h 前, 门禁取最旧者 → 误报)。读不到注册表时退回旧行为,
    宁可误报也不静默豁免。
    """
    if not WATERMARKS.is_dir():
        return True, "watermarks dir absent (daemon never configured), never_ticked=true"
    files = sorted(
        p for p in WATERMARKS.glob("resident-*.json") if p.name != "resident-sub.json"
    )
    if not files:
        return True, "no role watermark (daemon never ticked), never_ticked=true"
    enabled = enabled_resident_roles()
    # 判活范围 = daemon 会推进水位的角色 ∩ 在册 enabled 的角色。
    #   · 不看 enabled=False 的角色: 它们已停用, 水位本就不再推进
    #     (2026-10-06 实锤: decision/execute 水位 3s 前, 三个停用角色停在 33h 前,
    #      旧判据取 min(mtime) → 误报 degraded, 而 daemon 本身健康)。
    #   · 不看 signals/inbox/promote: 它们不写水位, 判活等于要求永不变的文件新鲜。
    # 两个集合交集为空时退回全部水位(宁可误报也不静默豁免)。
    ticked = [p for p in files if p.stem in DAEMON_TICKED_ROLES]
    in_service = [p for p in ticked if p.stem in enabled] if enabled else []
    considered = in_service or ticked or files
    scope = "enabled+daemon" if in_service else ("daemon" if ticked else "all")
    oldest = min(considered, key=lambda p: p.stat().st_mtime)
    age = time.time() - oldest.stat().st_mtime
    wm = _load_json(oldest)
    byte_offset = int(wm.get("byte_offset", 0)) if wm else None
    detail = (
        f"last daemon tick {age:.0f}s ago (stale >{STALE_THRESHOLD_SECONDS}s), "
        f"watermark={oldest.name} scope={scope} byte_offset={byte_offset}"
    )
    if age > STALE_THRESHOLD_SECONDS:
        return False, f"{detail} → degraded"
    return True, detail


def main() -> int:
    print("── CR-RESIDENT-STATUS-01: resident daemon 水位活性 ──")
    passed, detail = check_daemon_watermark()
    icon = "OK" if passed else "FAIL"
    print(f"  [{icon}] {detail}")
    print()
    if passed:
        print("CR-RESIDENT-STATUS-01 PASS")
        return 0
    print("CR-RESIDENT-STATUS-01 FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
