#!/usr/bin/env python3
"""Calibration Engine — continuous scene trust scoring with sliding window.

Fallback-chain contract (SSOT: ``.omo/standards/scene-card-lifecycle.yaml``):
- ONE canonical demotion rule: executed tiers (assisted+) with ≥ 10 samples
  and a single calibration reading < 0.5 → demote exactly one level.
- Proposal-only: this engine NEVER auto-applies a transition. Demote and
  promote outcomes are written to ``scene_lifecycle_log`` with a
  ``needs_human/`` reason and executed solely by an explicit human command
  (``scene-card-lifecycle.py transition --actor``, ``omo scene demote``,
  cockpit demote). Never auto-activate.
"""

from __future__ import annotations
import argparse, json, os, sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]


def _default_db_path(root: Path | None = None) -> Path:
    """校准库路径：默认 data/scene-metrics.db，可用 SCENE_METRICS_DB 覆盖.

    为什么需要覆盖：测试若直接跑生产库, 会把夹具 scene_id (test-scene /
    gate-test-scene / ...) 写进生产校准表, 而夹具样本数足以通过晋升门禁
    (gate-test-scene 35 samples → eligible:true)。校准库是信任平面的证据源,
    被夹具污染即违反"真实数据"约束。
    """
    override = os.environ.get("SCENE_METRICS_DB")
    if override:
        return Path(override).expanduser().resolve()
    return (root or _ROOT) / "data" / "scene-metrics.db"


_DB_PATH = _default_db_path()

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

# Canonical gates, mirroring the SSOT promotion block. SSOT remains
# authoritative; these defaults apply only if the SSOT file is unreadable.
# NOTE on naming: engine target "assisted" = first executable tier, i.e.
# the cruiser draft→shadow 3-sample gate. supervised/routine match by name.
_PROMOTION_DEFAULTS = {"assisted": {"min_samples": 3, "min_calibration": 0.5, "min_precision": 0.5, "max_fp": 0.3},
              "supervised": {"min_samples": 30, "min_calibration": 0.6, "min_precision": 0.7, "max_fp": 0.15},
              "routine": {"min_samples": 100, "min_calibration": 0.8, "min_precision": 0.8, "max_fp": 0.05}}

# Lifecycle order for one-level demotion proposals (mirrors SSOT + cruiser).
_ORDER = ("draft", "shadow", "assisted", "supervised", "routine")


def _promotion_thresholds() -> dict:
    """Load promotion gates from SSOT, falling back to compiled defaults."""
    try:
        import yaml
        doc = yaml.safe_load((_ROOT / ".omo" / "standards" / "scene-card-lifecycle.yaml").read_text(encoding="utf-8")) or {}
        promo = doc.get("promotion") or {}
        out = {}
        for level, default in _PROMOTION_DEFAULTS.items():
            node = promo.get(level) or {}
            out[level] = {"min_samples": int(node.get("min_samples", default["min_samples"])),
                          "min_calibration": float(node.get("min_calibration", default["min_calibration"])),
                          "min_precision": default["min_precision"], "max_fp": default["max_fp"]}
        return out
    except Exception:
        return {k: dict(v) for k, v in _PROMOTION_DEFAULTS.items()}


def _current_lifecycle(scene_id: str) -> str | None:
    """Read the current lifecycle tier from the scene card (read-only)."""
    import yaml
    for base in (_ROOT / ".omo" / "_truth" / "scenarios" / "v3", _ROOT / "docs" / "scene-cards"):
        card = base / f"{scene_id}.yaml"
        if not card.is_file():
            continue
        try:
            docs = list(yaml.safe_load_all(card.read_text(encoding="utf-8")))
            body = docs[-1] if len(docs) > 1 else docs[0]
            if isinstance(body, dict) and body.get("lifecycle") in _ORDER:
                return body["lifecycle"]
        except Exception:
            continue
    return None


def _log_proposal(scene_id: str, to_level: str, reason: str, calibration_score: float,
                  actor: str = "calibration-engine") -> None:
    """Persist a needs_human proposal to scene_lifecycle_log (the human-gate sink).

    This is the ONLY write this engine performs besides calibration evidence.
    It never touches scene card YAML — execution stays a human command.
    """
    from_level = _current_lifecycle(scene_id)
    conn = _get_db()
    conn.execute("INSERT INTO scene_lifecycle_log (scene_id,from_level,to_level,reason,calibration_score,actor,created_at)"
                 " VALUES (?,?,?,?,?,?,?)",
                 (scene_id, from_level, to_level, reason, calibration_score, actor, datetime.now(UTC).isoformat()))
    conn.commit(); conn.close()


