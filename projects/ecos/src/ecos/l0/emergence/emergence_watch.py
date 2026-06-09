#!/usr/bin/env python3
"""
emergence_watch.py — 涌现度量偏离检测 & 阈值告警

比较当前度量与 STATE.yaml 基线，偏离 > 30% 时：
  1. 写入 SSB 告警事件
  2. 输出警报信息供 WF-003 巡检捕获

用法:
  python3 scripts/emergence_watch.py

返回码: 0=正常, 1=有告警
"""

import sqlite3
import sys
from datetime import UTC, datetime, timedelta

import yaml

from ecos.common.common import ECOS_HOME as ECOS_DIR  # type: ignore[import-not-found]

STATE_PATH = ECOS_DIR / "STATE.yaml"
SSB_DB = ECOS_DIR / "LADS/ssb/ecos.db"

# 定义需要监控的度量及其阈值偏差比
MONITORED_METRICS = {
    "event_freq_24h": {
        "label": "24h事件频度",
        "threshold": 0.30,
        "type": "event_volume",
    },
    "event_hourly_avg": {
        "label": "小时事件均值",
        "threshold": 0.30,
        "type": "event_volume",
    },
    "signature_coverage": {
        "label": "签名覆盖率",
        "threshold": 0.05,  # 签名必须严格 — 只允许 5% 下降
        "type": "security",
        "direction": "decrease",
    },
    "role_switch_rate": {
        "label": "角色切换率",
        "threshold": 0.30,
        "type": "emergence",
    },
    "role_balance": {
        "label": "角色平衡度",
        "threshold": 0.30,
        "type": "emergence",
    },
    "error_resilience": {
        "label": "错误韧性",
        "threshold": 0.30,
        "type": "resilience",
        "direction": "decrease",
    },
    "knowledge_velocity": {
        "label": "知识流速",
        "threshold": 0.30,
        "type": "velocity",
        "direction": "decrease",
    },
}


def load_baseline():
    """从 STATE.yaml 读取 emergence 基线"""
    with open(STATE_PATH) as f:
        state = yaml.safe_load(f)
    return state.get("emergence", {})


def get_current():
    """实时采集最新度量"""
    db = sqlite3.connect(SSB_DB)
    cur = db.cursor()
    now = datetime.now()

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
    sig_coverage = round(sig / total, 3) if total > 0 else 0

    # 角色切换率
    agents = [
        r[0]
        for r in cur.execute(
            "SELECT source_agent FROM ssb_events ORDER BY seq"
        ).fetchall()
    ]
    switch_rate = (
        round(
            sum(1 for i in range(1, len(agents)) if agents[i] != agents[i - 1])
            / len(agents),
            3,
        )
        if agents
        else 0
    )

    # 角色均匀度
    rows = cur.execute(
        "SELECT source_agent, COUNT(*) as c FROM ssb_events GROUP BY source_agent"
    ).fetchall()
    total_evt = sum(r[1] for r in rows)
    core = [(a, c) for a, c in rows if not a.startswith("sub_test")]
    share_sq = sum((c / total_evt) ** 2 for _, c in core)
    balance = round(1 - share_sq, 3) if core else 0

    db.close()

    return {
        "event_freq_24h": cnt_24h,
        "event_freq_7d": cnt_7d,
        "event_hourly_avg": hourly_avg,
        "signature_coverage": sig_coverage,
        "role_switch_rate": switch_rate,
        "role_balance": balance,
        "knowledge_velocity": total,
    }


def calc_deviation(baseline_val, current_val, direction="both"):
    """计算偏离比例"""
    if baseline_val == 0:
        return 0 if current_val == 0 else 1.0

    if direction == "decrease":
        # 只关心下降：基线 * (1-阈值) 以下才告警
        if current_val >= baseline_val:
            return 0
        return (baseline_val - current_val) / baseline_val
    elif direction == "increase":
        if current_val <= baseline_val:
            return 0
        return (current_val - baseline_val) / baseline_val
    else:
        return abs(current_val - baseline_val) / baseline_val


def write_ssb_alert(metric_name, metric_label, baseline, current, deviation, severity):
    """将告警写入 SSB 事件（避免循环：不走 SSBClient，直接 INSERT）"""
    import uuid

    event_id = f"EMERGENCE-ALERT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    now_utc = datetime.now(UTC).isoformat()

    detail = json.dumps(
        {
            "metric": metric_name,
            "label": metric_label,
            "baseline": baseline,
            "current": current,
            "deviation_pct": round(deviation * 100, 1),
            "severity": severity,
            "triggered_at": now_utc,
        }
    )

    db = None
    try:
        db = sqlite3.connect(SSB_DB)
        db.execute("BEGIN")
        last_seq = db.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM ssb_events"
        ).fetchone()[0]
        new_seq = last_seq + 1

        db.execute(
            """
            INSERT INTO ssb_events
            (id, seq, timestamp, source_agent, source_instance, event_type, event_subtype,
             summary, detail, risk_level, priority, action_req, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                event_id,
                new_seq,
                now_utc,
                "EMERGENCE_WATCH",
                "sprint3",
                "ALERT",
                "EMERGENCE_DRIFT",
                f"度量漂移: {metric_label} 偏离 {round(deviation * 100, 1)}% (基线={baseline}, 当前={current})",
                detail,
                severity,
                "P1" if severity == "HIGH" else "P2",
                "REVIEW",
                "{}",
            ),
        )

        # 计算并写入 HMAC 签名
        from ecos.protocol.ssb.ssb_auth import compute_signature

        sig = compute_signature(new_seq, event_id, "EMERGENCE_WATCH", "{}")
        if sig:
            db.execute(
                "UPDATE ssb_events SET agent_signature = ? WHERE id = ?",
                (sig, event_id),
            )

        db.commit()
    except Exception:
        if db:
            db.rollback()
        raise
    finally:
        if db:
            db.close()


def check():
    baseline = load_baseline()
    current = get_current()

    alerts = []
    for metric, cfg in MONITORED_METRICS.items():
        b = baseline.get(metric)
        c = current.get(metric)
        if b is None or c is None:
            continue
        direction = cfg.get("direction", "both")
        dev = calc_deviation(b, c, direction)
        if dev > cfg["threshold"]:
            severity = "HIGH" if dev > 0.50 else "MED"
            alerts.append(
                {
                    "metric_name": metric,
                    "metric_label": cfg["label"],
                    "baseline": b,
                    "current": c,
                    "deviation": dev,
                    "severity": severity,
                }
            )

    if alerts:
        for alert in alerts:
            write_ssb_alert(**alert)
            print(
                f"⚠️ [{alert['severity']}] {alert['metric_label']}: 偏离 {alert['deviation'] * 100:.1f}% "
                f"(基线={alert['baseline']}, 当前={alert['current']})"
            )
        print(f"共 {len(alerts)} 个度量告警 -> 已写入 SSB")
        return 1
    else:
        print(f"✅ 所有度量正常 (基线: {datetime.now().strftime('%Y-%m-%d %H:%M')})")
        return 0


if __name__ == "__main__":
    import json

    sys.exit(check())
