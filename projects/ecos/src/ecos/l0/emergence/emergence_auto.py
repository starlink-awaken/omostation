#!/usr/bin/env python3
"""
emergence_auto.py — 涌现自调自动化 (C2 + C3 + C4)

当 emergence_watch 或 snapshot_emergence 检测到异常时：
  1. CRITIC 分析：调用 5 模型委员会分析根因 (C2)
  2. 根因分类：P0(数据丢失/签名崩溃) ← 需人类确认
                 P1(中度偏离)      ← 自动分析+回滚
                 P2(轻微偏离)      ← 仅标记
  3. 自动回滚：P1 自动恢复 CHECKPOINT (C3)
  4. 安全阀：P0 仅告警，不改动 (C4)

用法:
  python3 scripts/emergence_auto.py --analyze    # 检查当前偏离+CRITIC分析
  python3 scripts/emergence_auto.py --rollback    # 手动执行回滚
  python3 scripts/emergence_auto.py --status      # 状态
"""

import json
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone

from ecos.common.common import ECOS_HOME as ECOS_DIR  # type: ignore[import-not-found]

SSB_DB = ECOS_DIR / "LADS/ssb/ecos.db"
STATE_PATH = ECOS_DIR / "STATE.yaml"
SCRIPTS = ECOS_DIR / "scripts"
EMERGENCE_DIR = ECOS_DIR / "LADS" / "EMERGENCE"
HANDOFF_LATEST = ECOS_DIR / "LADS/HANDOFF/LATEST.md"
CHECKPOINT_LABEL = EMERGENCE_DIR / ".checkpoint_label"

TZ = timezone(timedelta(hours=8))

# P0: 必须人类确认
P0_METRICS = {"signature_coverage", "event_total"}
P0_THRESHOLD = 0.50  # 50%以上的变化

# P1: 自动 CRITIC → 回滚
P1_THRESHOLD = 0.30  # 30%以上变化

# P2: 仅标记
P2_THRESHOLD = 0.15  # 15%以上变化


def _now():
    return datetime.now(TZ).isoformat()


def _ts():
    return datetime.now(TZ)


def get_deviations():
    """对照最近快照计算偏离"""
    latest_path = EMERGENCE_DIR / "LATEST.json"
    if not latest_path.exists():
        return None, "无基线快照"

    try:
        sys.path.insert(0, str(SCRIPTS))
        from snapshot_emergence import collect_metrics, compare, load_latest_snapshot  # type: ignore[import-not-found]

        current = collect_metrics()
        previous = load_latest_snapshot()
        if not previous:
            return None, "无历史快照可比较"

        diffs = compare(current, previous)
        return {
            "current": current,
            "previous": previous,
            "differences": diffs,
            "timestamp": _now(),
        }, None
    except Exception as e:
        return None, str(e)


def classify_deviations(diffs: list) -> dict:
    """
    按 P0/P1/P2 分类偏离
    """
    p0, p1, p2 = [], [], []

    for d in diffs:
        metric = d["metric"]
        abs_dev = d["abs_deviation"]

        # P0: 关键指标严重偏离
        if metric in P0_METRICS and abs_dev > P0_THRESHOLD:
            p0.append({**d, "severity": "P0", "action": "HUMAN_CONFIRM"})
        # P1: 中度偏离
        elif abs_dev > P1_THRESHOLD:
            p1.append({**d, "severity": "P1", "action": "AUTO_CRITIC_ROLLBACK"})
        # P2: 轻微偏离
        elif abs_dev > P2_THRESHOLD:
            p2.append({**d, "severity": "P2", "action": "FLAG_ONLY"})

    return {"p0": p0, "p1": p1, "p2": p2}