def _eval_gates(cal: dict, target_level: str) -> dict:
    """Pure gate evaluation against one calibration reading (no DB writes)."""
    thresholds = _promotion_thresholds()
    t = thresholds.get(target_level, {})
    if not t: return {"eligible": False, "reason": f"unknown level: {target_level}"}
    gates = {"sufficient_samples": cal["sample_count"] >= t["min_samples"],
             "calibration_threshold": cal["calibration_score"] >= t["min_calibration"],
             "precision_threshold": cal["precision"] >= t["min_precision"],
             "fp_rate_threshold": cal["false_positive_rate"] <= t["max_fp"],
             "no_regression": cal["trend_14d"] >= -0.05}
    out = {"eligible": all(gates.values()), "target_level": target_level,
           "calibration": cal, "gates": gates, "failing_gates": [k for k, v in gates.items() if not v]}
    if target_level == "routine":
        out["needs_human"] = True  # routine never auto-promotes, even when eligible
    return out


def check_promotion_gates(scene_id, target_level) -> dict:
    cal = compute_calibration(scene_id)
    out = _eval_gates(cal, target_level)
    out["scene_id"] = scene_id
    return out

def check_demotion_triggers(scene_id, cal: dict | None = None) -> dict:
    """Canonical SSOT demotion rule, proposal-only.

    ONE rule: sample_count ≥ 10 AND calibration_score < 0.5 →
    a single ``demote_one_level`` trigger. Deliberately NOT included:
    - ``< 0.6 (n ≥ 30)`` medium trigger: sits exactly on the 0.6 promotion
      gate and would oscillate promote/demote on the same reading.
    - ``fp_rate > 0.2`` / ``trend < -0.15`` triggers: second-guess the
      composite score with its own inputs; the score already prices in
      false-positive rejections.
    - retro 3× ``< 0.4``: scene-local note, needs run history this engine
      does not track, and detects decay later than the 0.5 floor.
    Pass ``cal`` to reuse one reading (avoids a duplicate calibration row).
    """
    if cal is None:
        cal = compute_calibration(scene_id)
    triggers = []
    if cal["sample_count"] >= 10 and cal["calibration_score"] < 0.5:
        triggers.append({"condition": "calibration < 0.5", "action": "demote_one_level", "severity": "high"})
    return {"scene_id": scene_id, "demote": len(triggers) > 0, "triggers": triggers, "calibration": cal}


