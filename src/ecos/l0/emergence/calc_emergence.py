#!/usr/bin/env python3
"""Calculate all emergence metrics from SSB data."""

import sqlite3
from datetime import datetime, timedelta

from ecos.common.common import ECOS_HOME as ECOS_DIR  # type: ignore[import-not-found]

SSB_DB = ECOS_DIR / "LADS/ssb/ecos.db"


def run():
    db = sqlite3.connect(str(SSB_DB))
    cur = db.cursor()
    now = datetime.now()

    total = cur.execute("SELECT COUNT(*) FROM ssb_events").fetchone()[0]

    # SSB 事件频度
    cnt_24h = cur.execute(
        "SELECT COUNT(*) FROM ssb_events WHERE timestamp >= ?",
        ((now - timedelta(hours=24)).isoformat(),),
    ).fetchone()[0]
    cnt_7d = cur.execute(
        "SELECT COUNT(*) FROM ssb_events WHERE timestamp >= ?",
        ((now - timedelta(days=7)).isoformat(),),
    ).fetchone()[0]
    hourly_avg = round(cnt_7d / 168, 1)

    # 签名覆盖率
    sig = cur.execute(
        "SELECT COUNT(*) FROM ssb_events WHERE agent_signature IS NOT NULL AND agent_signature != ''"
    ).fetchone()[0]
    sig_coverage = round(sig / total, 3) if total > 0 else 0

    # Agent 角色分布
    rows = cur.execute("""
        SELECT source_agent, COUNT(*) as c FROM ssb_events
        GROUP BY source_agent ORDER BY c DESC
    """).fetchall()
    total_events = sum(r[1] for r in rows)
    core_agents = [(a, c) for a, c in rows if not a.startswith("sub_test")]
    num_core = len(core_agents)

    # 均匀度 (1 - Herfindahl index)
    share_sq = sum((c / total_events) ** 2 for _, c in core_agents)
    balance = round(1 - share_sq, 3)

    # 角色切换率
    agents_only = [
        r[0]
        for r in cur.execute("""
        SELECT source_agent FROM ssb_events ORDER BY seq
    """).fetchall()
    ]
    switches = sum(
        1 for i in range(1, len(agents_only)) if agents_only[i] != agents_only[i - 1]
    )
    switch_rate = round(switches / len(agents_only), 3) if agents_only else 0

    # 每日事件量
    daily_rows = cur.execute(
        """
        SELECT date(timestamp) as d, COUNT(*) as c
        FROM ssb_events
        WHERE timestamp >= ?
        GROUP BY d ORDER BY d
    """,
        ((now - timedelta(days=7)).isoformat(),),
    ).fetchall()

    # 风险等级
    risk_rows = cur.execute("""
        SELECT risk_level, COUNT(*) as c FROM ssb_events
        GROUP BY risk_level ORDER BY c DESC
    """).fetchall()
    risk_med = sum(c for r, c in risk_rows if r == "MED")

    # 24h 每小时分布
    hourly_rows = cur.execute(
        """
        SELECT strftime('%H', timestamp) as h, COUNT(*) as c
        FROM ssb_events
        WHERE timestamp >= ?
        GROUP BY h ORDER BY h
    """,
        ((now - timedelta(hours=24)).isoformat(),),
    ).fetchall()

    db.close()

    print(f"total_events={total}")
    print(f"event_freq_24h={cnt_24h}")
    print(f"event_freq_7d={cnt_7d}")
    print(f"event_hourly_avg={hourly_avg}")
    print(f"sig_coverage={sig_coverage}")
    print(f"num_active_agents={num_core}")
    print(f"role_switch_rate={switch_rate}")
    print(f"role_balance={balance}")
    print(f"risk_med_count={risk_med}")
    print(f"knowledge_velocity={total}")
    print(f'daily_breakdown="{"".join(f"{d}:{c} " for d, c in daily_rows).strip()}"')
    print(
        f'hourly_breakdown="{"".join(f"{h}:00-{c} " for h, c in hourly_rows).strip()}"'
    )


if __name__ == "__main__":
    run()