def write_ssb_event(event_type, summary, detail, risk="LOW", action="NONE"):
    """直接写入 SSB（避免循环依赖）"""
    db = None
    try:
        db = sqlite3.connect(str(SSB_DB))
        db.execute("BEGIN")
        last_seq = db.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM ssb_events"
        ).fetchone()[0]
        eid = f"EMERGENCE-AUTO-{_ts().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        db.execute(
            """
            INSERT INTO ssb_events
            (id, seq, timestamp, session_id,
             source_agent, source_instance,
             target_scope, target_hint,
             event_type, event_subtype,
             summary, detail, confidence, risk_level, priority,
             action_req, deadline, payload_json, semantic_json)
            VALUES (?, ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?)
        """,
            (
                eid,
                last_seq + 1,
                _now(),
                "",
                "EMERGENCE_AUTO",
                "phase6",
                "SSB_PERSIST",
                "",
                event_type,
                "EMERGENCE_ACTION",
                summary[:200],
                str(detail)[:1000],
                0.9,
                risk,
                "P1" if risk == "HIGH" else "P2",
                action,
                "",
                json.dumps(
                    {
                        "summary": summary,
                        "detail": str(detail)[:500],
                        "confidence": 0.9,
                        "risk_level": risk,
                        "priority": "P1",
                        "action_required": action,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "intent": "emergence auto-response",
                        "state_change": "emergence_deviation_detected",
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        db.commit()
        return eid
    except Exception as e:
        if db:
            db.rollback()
        print(f"  ⚠️ SSB写入失败: {e}")
        return None
    finally:
        if db:
            db.close()


def run_critic_analysis(deviations: list) -> dict:
    """
    使用5模型委员会分析偏离根因 (C2)
    如果委员会可用，调用 multi_model_committee.py
    否则生成内置分析报告
    """
    topic_parts = []
    for d in deviations:
        arrow = "↑" if d["deviation"] > 0 else "↓"
        topic_parts.append(
            f"{d['label']} {arrow}{abs(d['deviation'] * 100):.0f}% ({d['previous']}→{d['current']})"
        )

    topic = "偏离诊断: " + " | ".join(topic_parts[:3])

    try:
        # 尝试调用委员会
        r = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "multi_model_committee.py"),
                "--risk",
                "MED",
                topic,
            ],
            capture_output=True,
            text=True,
            timeout=200,
        )
        if r.returncode == 0 or r.returncode == 1:
            return {
                "method": "multi_model_committee",
                "output": r.stdout[:2000] if r.stdout else r.stderr[:500],
                "success": True,
            }
        else:
            raise Exception(f"退出码: {r.returncode}")
    except Exception as e:
        # 降级：内置 CRITIC 分析
        print(f"  ⚠️ 委员会调用失败, 使用内置CRITIC: {e}")
        analysis = []
        for d in deviations:
            direction = "上升" if d["deviation"] > 0 else "下降"
            analysis.append(
                f"- {d['label']}: {direction} {abs(d['deviation']):.1%} (从 {d['previous']} 到 {d['current']})"
            )
        return {
            "method": "builtin",
            "output": "\n".join(analysis),
            "success": True,
        }


def auto_rollback():
    """执行自动回滚 (C3)"""
    if not CHECKPOINT_LABEL.exists():
        return {"success": False, "reason": "无可用检查点"}

    label = CHECKPOINT_LABEL.read_text().strip()
    restored = []

    # 恢复 STATE.yaml
    cp_state = EMERGENCE_DIR / f"checkpoint-{label}-STATE.yaml"
    if cp_state.exists():
        STATE_PATH.write_text(cp_state.read_text())
        restored.append("STATE.yaml")

    # 恢复 HANDOFF
    cp_handoff = EMERGENCE_DIR / f"checkpoint-{label}-HANDOFF.md"
    if cp_handoff.exists():
        HANDOFF_LATEST.write_text(cp_handoff.read_text())
        restored.append("HANDOFF/LATEST.md")

    if restored:
        summary = f"自动回滚到检查点 {label}: {' + '.join(restored)}"
        write_ssb_event(
            "STATE_CHANGE",
            summary,
            json.dumps(
                {
                    "action": "ROLLBACK",
                    "checkpoint": label,
                    "files_restored": restored,
                },
                ensure_ascii=False,
            ),
            "MED",
            "REVIEW",
        )
        return {"success": True, "checkpoint": label, "restored": restored}
    else:
        return {"success": False, "reason": "检查点文件缺失"}