def _demote_target(scene_id: str) -> str:
    """One level below the card's current tier (fallback: demote_one_level)."""
    current = _current_lifecycle(scene_id)
    if current in _ORDER:
        idx = _ORDER.index(current)
        if idx > 0:
            return _ORDER[idx - 1]
    return "demote_one_level"

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    rp = sub.add_parser("record"); rp.add_argument("--scene-id",required=True); rp.add_argument("--run-id",required=True); rp.add_argument("--result",type=json.loads,required=True)
    cp = sub.add_parser("compute"); cp.add_argument("--scene-id",required=True); cp.add_argument("--window",type=int,default=30)
    gp = sub.add_parser("check-gates"); gp.add_argument("--scene-id",required=True); gp.add_argument("--target-level",required=True)
    dp = sub.add_parser("check-demotion"); dp.add_argument("--scene-id",required=True)
    vp = sub.add_parser("verify", help="Verify T7 fallback chain (thresholds + human gate + store proof)")
    vp.add_argument("--root", type=Path, default=_ROOT)
    vp.add_argument("--json", action="store_true")
    lp = sub.add_parser("list", help="List latest calibration per scene (read-only, no new rows)")
    ap = sub.add_parser("daily", help="Run daily calibration cycle for all scenes (proposal-only, never auto-applies)")
    args = parser.parse_args(argv); cmd = args.command or "list"
    if cmd == "record": record_execution(args.scene_id,args.run_id,args.result); print(json.dumps({"status":"ok"})); return 0
    if cmd == "compute": print(json.dumps(compute_calibration(args.scene_id,args.window),ensure_ascii=False,indent=2)); return 0
    if cmd == "check-gates": r = check_promotion_gates(args.scene_id,args.target_level); print(json.dumps(r,ensure_ascii=False,indent=2)); return 0 if r["eligible"] else 1
    if cmd == "check-demotion":
        demo = check_demotion_triggers(args.scene_id)
        if demo["demote"]:
            for t in demo["triggers"]:
                _log_proposal(args.scene_id, _demote_target(args.scene_id),
                              f"needs_human/demote/calibration-drop ({t['condition']}, action={t['action']})",
                              demo["calibration"]["calibration_score"])
            print(json.dumps({**demo, "proposal": "logged to scene_lifecycle_log; execute via human command"}, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(demo, ensure_ascii=False, indent=2))
        return 0
    if cmd == "verify":
        result = verify_chain(args.root)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Scene Calibration Fallback: {result['overall']}")
            for c in result["checks"]:
                icon = "OK" if c["status"] in ("PASS", "PRESENT") else ("--" if c["status"] == "EMPTY" else "FAIL")
                print(f"  [{icon}] {c['name']}: {c['status']}")
        return 0 if result["overall"] == "PASS" else 1
    if cmd == "list": return _cmd_list()
    if cmd == "daily":
        conn = _get_db()
        rows = conn.execute("SELECT DISTINCT scene_id FROM scene_execution").fetchall(); conn.close()
        proposals = 0; candidates = 0
        for r in rows:
            sid = r["scene_id"]
            cal = compute_calibration(sid)  # one evidence row per scene per cycle
            demo = check_demotion_triggers(sid, cal=cal)
            if demo["demote"]:
                print(f"[PROPOSAL demote] {sid}: {demo['triggers']}"); proposals += 1
                for t in demo["triggers"]:
                    _log_proposal(sid, _demote_target(sid),
                                  f"needs_human/demote/calibration-drop ({t['condition']}, action={t['action']})",
                                  cal["calibration_score"])
                continue  # demote proposals take precedence over promotion candidates
            for level in ("assisted", "supervised", "routine"):
                gates = _eval_gates(cal, level)
                if gates["eligible"]:
                    print(f"[PROPOSAL promote] {sid} → {level} (score={cal['calibration_score']:.3f}, needs human command)"); candidates += 1
                    _log_proposal(sid, level, f"needs_human/promote/{level} (score={cal['calibration_score']:.3f})",
                                  cal["calibration_score"])
                    break
        print(f"Daily cycle: {len(rows)} scenes, {proposals} demote proposals, {candidates} promotion candidates, 0 auto-applied (human gate)")
        return 0

def _cmd_list() -> int:
    """Read-only latest-calibration listing (writes no evidence rows)."""
    db_path = _default_db_path()
    if not db_path.is_file():
        print("No calibration store yet (data/scene-metrics.db missing).")
        return 0
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "scene_calibration" not in tables:
            print("No scene_calibration table yet.")
            return 0
        rows = conn.execute("""SELECT scene_id, sample_count, calibration_score, false_positive_rate, trend_14d, computed_at
            FROM scene_calibration WHERE id IN (SELECT MAX(id) FROM scene_calibration GROUP BY scene_id)
            ORDER BY scene_id""").fetchall()
    finally:
        conn.close()
    if not rows:
        print("No calibration readings yet — run compute/check-demotion/daily first.")
        return 0
    print(f"{'Scene ID':<40} {'Samples':>8} {'Score':>8} {'FP Rate':>8} {'Trend':>8}")
    print("-" * 76)
    for r in rows:
        print(f"{r['scene_id']:<40} {r['sample_count']:>8} {r['calibration_score']:>8.3f} {r['false_positive_rate']:>8.3f} {r['trend_14d']:>8.3f}")
    return 0


def verify_chain(root: Path) -> dict:
    """T7 fallback-chain verifier (panorama consumption point).

    A. threshold agreement: SSOT demotion floor/min_samples == 0.5/10, the
       engine's canonical trigger uses exactly those bounds with a single
       ``demote_one_level`` action, and the cruiser ``_DEMOTE_CALIBRATION``
       equals the SSOT floor.
    B. human gate intact: this engine defines no ``_auto_transition`` and
       imports no ``subprocess`` (it cannot shell out to a card transition),
       and the SSOT ``human_gate.never_auto_activate`` is true.
    C. consumption proof (informational): scene_calibration /
       scene_lifecycle_log row counts — EMPTY never fails the run.
    """
    import ast as _ast

    def _ssot() -> dict:
        import yaml
        with open(root / ".omo" / "standards" / "scene-card-lifecycle.yaml", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # --- A ---
    demotion = _ssot().get("demotion", {}) or {}
    ssot_floor, ssot_min = demotion.get("calibration_floor"), demotion.get("min_samples")
    ssot_action = demotion.get("action")
    cruiser_src = root / "projects" / "omo" / "src" / "omo" / "scene" / "cruiser.py"
    cruiser_floor = None
    if cruiser_src.is_file():
        tree = _ast.parse(cruiser_src.read_text(encoding="utf-8"), filename=str(cruiser_src))
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Assign) and any(
                    isinstance(t, _ast.Name) and t.id == "_DEMOTE_CALIBRATION" for t in node.targets):
                if isinstance(node.value, _ast.Constant):
                    cruiser_floor = node.value.value
    engine_src = root / "bin" / "ssot" / "calibration-engine.py"
    engine_text = engine_src.read_text(encoding="utf-8")
    engine_tree = _ast.parse(engine_text, filename=str(engine_src))
    lt_floors: list = []
    sample_floors: list = []
    demote_fn: _ast.FunctionDef | None = None
    for node in _ast.walk(engine_tree):
        if isinstance(node, _ast.FunctionDef) and node.name == "check_demotion_triggers":
            demote_fn = node
            break
    fn_consts: list = []
    if demote_fn is not None:
        for sub in _ast.walk(demote_fn):
            if isinstance(sub, _ast.Compare) and len(sub.ops) == 1 and len(sub.comparators) == 1:
                comp = sub.comparators[0]
                if isinstance(comp, _ast.Constant) and isinstance(comp.value, (int, float)):
                    if isinstance(sub.ops[0], _ast.Lt):
                        lt_floors.append(comp.value)
                    elif isinstance(sub.ops[0], (_ast.GtE, _ast.Gt)):
                        sample_floors.append(comp.value)
            elif isinstance(sub, _ast.Constant) and isinstance(sub.value, str):
                fn_consts.append(sub.value)
    single_rule = "demote_one_level" in fn_consts and not any("demote_to_shadow" in c for c in fn_consts)
    a_ok = bool(ssot_floor == 0.5 == cruiser_floor and ssot_min == 10 and 10 in sample_floors
                and lt_floors == [0.5] and ssot_action == "demote_one_level" and single_rule)
    check_a = {"name": "threshold-agreement", "status": "PASS" if a_ok else "FAIL",
               "detail": {"ssot_floor": ssot_floor, "ssot_min_samples": ssot_min, "ssot_action": ssot_action,
                          "cruiser_demote_calibration": cruiser_floor,
                          "engine_lt_floors": sorted(set(lt_floors)),
                          "engine_sample_floors": sorted(set(sample_floors)),
                          "engine_single_rule": single_rule}}
    # --- B: precise AST check, not substring ---
    def_names = [n.name for n in _ast.walk(engine_tree) if isinstance(n, _ast.FunctionDef)]
    imported: set = set()
    for n in _ast.walk(engine_tree):
        if isinstance(n, _ast.Import):
            imported.update((a.asname or a.name).split(".")[0] for a in n.names)
        elif isinstance(n, _ast.ImportFrom) and n.module:
            imported.add(n.module.split(".")[0])
    no_auto = "_auto_transition" not in def_names and not any(
        isinstance(n, _ast.Call) and getattr(n.func, "id", "") == "_auto_transition"
        for n in _ast.walk(engine_tree))
    no_sub = "subprocess" not in imported
    has_gate = bool((_ssot().get("human_gate") or {}).get("never_auto_activate") is True)
    b_ok = bool(no_auto and no_sub and has_gate)
    check_b = {"name": "human-gate", "status": "PASS" if b_ok else "FAIL",
               "detail": {"engine_no_auto_transition": no_auto,
                          "engine_no_subprocess": no_sub,
                          "ssot_never_auto_activate": has_gate}}
    # --- C (informational only) ---
    db_path = _default_db_path(root)
    if not db_path.is_file():
        check_c = {"name": "consumption-proof", "status": "EMPTY",
                   "detail": {"note": "no executions recorded yet — chain wired, awaiting data"}}
    else:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            cal_n = conn.execute("SELECT COUNT(*) FROM scene_calibration").fetchone()[0] if "scene_calibration" in tables else 0
            log_n = conn.execute("SELECT COUNT(*) FROM scene_lifecycle_log").fetchone()[0] if "scene_lifecycle_log" in tables else 0
            prop_n = conn.execute("SELECT COUNT(*) FROM scene_lifecycle_log WHERE reason LIKE 'needs_human/%'").fetchone()[0] if "scene_lifecycle_log" in tables else 0
            conn.close()
            check_c = {"name": "consumption-proof",
                       "status": "PRESENT" if (cal_n or log_n) else "EMPTY",
                       "detail": {"scene_calibration_rows": cal_n, "scene_lifecycle_log_rows": log_n,
                                  "human_gate_proposal_rows": prop_n}}
        except Exception as exc:
            check_c = {"name": "consumption-proof", "status": "ERROR", "detail": {"error": str(exc)}}
    checks = [check_a, check_b, check_c]
    return {"overall": "PASS" if all(c["status"] == "PASS" for c in checks[:2]) else "FAIL",
            "checks": checks}


if __name__ == "__main__": raise SystemExit(main())
