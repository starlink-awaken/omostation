#!/usr/bin/env python3
"""P44 W2: 分类 60 planned 任务 → keep-active / archive / escalate 三桶"""
import yaml, sys
from pathlib import Path
from collections import defaultdict

PLANNED_DIR = Path("/Users/xiamingxing/Workspace/.omo/tasks/planned")
OUTPUT = Path("/Users/xiamingxing/Workspace/.omo/_delivery/p44-w2-classification.yaml")

# 维度阈值
HIGH_PRIORITY = {"P0", "P1"}
MEDIUM_PRIORITY = {"P2"}
KEEP_MAX = 30

def load_task(path):
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def classify():
    files = sorted(PLANNED_DIR.glob("*.yaml"))
    print(f"📂 共 {len(files)} 个 planned YAML")

    buckets = defaultdict(list)
    anomaly_buckets = defaultdict(list)

    for f in files:
        task = load_task(f)
        name = f.stem
        priority = task.get("priority", "unassigned")
        risk = task.get("risk", task.get("risk_level", "unassigned"))
        phase = task.get("phase", "unphased")
        owner = task.get("owner", "unassigned")
        subject = task.get("subject", name)

        entry = {
            "file": name,
            "priority": priority,
            "risk": risk,
            "phase": phase,
            "owner": owner,
            "subject": subject,
        }

        # 异常检测
        if priority == "P0":
            anomaly_buckets["P0-overload"].append(entry)
        elif risk in ("L3", "L4"):
            anomaly_buckets["high-risk"].append(entry)
        elif owner == "unassigned" and priority in ("P0", "P1"):
            anomaly_buckets["orphaned-critical"].append(entry)
        else:
            buckets["normal"].append(entry)

    # 三桶分配
    # keep-active: P0/P1 高优先级 + 高风险 + orphans-critical → escalate
    # archive: P2/P3/unassigned 且 phase 较老
    keep_active, archive, escalate = [], [], []

    for entry in buckets["normal"]:
        p = entry["priority"]
        r = entry["risk"]
        ph = entry["phase"]
        if p in HIGH_PRIORITY or r in ("L2", "L3"):
            escalate.append(entry)
        elif p in MEDIUM_PRIORITY or ph in ("unphased",) or (isinstance(ph, str) and ph.isdigit() and int(ph) < 30):
            archive.append(entry)
        else:
            keep_active.append(entry)

    # 合并异常到 escalate
    for anom_list in anomaly_buckets.values():
        escalate.extend(anom_list)

    # 如果 keep-active > 30，按 phase 砍最老的
    if len(keep_active) > KEEP_MAX:
        keep_active.sort(key=lambda x: (x["phase"] or "0"))
        keep_active = keep_active[:KEEP_MAX]
        archive.extend(keep_active[KEEP_MAX:])

    result = {
        "summary": {
            "total": len(files),
            "keep_active": len(keep_active),
            "archive": len(archive),
            "escalate": len(escalate),
        },
        "keep_active": keep_active,
        "archive": archive,
        "escalate": escalate,
        "anomaly_detail": dict(anomaly_buckets),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        yaml.dump(result, f, allow_unicode=True, sort_keys=False)

    print(f"✅ 分类完成 → {OUTPUT}")
    print(f"   keep-active: {len(keep_active)} / archive: {len(archive)} / escalate: {len(escalate)}")
    for k, v in anomaly_buckets.items():
        print(f"   异常[{k}]: {len(v)}")

    return result

if __name__ == "__main__":
    classify()