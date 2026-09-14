#!/usr/bin/env python3
"""mesh-stale-analyze.py — 分析 workflow mesh 的 stale planned run (只读).

扫描 mesh events.jsonl 的 planned run, 按是否有 required_capabilities 分类:
- 老格式 (无 required_capabilities): 永远不会被 consume, 候选清理
- 新格式 (有 required_capabilities): consume 可处理

只读, 不写入. 用于评估清理范围 (268 老 run 积压问题).

用法: python3 bin/ssot/mesh-stale-analyze.py
"""

import subprocess
import sys
from collections import Counter
from pathlib import Path

TIMEOUT = 30  # seconds per subprocess call
RETRY = 3    # max retries on transient failure

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "projects" / "omo" / "src"))

from omo.workflow_mesh import WorkflowMeshStore  # type: ignore[import-not-found]

OMO_DIR = WORKSPACE / ".omo"


def main() -> int:
    store = WorkflowMeshStore(OMO_DIR)
    snapshots = store.snapshots()
    events = store.events()

    state_counts = Counter(s.get("state") for s in snapshots)
    print(f"=== mesh run 分析 ({len(snapshots)} runs, {len(events)} events) ===")
    print(f"state 分布: {dict(state_counts)}")

    # 建 run → WorkflowRequested payload + producer 映射
    requested_payload: dict[str, dict] = {}
    producer_by_run: dict[str, str] = {}
    for event in events:
        if event.get("event_type") == "WorkflowRequested":
            rid = event.get("workflow_run_id")
            if rid:
                requested_payload[rid] = event.get("payload") or {}
                producer_by_run[rid] = event.get("producer", "?")

    planned = [s for s in snapshots if s.get("state") == "planned"]
    print(f"\n=== planned run 分类 ({len(planned)}) ===")

    stale: list[tuple[str, dict, str]] = []
    fresh: list[tuple[str, dict, str]] = []
    for s in planned:
        rid = str(s.get("workflow_run_id"))
        payload = requested_payload.get(rid, {})
        producer = producer_by_run.get(rid, "?")
        entry = (rid, payload, producer)
        if payload.get("required_capabilities"):
            fresh.append(entry)
        else:
            stale.append(entry)

    print(f"老格式 (无 required_capabilities, stale): {len(stale)}")
    print(f"新格式 (有 required_capabilities, consume-ready): {len(fresh)}")

    if stale:
        producers = Counter(p for _, _, p in stale)
        print("\n=== stale run producer 分布 ===")
        for p, c in producers.most_common(10):
            print(f"  {p}: {c}")

        # task_id 有无 (判断是 request 缺字段还是 event 缺字段)
        has_task = sum(1 for _, payload, _ in stale if payload.get("task_id"))
        print(f"\nstale 中有 task_id 的: {has_task}/{len(stale)}")

        print("\n=== stale run 样本 (前 5) ===")
        for rid, payload, producer in stale[:5]:
            keys = sorted(payload.keys())
            print(f"  {rid}: producer={producer}, task_id={payload.get('task_id')}, keys={keys[:6]}")

    if fresh:
        print("\n=== fresh run 样本 (前 3) ===")
        for rid, payload, producer in fresh[:3]:
            print(f"  {rid}: producer={producer}, caps={payload.get('required_capabilities')}")

    print(f"\n结论: {len(stale)} 个 stale run 候选清理 (WorkflowCancelled → cancelled → closed)")
    print(f"      {len(fresh)} 个 fresh run 可被 consume (daemon --auto-consume)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
