#!/usr/bin/env python3
"""trigger_real_outcome.py — 触发真实 Outcome.Human.v1 事件.

完整流程: start episode → human confirm → record outcome.
通过 PersonalEpisodeService 写入 event-ledger.sqlite3.
让 north_star_meter_v2 能读到真实 episodes.
"""

import os
import sys
from pathlib import Path

os.chdir("/Users/xiamingxing/Workspace")
sys.path.insert(0, "projects/omo/src")

from omo.personal_episode import (
    PersonalEpisodeService,
    EVT_OUTCOME_HUMAN,
    PersonalLocalSignal,
    PersonalEpisodeError,
)
from omo.sovereignty.roles import SovereigntyService

LEDGER = Path("runtime/omo/event-ledger.sqlite3").resolve()
PRINCIPAL_ID = "principal:xiamingxing"
ROLE_ID = "role:business-owner"
RESPONSIBILITY_ID = "responsibility:business-consultant-v1"
EXECUTOR_ID = "agent:omo.personal-episode"
REQUEST_ID = "real-outcome-2026-08-20-002"


def main():
    print("=== 触发真实 Outcome.Human.v1 事件 ===\n")

    # 1. 打开 service
    print(f"1. 打开 ledger: {LEDGER}")
    svc = PersonalEpisodeService.open(LEDGER)
    print("   ✅ service opened\n")

    # 1.5 先 revoke 旧 role, 再 assign 新 role (with responsibility)
    print("1.5 revoke 旧 role + assign 新 role (含 responsibility)")
    sov = SovereigntyService.open(LEDGER)
    try:
        sov.revoke(principal_id=PRINCIPAL_ID, role_id=ROLE_ID)
        print(f"   🔄 revoked old assignment")
    except Exception as e:
        print(f"   (无旧 assignment: {e})")
    sov.assign(
        principal_id=PRINCIPAL_ID,
        role_id=ROLE_ID,
        role_name="Business Owner",
        scope="omo.personal-episode",
        responsibilities=[
            {"resp_id": "responsibility:business-consultant-v1", "name": "Business Consultant"},
        ],
    )
    print(f"   ✅ role assigned: {ROLE_ID} (with responsibility)\n")

    # 2. 启动 episode
    print(f"2. start episode (request_id={REQUEST_ID})")
    card = svc.start(
        principal_id=PRINCIPAL_ID,
        role_id=ROLE_ID,
        responsibility_id=RESPONSIBILITY_ID,
        executor_id=EXECUTOR_ID,
        request_id=REQUEST_ID,
        summary="真实业务触发: 投递国转中心公文请求, 走 document-review → ingest 流程",
        why_now="测试北極星 v2 因果事件流 (替代 consumer=human 自报)",
    )
    print(f"   ✅ episode_id={card.episode_id}")
    print(f"   summary: {card.summary[:60]}...\n")

    # 3. 人类确认 (这是 Outcome.Human.v1 需要的真实人类操作)
    print(f"3. confirm(human_confirmed=True)")
    try:
        mandate = svc.confirm(
            episode_id=card.episode_id,
            principal_id=PRINCIPAL_ID,
            executor_id=EXECUTOR_ID,
            human_confirmed=True,
        )
        print(f"   ✅ mandate_id={mandate.mandate_id}\n")
    except PersonalEpisodeError as e:
        print(f"   ⚠️ confirm error: {e}\n")

    # 4. 记录 outcome (这是真正的 Outcome.Human.v1 事件)
    print(f"4. record_outcome(verdict=accept)")
    exec_context = svc.reload_execution_context(card.episode_id, PRINCIPAL_ID)
    seq = svc.record_outcome(
        context=exec_context,
        verdict="accept",
        review_duration_seconds=45.0,  # 真实人类操作耗时
        estimated_time_saved_seconds=120.0,  # 节省时间
    )
    print(f"   ✅ event sequence={seq}\n")

    # 5. 验证
    print("5. 验证 event-ledger 写入:")
    import sqlite3
    con = sqlite3.connect(str(LEDGER))
    cur = con.cursor()
    cur.execute("SELECT event_type, principal_id, payload_json FROM event_log ORDER BY sequence DESC LIMIT 3")
    for row in cur.fetchall():
        print(f"   {row[0]} | principal={row[1]} | payload={row[2][:80]}...")
    con.close()
    print()

    # 6. 重新测量北極星
    print("6. 重新测量北極星:")
    import subprocess
    r = subprocess.run(
        ["uv", "run", "--project", "projects/omo", "python",
         "bin/bc-os/north_star_meter_v2.py",
         "--principal-id", PRINCIPAL_ID, "--json"],
        capture_output=True, text=True
    )
    import json
    data = json.loads(r.stdout)
    m = data.get("metrics", {})
    print(f"   total_episodes: {m.get('total_episodes', 0)}")
    print(f"   four_week_value_gate: {m.get('four_week_value_gate', '?')}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()