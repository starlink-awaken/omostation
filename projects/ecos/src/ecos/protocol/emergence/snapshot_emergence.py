#!/usr/bin/env python3
"""
snapshot_emergence.py — 涌现度量每日基线快照 (C1)

功能:
  1. 从 STATE.yaml 和实时 SSB 数据采集所有涌现度量
  2. 保存到 LADS/EMERGENCE/YYYY-MM-DD.json
  3. 维护 LATEST.json 指向最新快照
  4. 记录快照历史（用于比较回滚）

用法:
  python3 scripts/snapshot_emergence.py             # 创建今日快照
  python3 scripts/snapshot_emergence.py --compare     # 比较今日 vs 昨日
  python3 scripts/snapshot_emergence.py --list        # 列出所有快照
  python3 scripts/snapshot_emergence.py --rollback    # 回滚到上一快照

返回码: 0=正常, 1=有异常偏离
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import yaml

from ecos.core.common import ECOS_HOME as ECOS_DIR  # type: ignore[import-not-found]

STATE_PATH = ECOS_DIR / "STATE.yaml"
SSB_DB = ECOS_DIR / "LADS/ssb/ecos.db"
EMERGENCE_DIR = ECOS_DIR / "LADS" / "EMERGENCE"
HANDOFF_DIR = ECOS_DIR / "LADS" / "HANDOFF"
HANDOFF_HISTORY = HANDOFF_DIR / "HISTORY"
HANDOFF_LATEST = HANDOFF_DIR / "LATEST.md"
CHECKPOINT_LABEL = EMERGENCE_DIR / ".checkpoint_label"

TZ = timezone(timedelta(hours=8))


def _now():
    return datetime.now(TZ)


def _today():
    return _now().strftime("%Y-%m-%d")


def _ts():
    return _now().isoformat()


def ensure_dirs():
    EMERGENCE_DIR.mkdir(parents=True, exist_ok=True)


def collect_metrics() -> dict:
    """采集当前涌现度量"""
    db = sqlite3.connect(str(SSB_DB))
    cur = db.cursor()
    now = _now()

    total = cur.execute("SELECT COUNT(*) FROM ssb_events").fetchone()[0]
    cnt_24h = cur.execute(
        "SELECT COUNT(*) FROM ssb_events WHERE timestamp >= ?",
        ((now - timedelta(hours=24)).isoformat(),),
    ).fetchone()[0]
    cnt_7d = cur.execute(
        "SELECT COUNT(*) FROM ssb_events WHERE timestamp >= ?",
        ((now - timedelta(days=7)).isoformat(),),
    ).fetchone()[0]
    hourly_avg = round(cnt_7d / 168, 1) if cnt_7d > 0 else 0

    sig = cur.execute(
        "SELECT COUNT(*) FROM ssb_events WHERE agent_signature IS NOT NULL AND agent_signature != ''"
    ).fetchone()[0]
    sig_cov = round(sig / total, 3) if total > 0 else 0

    # 角色切换率
    agents = [r[0] for r in cur.execute("SELECT source_agent FROM ssb_events ORDER BY seq").fetchall()]
    switch_rate = (
        round(sum(1 for i in range(1, len(agents)) if agents[i] != agents[i - 1]) / len(agents), 3) if agents else 0
    )

    # 角色均匀度
    rows = cur.execute(
        "SELECT source_agent, COUNT(*) as c FROM ssb_events GROUP BY source_agent ORDER BY c DESC"
    ).fetchall()
    total_evt = sum(r[1] for r in rows)
    core = [(a, c) for a, c in rows]
    share_sq = sum((c / total_evt) ** 2 for _, c in core) if total_evt > 0 else 0
    balance = round(1 - share_sq, 3)

    # 事件类型分布
    type_dist = cur.execute(
        "SELECT event_type, COUNT(*) as c FROM ssb_events GROUP BY event_type ORDER BY c DESC"
    ).fetchall()

    # 活跃 Agent 数
    active_agents = len(core)

    # 24h C 事件量细分
    events_24h_list = cur.execute(
        "SELECT event_type, COUNT(*) as c FROM ssb_events WHERE timestamp >= ? GROUP BY event_type",
        ((now - timedelta(hours=24)).isoformat(),),
    ).fetchall()

    # 模型使用统计
    model_usage = {}
    try:
        with open(STATE_PATH) as f:
            st = yaml.safe_load(f)
        model_detail = st.get("emergence", {}).get("model_usage_detail", "")
        for part in model_detail.split():
            if ":" in part:
                m, s = part.split(":")
                model_usage[m] = s
    except Exception:
        pass

    db.close()

    return {
        "timestamp": _ts(),
        "date": _today(),
        "event_total": total,
        "event_freq_24h": cnt_24h,
        "event_freq_7d": cnt_7d,
        "event_hourly_avg": hourly_avg,
        "signature_coverage": sig_cov,
        "role_switch_rate": switch_rate,
        "role_balance": balance,
        "num_active_agents": active_agents,
        "event_type_distribution": {t: c for t, c in type_dist},
        "events_24h_breakdown": {t: c for t, c in events_24h_list},
        "model_usage": model_usage,
    }


def save_snapshot(metrics: dict) -> str:
    """保存快照到 LADS/EMERGENCE/YYYY-MM-DD.json"""
    ensure_dirs()
    date = metrics["date"]
    path = EMERGENCE_DIR / f"{date}.json"
    path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2))

    # 更新 LATEST 指向
    latest_path = EMERGENCE_DIR / "LATEST.json"
    latest_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2))

    print(f"  💾 快照已保存: {path.name}")
    return str(path)


def list_snapshots() -> list:
    """列出所有快照"""
    ensure_dirs()
    snapshots = sorted(EMERGENCE_DIR.glob("*.json"))
    # 排除 LATEST
    return [s for s in snapshots if s.name not in ("LATEST.json",)]


def load_latest_snapshot() -> dict | None:
    """加载最新快照"""
    latest_path = EMERGENCE_DIR / "LATEST.json"
    if not latest_path.exists():
        return None
    return json.loads(latest_path.read_text())


def compare(current: dict, previous: dict) -> list:
    """比较今日 vs 昨日快照，返回所有变化"""
    differences = []
    tracked = [
        ("event_freq_24h", "24h事件频度"),
        ("event_freq_7d", "7d事件量"),
        ("event_hourly_avg", "小时均值"),
        ("signature_coverage", "签名覆盖率"),
        ("role_switch_rate", "角色切换率"),
        ("role_balance", "角色平衡度"),
        ("num_active_agents", "活跃Agent数"),
        ("event_total", "事件总量"),
    ]

    for key, label in tracked:
        old = previous.get(key, 0)
        new = current.get(key, 0)
        if old == 0:
            deviation = 0
        else:
            deviation = round((new - old) / old, 3)

        if deviation != 0:
            differences.append(
                {
                    "metric": key,
                    "label": label,
                    "previous": old,
                    "current": new,
                    "deviation": deviation,
                    "abs_deviation": abs(deviation),
                }
            )

    return sorted(differences, key=lambda x: -abs(x["abs_deviation"]))


def save_checkpoint():
    """保存当前 STATE + HANDOFF 为可恢复的检查点"""
    ensure_dirs()
    checkpoint_ts = _now().strftime("%Y%m%d%H%M%S")

    # 复制 STATE.yaml
    if STATE_PATH.exists():
        cp = EMERGENCE_DIR / f"checkpoint-{checkpoint_ts}-STATE.yaml"
        cp.write_text(STATE_PATH.read_text())
    else:
        cp = None

    # 复制 HANDOFF/LATEST.md
    hp = None
    if HANDOFF_LATEST.exists():
        hp = EMERGENCE_DIR / f"checkpoint-{checkpoint_ts}-HANDOFF.md"
        hp.write_text(HANDOFF_LATEST.read_text())

    # 记录检查点标签
    CHECKPOINT_LABEL.write_text(checkpoint_ts)
    print(f"  📌 检查点: {checkpoint_ts}")
    return checkpoint_ts, cp, hp


def rollback():
    """
    回滚到上一检查点。
    恢复 STATE.yaml + HANDOFF/LATEST.md
    """
    if not CHECKPOINT_LABEL.exists():
        print("  ❌ 无可用检查点")
        return False

    label = CHECKPOINT_LABEL.read_text().strip()

    # 恢复 STATE
    cp_state = EMERGENCE_DIR / f"checkpoint-{label}-STATE.yaml"
    if cp_state.exists():
        STATE_PATH.read_text() if STATE_PATH.exists() else ""
        STATE_PATH.write_text(cp_state.read_text())
        print(f"  ↩️  STATE.yaml 已回滚到检查点 {label}")
    else:
        print("  ⚠️  STATE.yaml 检查点缺失")

    # 恢复 HANDOFF
    cp_handoff = EMERGENCE_DIR / f"checkpoint-{label}-HANDOFF.md"
    if cp_handoff.exists():
        HANDOFF_LATEST.write_text(cp_handoff.read_text())
        print(f"  ↩️  HANDOFF/LATEST.md 已回滚到检查点 {label}")
    else:
        print("  ⚠️  HANDOFF 检查点缺失")

    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="涌现度量快照 — C1")
    parser.add_argument("--snapshot", action="store_true", help="创建今日快照 (默认)")
    parser.add_argument("--compare", action="store_true", help="比较今日 vs 昨日")
    parser.add_argument("--list", action="store_true", help="列出所有快照")
    parser.add_argument("--rollback", action="store_true", help="回滚到上一检查点")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    # 默认行为：快照
    if args.snapshot or not any([args.compare, args.list, args.rollback]):
        metrics = collect_metrics()
        save_snapshot(metrics)
        save_checkpoint()

        # 与昨日比较
        snapshots = list_snapshots()
        if len(snapshots) >= 2:
            prev = json.loads(snapshots[-2].read_text())
            diffs = compare(metrics, prev)
            if diffs:
                print(f"\n📊 与昨日对比 ({snapshots[-2].stem} → {snapshots[-1].stem}):")
                for d in diffs[:8]:
                    arrow = "↑" if d["deviation"] > 0 else "↓"
                    print(f"  {arrow} {d['label']}: {d['previous']} → {d['current']} ({d['deviation']:+.1%})")

                # 检查严重偏离
                severe = [d for d in diffs if d["abs_deviation"] > 0.30]
                if severe:
                    print("\n  ⚠️  严重偏离 (>30%):")
                    for d in severe:
                        print(f"    • {d['label']}: {d['deviation']:+.1%}")
                    return 1

        if args.json:
            print(json.dumps(metrics, ensure_ascii=False, indent=2))
        return 0

    if args.compare:
        snapshots = list_snapshots()
        if len(snapshots) < 2:
            print("需要至少 2 个快照才能比较")
            return 1
        current = json.loads(snapshots[-1].read_text())
        previous = json.loads(snapshots[-2].read_text())
        diffs = compare(current, previous)
        print(f"比较: {snapshots[-2].stem} ↔ {snapshots[-1].stem}")
        for d in diffs:
            arrow = "↑" if d["deviation"] > 0 else "↓"
            print(f"  {arrow} {d['label']}: {d['previous']} → {d['current']} ({d['deviation']:+.1%})")
        if args.json:
            print(json.dumps(diffs, ensure_ascii=False, indent=2))
        return 0

    if args.list:
        snaps = list_snapshots()
        print(f"可用快照 ({len(snaps)}):")
        for s in snaps:
            try:
                data = json.loads(s.read_text())
                print(
                    f"  📅 {s.stem} | "
                    f"事件={data.get('event_total', '?')} | "
                    f"24h={data.get('event_freq_24h', '?')} | "
                    f"签名={data.get('signature_coverage', '?')}"
                )
            except (json.JSONDecodeError, OSError):
                print(f"  📅 {s.stem} | (无法读取)")
        return 0

    if args.rollback:
        ok = rollback()
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
