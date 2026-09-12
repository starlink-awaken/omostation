#!/usr/bin/env python3
"""Calibration Engine — continuous scene trust scoring with sliding window."""

from __future__ import annotations
import argparse, json, sqlite3, sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_DB_PATH = _ROOT / "data" / "scene-metrics.db"

def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    # Performance: WAL mode for concurrent reads + busy timeout
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-8000")  # 8MB cache
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scene_execution (id TEXT PRIMARY KEY, scene_id TEXT NOT NULL,
            run_id TEXT NOT NULL, status TEXT NOT NULL, confidence REAL DEFAULT 0.0,
            success INTEGER DEFAULT 0, duration_ms INTEGER DEFAULT 0, token_usage INTEGER DEFAULT 0,
            tool_calls INTEGER DEFAULT 0, human_reviewed INTEGER DEFAULT 0, human_agreed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS scene_calibration (id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id TEXT NOT NULL, window_days INTEGER NOT NULL, sample_count INTEGER DEFAULT 0,
            calibration_score REAL DEFAULT 0.0, precision REAL DEFAULT 0.0, recall REAL DEFAULT 0.0,
            false_positive_rate REAL DEFAULT 0.0, avg_duration_ms REAL DEFAULT 0.0,
            avg_token_usage REAL DEFAULT 0.0, intervention_rate REAL DEFAULT 0.0,
            trend_14d REAL DEFAULT 0.0, computed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS scene_lifecycle_log (id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id TEXT NOT NULL, from_level TEXT, to_level TEXT NOT NULL, reason TEXT,
            calibration_score REAL DEFAULT 0.0, actor TEXT DEFAULT 'calibration-engine', created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_exec_scene ON scene_execution(scene_id);
        CREATE INDEX IF NOT EXISTS idx_exec_created ON scene_execution(created_at);
        CREATE INDEX IF NOT EXISTS idx_cal_scene ON scene_calibration(scene_id);
    """); conn.commit(); return conn

def record_execution(scene_id, run_id, result) -> None:
    conn = _get_db()
    conn.execute("INSERT OR REPLACE INTO scene_execution (id,scene_id,run_id,status,confidence,success,duration_ms,token_usage,tool_calls,human_reviewed,human_agreed,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, scene_id, run_id, result.get("status","unknown"), result.get("confidence",0.0),
         1 if result.get("status")=="succeeded" else 0, result.get("duration_ms",0),
         result.get("token_usage",0), result.get("tool_calls",0),
         1 if result.get("human_reviewed") else 0, 1 if result.get("human_agreed") else 0, datetime.now(UTC).isoformat()))
    conn.commit(); conn.close()
    _write_llm_cost(scene_id, run_id, result)


def _write_llm_cost(scene_id: str, run_id: str, result: dict) -> None:
    """Bridge token_usage to llm_cost.jsonl (X3/K1 LLM cost tracking fix)."""
    try:
        import os
        token_usage = int(result.get("token_usage") or 0)
        if token_usage <= 0:
            return
        cost_file = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime"))) / "data" / "llm_cost.jsonl"
        cost_file.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "scene_id": scene_id,
            "run_id": run_id,
            "token_usage": token_usage,
            "source": "scene-execution",
            "estimated_cost_usd": round(token_usage * 0.000001, 6),
        }
        with open(cost_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # cost bridge is non-blocking

def compute_calibration(scene_id, window_days=30) -> dict:
    conn = _get_db()
    since = (datetime.now(UTC) - timedelta(days=window_days)).isoformat()
    row = conn.execute("""SELECT COUNT(*) as total, SUM(success) as successes,
        AVG(confidence) as avg_conf, AVG(duration_ms) as avg_dur, AVG(token_usage) as avg_tok,
        SUM(CASE WHEN human_reviewed=1 AND human_agreed=0 THEN 1 ELSE 0 END) as rejects,
        SUM(CASE WHEN human_reviewed=1 THEN 1 ELSE 0 END) as reviewed
        FROM scene_execution WHERE scene_id=? AND created_at>=?""", (scene_id, since)).fetchone()
    total, successes = row["total"] or 0, row["successes"] or 0
    avg_conf = row["avg_conf"] or 0.0
    precision = successes/total if total > 0 else 0.0
    fp_rate = row["rejects"]/row["reviewed"] if row["reviewed"] else 0.0
    intervention = row["reviewed"]/total if total > 0 else 0.0
    score = precision*0.4 + avg_conf*0.3 + max(0, 1.0-fp_rate/0.2)*0.3
    prev = conn.execute("""SELECT AVG(confidence) as pc FROM scene_execution WHERE scene_id=? AND created_at>=? AND created_at<?""",
        (scene_id, (datetime.now(UTC)-timedelta(days=window_days*2)).isoformat(), since)).fetchone()
    trend = avg_conf - (prev["pc"] or 0.0)
    result = {"scene_id":scene_id,"window_days":window_days,"sample_count":total,
              "calibration_score":round(score,4),"precision":round(precision,4),
              "avg_confidence":round(avg_conf,4),"false_positive_rate":round(fp_rate,4),
              "avg_duration_ms":round(row["avg_dur"] or 0.0,1),"avg_token_usage":round(row["avg_tok"] or 0.0,1),
              "intervention_rate":round(intervention,4),"trend_14d":round(trend,4),"computed_at":datetime.now(UTC).isoformat()}
    conn.execute("""INSERT INTO scene_calibration (scene_id,window_days,sample_count,calibration_score,
        precision,false_positive_rate,avg_duration_ms,avg_token_usage,intervention_rate,trend_14d,computed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (scene_id,window_days,total,result["calibration_score"],
        result["precision"],result["false_positive_rate"],result["avg_duration_ms"],
        result["avg_token_usage"],result["intervention_rate"],result["trend_14d"],result["computed_at"]))
    conn.commit(); conn.close(); return result

def check_promotion_gates(scene_id, target_level) -> dict:
    cal = compute_calibration(scene_id)
    thresholds = {"assisted":{"min_samples":3,"min_calibration":0.5,"min_precision":0.5,"max_fp":0.3},
                  "supervised":{"min_samples":30,"min_calibration":0.6,"min_precision":0.7,"max_fp":0.15},
                  "routine":{"min_samples":100,"min_calibration":0.8,"min_precision":0.8,"max_fp":0.05}}
    t = thresholds.get(target_level, {})
    if not t: return {"eligible":False,"reason":f"unknown level: {target_level}"}
    gates = {"sufficient_samples": cal["sample_count"] >= t["min_samples"],
             "calibration_threshold": cal["calibration_score"] >= t["min_calibration"],
             "precision_threshold": cal["precision"] >= t["min_precision"],
             "fp_rate_threshold": cal["false_positive_rate"] <= t["max_fp"],
             "no_regression": cal["trend_14d"] >= -0.05}
    return {"eligible":all(gates.values()),"scene_id":scene_id,"target_level":target_level,
            "calibration":cal,"gates":gates,"failing_gates":[k for k,v in gates.items() if not v]}

def check_demotion_triggers(scene_id) -> dict:
    cal = compute_calibration(scene_id); triggers = []
    if cal["sample_count"] >= 10:
        if cal["calibration_score"] < 0.5: triggers.append({"condition":"calibration < 0.5","action":"demote_to_shadow","severity":"high"})
        elif cal["calibration_score"] < 0.6 and cal["sample_count"] >= 30: triggers.append({"condition":"calibration < 0.6","action":"demote_to_shadow","severity":"medium"})
        if cal["false_positive_rate"] > 0.2: triggers.append({"condition":"fp_rate > 0.2","action":"demote_one_level","severity":"high"})
        if cal["trend_14d"] < -0.15: triggers.append({"condition":"calibration dropping > 0.15","action":"demote_one_level","severity":"medium"})
    return {"scene_id":scene_id,"demote":len(triggers)>0,"triggers":triggers,"calibration":cal}

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    rp = sub.add_parser("record"); rp.add_argument("--scene-id",required=True); rp.add_argument("--run-id",required=True); rp.add_argument("--result",type=json.loads,required=True)
    cp = sub.add_parser("compute"); cp.add_argument("--scene-id",required=True); cp.add_argument("--window",type=int,default=30)
    gp = sub.add_parser("check-gates"); gp.add_argument("--scene-id",required=True); gp.add_argument("--target-level",required=True)
    dp = sub.add_parser("check-demotion"); dp.add_argument("--scene-id",required=True)
    lp = sub.add_parser("list")
    ap = sub.add_parser("daily", help="Run daily calibration cycle for all scenes")
    args = parser.parse_args(argv); cmd = args.command or "list"
    if cmd == "record": record_execution(args.scene_id,args.run_id,args.result); print(json.dumps({"status":"ok"})); return 0
    if cmd == "compute": print(json.dumps(compute_calibration(args.scene_id,args.window),ensure_ascii=False,indent=2)); return 0
    if cmd == "check-gates": r = check_promotion_gates(args.scene_id,args.target_level); print(json.dumps(r,ensure_ascii=False,indent=2)); return 0 if r["eligible"] else 1
    if cmd == "check-demotion": print(json.dumps(check_demotion_triggers(args.scene_id),ensure_ascii=False,indent=2)); return 0
    if cmd == "daily":
        conn = _get_db()
        rows = conn.execute("SELECT DISTINCT scene_id FROM scene_execution").fetchall(); conn.close()
        alerts = 0; promoted = 0; auto_applied = 0
        lifecycle_path = _ROOT / ".omo" / "_truth" / "scenarios" / "v3"
        for r in rows:
            sid = r["scene_id"]
            cal = compute_calibration(sid)
            demo = check_demotion_triggers(sid)
            if demo["demote"]:
                print(f"[DEMOTION] {sid}: {demo['triggers']}"); alerts += 1
                _auto_transition(sid, "shadow", "calibration-engine")
            for level in ("assisted","supervised","routine"):
                gates = check_promotion_gates(sid, level)
                if gates["eligible"]:
                    print(f"[PROMOTION] {sid} → {level} (score={cal['calibration_score']:.3f})"); promoted += 1
                    # Auto-apply promotion for assisted (supervised/routine need human)
                    if level == "assisted":
                        card_path = lifecycle_path / f"{sid}.yaml"
                        if card_path.is_file() and _auto_transition(sid, level, "calibration-engine"):
                            auto_applied += 1
                    break
        print(f"Daily cycle: {len(rows)} scenes, {alerts} demotion alerts, {promoted} promotion candidates, {auto_applied} auto-applied")
        return 0

def _auto_transition(scene_id: str, target_level: str, actor: str) -> bool:
    """Auto-apply lifecycle transition. Returns True on success."""
    try:
        import subprocess as _sp
        lifecycle_script = _ROOT / "bin" / "ssot" / "scene-card-lifecycle.py"
        card_path = _ROOT / ".omo" / "_truth" / "scenarios" / "v3" / f"{scene_id}.yaml"
        if not card_path.is_file() or not lifecycle_script.is_file():
            return False
        result = _sp.run(
            [sys.executable, str(lifecycle_script), "transition",
             "--scene-card", str(card_path), "--tier", target_level, "--actor", actor],
            capture_output=True, text=True, timeout=15, cwd=str(_ROOT),
        )
        return result.returncode == 0
    except Exception:
        return False
    conn = _get_db(); rows = conn.execute("SELECT DISTINCT scene_id FROM scene_execution ORDER BY scene_id").fetchall(); conn.close()
    print(f"{'Scene ID':<40} {'Samples':>8} {'Score':>8} {'FP Rate':>8} {'Trend':>8}\n{'-'*76}")
    for r in rows:
        c = compute_calibration(r["scene_id"])
        print(f"{r['scene_id']:<40} {c['sample_count']:>8} {c['calibration_score']:>8.3f} {c['false_positive_rate']:>8.3f} {c['trend_14d']:>8.3f}")
    return 0

if __name__ == "__main__": raise SystemExit(main())