def analyze():
    """完整分析流程：检测→分类→CRITIC→决策"""
    print("=" * 70)
    print("🔍 涌现自调 — 偏离检测 & CRITIC 分析")
    print("=" * 70)

    # Step 1: 更新快照
    print("\n▶ 步骤1: 采集当前度量")
    try:
        sys.path.insert(0, str(SCRIPTS))
        from snapshot_emergence import (
            collect_metrics,
            load_latest_snapshot,
            save_checkpoint,
            save_snapshot,
        )

        current = collect_metrics()
        save_snapshot(current)
        load_latest_snapshot()
        # 重新加载（LATEST.json已被更新）
    except Exception as e:
        print(f"  ❌ 快照失败: {e}")
        return 1

    # Step 2: 计算偏离
    print("\n▶ 步骤2: 计算偏离")
    data, err = get_deviations()
    if err or not data:
        print(f"  ⚠️ {err or '无数据'}")
        return 1

    diffs = data["differences"]
    if not diffs:
        print("  ✅ 无显著偏离")
        return 0

    for d in diffs:
        arrow = "↑" if d["deviation"] > 0 else "↓"
        print(
            f"  {arrow} {d['label']}: {d['deviation']:+.1%} ({d['previous']}→{d['current']})"
        )

    # Step 3: 分类
    print("\n▶ 步骤3: 偏离分类")
    classified = classify_deviations(diffs)

    for level, items in [
        ("P0 🔴", classified["p0"]),
        ("P1 🟡", classified["p1"]),
        ("P2 ⚪", classified["p2"]),
    ]:
        for item in items:
            print(
                f"  {level}: {item['label']} ({item['deviation']:+.1%}) → {item['action']}"
            )

    # Step 4: CRITIC 分析 (P0+P1)
    all_critic = classified["p0"] + classified["p1"]
    if all_critic:
        print(f"\n▶ 步骤4: CRITIC 分析 ({len(all_critic)} 个偏离)")
        critic_result = run_critic_analysis(all_critic)
        print(f"  方法: {critic_result['method']}")
        print(f"  分析:\n{critic_result['output'][:500]}")
        write_ssb_event(
            "CRITIC",
            f"CRITIC分析: {len(all_critic)} 个偏离",
            json.dumps(
                {"deviations": all_critic, "critic": critic_result}, ensure_ascii=False
            ),
            "MED" if classified["p0"] else "LOW",
            "EXECUTE" if classified["p1"] else "NONE",
        )

    # Step 5: 决策
    print("\n▶ 步骤5: 决策")
    if classified["p0"]:
        print("  🔴 P0 偏离: 必须人类确认 — 跳过自动回滚")
        write_ssb_event(
            "STATE_CHANGE",
            f"P0偏离需人工确认: {classified['p0'][0]['label']}",
            json.dumps({"classified": classified}, ensure_ascii=False),
            "HIGH",
            "HUMAN_CONFIRM",
        )
    elif classified["p1"]:
        print("  🟡 P1 偏离: 自动执行 CRITIC 回滚")
        # 保存当前状态作为回滚前的最后检查点
        save_checkpoint()
        rollback_result = auto_rollback()
        if rollback_result["success"]:
            print(f"  ✅ 自动回滚完成: {' + '.join(rollback_result['restored'])}")
            write_ssb_event(
                "STATE_CHANGE",
                f"自动回滚完成: {' + '.join(rollback_result['restored'])}",
                json.dumps(rollback_result, ensure_ascii=False),
                "LOW",
                "REVIEW",
            )
        else:
            print(f"  ❌ 自动回滚失败: {rollback_result['reason']}")
    else:
        print("  ⚪ P2 以下: 仅标记，无需回滚")

    print("\n✅ 分析完成")
    return 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description="涌现自调自动化")
    parser.add_argument("--analyze", action="store_true", help="完整分析 (默认)")
    parser.add_argument("--rollback", action="store_true", help="手动回滚")
    parser.add_argument("--status", action="store_true", help="状态")
    args = parser.parse_args()

    if not any([args.analyze, args.rollback, args.status]):
        args.analyze = True

    if args.status:
        data, err = get_deviations()
        if err:
            print(f"状态: {err}")
            return 1
        if not data:
            print("状态: 无基线")
            return 1
        diffs = data["differences"]
        classified = classify_deviations(diffs) if diffs else {}
        print(f"最近快照: {data['current']['date']}")
        print(f"偏离数: {len(diffs)}")
        if diffs:
            print(f"  P0: {len(classified.get('p0', []))}")
            print(f"  P1: {len(classified.get('p1', []))}")
            print(f"  P2: {len(classified.get('p2', []))}")
        else:
            print("  状态: ✅ 正常")
        return 0

    if args.rollback:
        ok = auto_rollback()
        print(
            f"回滚: {'成功' if ok['success'] else '失败: ' + ok.get('reason', '未知')}"
        )
        return 0 if ok["success"] else 1

    return analyze()


if __name__ == "__main__":
    sys.exit(main())
