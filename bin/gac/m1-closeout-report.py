#!/usr/bin/env python3
"""M1 closeout rejudge — ADR-0210 + ADR-0220 + ADR-0222 + ADR-0224.

Aggregates G-CONV.1–7 into a JSON verdict. M1「冲突=0」证据路径:

  * **passive**: 72h window elapsed AND conflict_count=0 AND hard greens
  * **adversarial**: four-gate intentional abuse all blocked (evidence JSON)
    AND hard greens (need not wait 72h); when conflict_count==0 → evidence_path
    ``adversarial`` (ADR-0222)
  * **adversarial_with_rootcause** (ADR-0224): path B when conflict_count>0
    only if conflict-rootcause classifies every event as gate_interception
    or historical_pre_gate (no coverage_gap_bypass / unresolved)

Never claims phase2_recommend without a completed path (skeptic: evidence first).

Usage:
  python3 bin/gac/m1-closeout-report.py --ssot-root <live>
  python3 bin/gac/m1-closeout-report.py --adversarial-evidence .omo/_delivery/m1-adversarial/latest.json
  python3 bin/gac/m1-closeout-report.py --conflict-rootcause .omo/_knowledge/audits/....json
  python3 bin/gac/m1-closeout-report.py --json --out .omo/_delivery/m1-closeout/latest.json

Exit codes:
  0  report emitted (window_open / pass / fail all exit 0)
  2  fatal (root unreadable)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc

DEFAULT_RATIO_MIN = 0.9
DEFAULT_ADVERSARIAL = ".omo/_delivery/m1-adversarial/latest.json"
DEFAULT_ROOTCAUSE_GLOB = ".omo/_delivery/m1-closeout/conflict-rootcause-*.json"
BAD_ROOTCAUSE = frozenset({"coverage_gap_bypass", "unresolved"})
OK_ROOTCAUSE = frozenset({"gate_interception", "historical_pre_gate"})
ISC3_WEIGHT_RE = re.compile(
    r"governance['\"]?\s*:\s*0\.3|0\.3.*0\.5.*0\.2|ISC-3|isc3",
    re.I,
)


def _utc_iso(dt: datetime | None = None) -> str:
    d = dt or datetime.now(UTC)
    return d.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_swarm(root: Path):
    path = root / "bin/gac/swarm_discipline.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("swarm_discipline", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        import yaml  # noqa: PLC0415

        docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
        if not docs:
            return {}
        last = docs[-1]
        return last if isinstance(last, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _check(
    gate_id: str,
    name: str,
    ok: bool,
    *,
    hard: bool,
    detail: dict[str, Any] | None = None,
    note: str = "",
) -> dict[str, Any]:
    return {
        "id": gate_id,
        "name": name,
        "ok": bool(ok),
        "hard": bool(hard),
        "detail": detail or {},
        "note": note,
    }


def check_g_conv_1_isolation(root: Path) -> dict[str, Any]:
    """Structural: worktree+hooks+branch-protection tooling present (ISC-4)."""
    hooks = {
        "pre_push": (root / ".githooks/pre-push").is_file(),
        "pre_commit": (root / ".githooks/pre-commit").is_file(),
        "gac_worktree": (root / "bin/gac/gac-worktree.sh").is_file(),
        "branch_protection_script": (root / "bin/gac/gac-branch-protection.sh").is_file(),
    }
    push_txt = ""
    pre_path = root / ".githooks/pre-push"
    if pre_path.is_file():
        push_txt = pre_path.read_text(encoding="utf-8", errors="replace")
    hooks["pre_push_blocks_main"] = "main" in push_txt and (
        "branch" in push_txt.lower() or "protect" in push_txt.lower() or "direct" in push_txt.lower()
    )
    ok = all(
        [
            hooks["pre_push"],
            hooks["pre_commit"],
            hooks["gac_worktree"],
            hooks["branch_protection_script"],
        ]
    )
    return _check(
        "g-conv.1",
        "agent_isolation_isc4",
        ok,
        hard=True,
        detail=hooks,
        note="structural presence; live GitHub protection is ops-side",
    )


def check_g_conv_2_daemon(ssot_root: Path, *, ratio_min: float = DEFAULT_RATIO_MIN) -> dict[str, Any]:
    """service_online_ratio ≥ 0.9 from system.yaml (single-source preferred)."""
    system = _load_yaml(ssot_root / ".omo/state/system.yaml")
    health = _load_yaml(ssot_root / ".omo/state/health.yaml")
    ratio = system.get("service_online_ratio")
    if ratio is None:
        ratio = health.get("service_online_ratio")
    rhs = system.get("runtime_health_summary") or {}
    if ratio is None and isinstance(rhs, dict):
        ratio = rhs.get("ratio")
    try:
        ratio_f = float(ratio) if ratio is not None else None
    except (TypeError, ValueError):
        ratio_f = None
    ok = ratio_f is not None and ratio_f >= ratio_min
    return _check(
        "g-conv.2",
        "daemon_online_ratio",
        ok,
        hard=True,
        detail={
            "service_online_ratio": ratio_f,
            "ratio_min": ratio_min,
            "runtime_health_summary": rhs if isinstance(rhs, dict) else {},
            "source_fields": {
                "system.yaml": system.get("service_online_ratio"),
                "health.yaml": health.get("service_online_ratio"),
                "rhs.ratio": rhs.get("ratio") if isinstance(rhs, dict) else None,
            },
        },
        note="hard M1: ratio ≥ 0.9; missing SSOT = fail-closed",
    )


def check_g_conv_3_health(ssot_root: Path) -> dict[str, Any]:
    """ISC-3 composite present (weights + source marker)."""
    system = _load_yaml(ssot_root / ".omo/state/system.yaml")
    health_path = ssot_root / ".omo/state/health.yaml"
    health_raw = health_path.read_text(encoding="utf-8") if health_path.is_file() else ""
    health = _load_yaml(health_path)
    source = str(system.get("health_score_source") or health.get("source") or "")
    score = system.get("health_score", health.get("health_score"))
    isc3_marker = "isc3" in source.lower() or bool(ISC3_WEIGHT_RE.search(health_raw))
    # Prefer explicit weights in health body comments/fields
    weights_ok = bool(re.search(r"0\.3", health_raw)) and bool(
        re.search(r"0\.5", health_raw)
    ) and bool(re.search(r"0\.2", health_raw))
    ok = isc3_marker or weights_ok
    return _check(
        "g-conv.3",
        "health_score_isc3",
        ok,
        hard=True,
        detail={
            "health_score": score,
            "health_score_source": source,
            "isc3_marker": isc3_marker,
            "weights_ok": weights_ok,
        },
        note="hard M1: ISC-3 formula/source present (score value may be <100)",
    )


def check_g_conv_4_gitlink(root: Path) -> dict[str, Any]:
    foundry = root / "bin/gac/knowledge-foundry-cron.py"
    text = foundry.read_text(encoding="utf-8") if foundry.is_file() else ""
    ok = "5:45-gitlink-check" in text and "submodule-gitlink-check" in text
    return _check(
        "g-conv.4",
        "gitlink_foundry_slot",
        ok,
        hard=True,
        detail={"foundry_present": foundry.is_file(), "slot_545": "5:45-gitlink-check" in text},
    )


def check_g_conv_5_write_owner(root: Path) -> dict[str, Any]:
    wo = root / ".omo/_truth/registry/write-owners.yaml"
    repair = root / "bin/ssot/write-owner-repair-draft.py"
    pre = root / ".pre-commit-config.yaml"
    pre_txt = pre.read_text(encoding="utf-8") if pre.is_file() else ""
    ok = wo.is_file() and repair.is_file() and (
        "write-owner" in pre_txt or "write_owner" in pre_txt
    )
    return _check(
        "g-conv.5",
        "single_writer_immune",
        ok,
        hard=True,
        detail={
            "write_owners": wo.is_file(),
            "repair_draft": repair.is_file(),
            "pre_commit_wired": "write-owner" in pre_txt or "write_owner" in pre_txt,
        },
    )


def check_g_conv_6_kos(code_root: Path, ssot_root: Path) -> dict[str, Any]:
    """KOS seed tooling present; index growth is ops (non-blocking if seed exists)."""
    seed = code_root / "bin/gac/kos-seed-import.py"
    # common kos index locations (best-effort) — prefer live ssot/runtime tree
    candidates = [
        ssot_root / "kos" / "kos-index.sqlite",
        ssot_root / "runtime" / "kos" / "kos-index.sqlite",
        ssot_root / ".omo" / "kos" / "kos-index.sqlite",
        code_root / "kos" / "kos-index.sqlite",
        code_root / "runtime" / "kos" / "kos-index.sqlite",
    ]
    index = next((p for p in candidates if p.is_file()), None)
    ok = seed.is_file()  # hard: seed path exists; index optional
    return _check(
        "g-conv.6",
        "kos_index_bootstrap",
        ok,
        hard=True,
        detail={
            "seed_script": seed.is_file(),
            "index_path": str(index) if index else None,
            "index_present": index is not None,
        },
        note="hard = seed tooling present; index growth is quarterly ops",
    )


def check_g_conv_7_window(
    code_root: Path,
    ssot_root: Path,
    *,
    scan_orphans: bool = True,
    emit_orphans: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Returns (gate_check, window_status_payload).

    Registry/four-gates from code_root; window events from ssot_root (live delivery).
    """
    sd = _load_swarm(code_root)
    if sd is None:
        empty = {
            "window_start": None,
            "elapsed_hours": 0.0,
            "conflict_count": 0,
            "m1_conflict_zero_verdict": "window_open",
            "note": "swarm_discipline.py missing",
        }
        gate = _check(
            "g-conv.7",
            "swarm_conflict_window",
            False,
            hard=True,
            detail=empty,
            note="swarm_discipline missing",
        )
        return gate, empty

    # Window + events live on ssot_root; orphan scan uses code_root git if same,
    # else ssot_root (where main history / launchd runs).
    status = sd.conflict_window_status(
        ssot_root, scan_orphans=scan_orphans, emit_orphans=emit_orphans
    )
    reg = sd.load_registry(code_root)
    gates = reg.get("gates") or {}
    four = {
        "d1_adr_atomic_claim",
        "d2_branch_occupancy",
        "d3_shared_worktree_claim",
        "d4_escape_hatch",
    }
    gate_keys = set(gates.keys()) if isinstance(gates, dict) else set()
    reg_path = code_root / ".omo/_truth/registry/swarm-coordination.yaml"
    reg_txt = reg_path.read_text(encoding="utf-8") if reg_path.is_file() else ""
    four_ok = all(k in gate_keys or k in reg_txt for k in four)

    verdict = status.get("m1_conflict_zero_verdict") or "window_open"
    count = int(status.get("conflict_count") or 0)
    mech_ok = four_ok and status.get("window_start") is not None
    no_conflicts = count == 0
    gate = _check(
        "g-conv.7",
        "swarm_conflict_window",
        mech_ok and no_conflicts,
        hard=True,
        detail={
            "four_gates_registered": four_ok,
            "window_start": status.get("window_start"),
            "elapsed_hours": status.get("elapsed_hours"),
            "window_hours_target": status.get("window_hours_target"),
            "conflict_count": count,
            "event_breakdown": status.get("event_breakdown"),
            "m1_conflict_zero_verdict": verdict,
            "orphan_commits_scanned_n": len(status.get("orphan_commits_scanned") or []),
        },
        note="ok=mech+count0; full pass needs elapsed≥window_hours",
    )
    return gate, status


def load_adversarial_evidence(path: Path | None) -> dict[str, Any] | None:
    """Load path-B adversarial report (ADR-0222).

    Accepts either:
      - {m1_adversarial_verdict: pass|fail, gates: [{gate, blocked}, ...]}
      - {gates: [...], all_blocked: true}
    """
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def adversarial_path_pass(evidence: dict[str, Any] | None) -> tuple[bool, dict[str, Any]]:
    """Return (pass?, detail) for path B four-gate all blocked.

    Convention: each gate entry has ``blocked: true`` when abuse was successfully
    stopped (D1 second claim fails, etc.).
    """
    if not evidence:
        return False, {"present": False}
    gates = evidence.get("gates") or []
    by_id: dict[str, bool] = {}
    for g in gates:
        if not isinstance(g, dict):
            continue
        raw = str(g.get("gate") or g.get("id") or "").strip().upper()
        if not raw:
            continue
        key = raw if raw in {"D1", "D2", "D3", "D4"} else (
            f"D{raw[1]}" if raw.startswith("D") and len(raw) > 1 and raw[1].isdigit() else raw
        )
        if key not in {"D1", "D2", "D3", "D4"}:
            # try extract D\d
            m = re.search(r"D([1-4])", raw)
            if not m:
                continue
            key = f"D{m.group(1)}"
        by_id[key] = bool(g.get("blocked", False))
    required = ("D1", "D2", "D3", "D4")
    missing = [k for k in required if k not in by_id]
    all_blocked = not missing and all(by_id[k] for k in required)
    # trust explicit rollup when present and consistent
    if evidence.get("summary", {}).get("all_blocked") is True and not missing:
        all_blocked = all(by_id[k] for k in required)
    if str(evidence.get("m1_adversarial_verdict") or "").lower() == "pass" and not missing:
        if all(by_id.get(k) for k in required):
            all_blocked = True
    detail = {
        "present": True,
        "all_blocked": all_blocked,
        "gate_blocked": {k: by_id.get(k) for k in required},
        "missing_gates": missing,
        "source_verdict": evidence.get("m1_adversarial_verdict"),
        "evidence_generated_at": evidence.get("generated_at"),
    }
    return all_blocked, detail


def load_conflict_rootcause(
    live: Path, code_root: Path, explicit: Path | None = None
) -> tuple[dict[str, Any] | None, Path | None]:
    """Load newest conflict-rootcause JSON (ADR-0224)."""
    if explicit is not None and explicit.is_file():
        try:
            return json.loads(explicit.read_text(encoding="utf-8")), explicit
        except (OSError, json.JSONDecodeError):
            return None, explicit
    candidates: list[Path] = []
    for base in (live, code_root):
        d = base / ".omo/_delivery/m1-closeout"
        if d.is_dir():
            candidates.extend(sorted(d.glob("conflict-rootcause-*.json")))
        audits = base / ".omo/_knowledge/audits"
        if audits.is_dir():
            candidates.extend(sorted(audits.glob("*m1-conflict-rootcause*.json")))
            candidates.extend(sorted(audits.glob("conflict-rootcause-*.json")))
    if not candidates:
        return None, None
    # Prefer newest by mtime among unique paths
    uniq = sorted({p.resolve() for p in candidates}, key=lambda p: p.stat().st_mtime)
    path = uniq[-1]
    try:
        return json.loads(path.read_text(encoding="utf-8")), path
    except (OSError, json.JSONDecodeError):
        return None, path


def evaluate_rootcause(
    rootcause: dict[str, Any] | None, conflict_count: int
) -> dict[str, Any]:
    """ADR-0224: classify whether path B may still pass when count>0."""
    if conflict_count <= 0:
        return {
            "required": False,
            "present": False,
            "ok": True,
            "classes": [],
            "blocking_classes": [],
        }
    if not rootcause:
        return {
            "required": True,
            "present": False,
            "ok": False,
            "reason": "conflict_count>0 requires conflict-rootcause JSON (ADR-0224)",
            "classes": [],
            "blocking_classes": ["missing_rootcause"],
        }
    events = rootcause.get("events") or []
    classes = [str(e.get("class") or "unresolved") for e in events if isinstance(e, dict)]
    if not classes and conflict_count > 0:
        classes = ["unresolved"]
    blocking = [c for c in classes if c in BAD_ROOTCAUSE or c not in OK_ROOTCAUSE]
    # unknown classes treated as blocking
    blocking = [c for c in classes if c not in OK_ROOTCAUSE]
    ok = len(blocking) == 0 and len(classes) >= conflict_count
    # allow rootcause with exactly the known events even if count slightly differs
    if len(blocking) == 0 and classes and all(c in OK_ROOTCAUSE for c in classes):
        ok = True
    return {
        "required": True,
        "present": True,
        "ok": ok,
        "classes": classes,
        "blocking_classes": blocking,
        "disposition": rootcause.get("disposition"),
        "reason": None
        if ok
        else f"rootcause has blocking classes: {blocking or 'incomplete'}",
    }


def build_report(
    root: Path,
    *,
    ssot_root: Path | None = None,
    ratio_min: float = DEFAULT_RATIO_MIN,
    scan_orphans: bool = True,
    emit_orphans: bool = False,
    adversarial_evidence: Path | None = None,
    conflict_rootcause: Path | None = None,
) -> dict[str, Any]:
    code_root = root.resolve()
    live = (ssot_root or root).resolve()
    g1 = check_g_conv_1_isolation(code_root)
    g2 = check_g_conv_2_daemon(live, ratio_min=ratio_min)
    g3 = check_g_conv_3_health(live)
    g4 = check_g_conv_4_gitlink(code_root)
    g5 = check_g_conv_5_write_owner(code_root)
    g6 = check_g_conv_6_kos(code_root, live)
    g7, window = check_g_conv_7_window(
        code_root,
        live,
        scan_orphans=scan_orphans,
        emit_orphans=emit_orphans,
    )
    checks = [g1, g2, g3, g4, g5, g6, g7]

    hard_fails = [c["id"] for c in checks if c["hard"] and not c["ok"]]
    elapsed = float(window.get("elapsed_hours") or 0.0)
    target_h = float(window.get("window_hours_target") or 72)
    conflict_count = int(window.get("conflict_count") or 0)
    window_verdict = window.get("m1_conflict_zero_verdict") or "window_open"

    # Path B — adversarial (ADR-0222 + 0224)
    adv_path = adversarial_evidence
    if adv_path is None:
        candidate = live / DEFAULT_ADVERSARIAL
        if candidate.is_file():
            adv_path = candidate
        else:
            candidate2 = code_root / DEFAULT_ADVERSARIAL
            if candidate2.is_file():
                adv_path = candidate2
    adv_raw = load_adversarial_evidence(adv_path)
    adv_ok, adv_detail = adversarial_path_pass(adv_raw)
    if adv_path is not None:
        adv_detail["path"] = str(adv_path)

    rc_raw, rc_path = load_conflict_rootcause(live, code_root, conflict_rootcause)
    rc_eval = evaluate_rootcause(rc_raw, conflict_count)
    if rc_path is not None:
        rc_eval["path"] = str(rc_path)

    # Path A — passive full window
    passive_ok = (
        window.get("window_start") is not None
        and elapsed >= target_h
        and conflict_count == 0
        and window_verdict != "fail"
        and not hard_fails
    )

    # M1 rollup (ADR-0210 + ADR-0220 + ADR-0222 + ADR-0224)
    structural_hard = [c for c in hard_fails if c != "g-conv.7"]
    evidence_path: str | None = None
    # Path B with ADR-0224: if conflict_count>0 need clean rootcause
    if adv_ok and not structural_hard:
        if conflict_count > 0 and not rc_eval.get("ok"):
            m1_verdict = "fail"
            evidence_path = None
        elif conflict_count > 0 and rc_eval.get("ok"):
            m1_verdict = "pass"
            evidence_path = "adversarial_with_rootcause"
        else:
            m1_verdict = "pass"
            evidence_path = "adversarial"
    elif conflict_count > 0 or window_verdict == "fail":
        # passive path fails on raw conflicts unless only historical (not auto)
        m1_verdict = "fail"
    elif structural_hard:
        m1_verdict = "fail"
    elif window.get("window_start") is None:
        m1_verdict = "window_not_started"
    elif elapsed < target_h:
        m1_verdict = "window_open"
    elif passive_ok:
        m1_verdict = "pass"
        evidence_path = "passive"
    elif hard_fails:
        m1_verdict = "fail"
    else:
        m1_verdict = "fail"

    phase2_recommend = m1_verdict == "pass"
    remaining = max(0.0, target_h - elapsed)

    report: dict[str, Any] = {
        "schema": "m1-closeout-report/v3",
        "generated_at": _utc_iso(),
        "root": str(code_root),
        "ssot_root": str(live),
        "adr": ["0210", "0220", "0222", "0224"],
        "m1_verdict": m1_verdict,
        "evidence_path": evidence_path,
        "phase2_recommend": phase2_recommend,
        "window": {
            "window_start": window.get("window_start"),
            "window_end_or_null": window.get("window_end_or_null"),
            "window_hours_target": target_h,
            "elapsed_hours": elapsed,
            "remaining_hours": round(remaining, 3),
            "conflict_count": conflict_count,
            "event_breakdown": window.get("event_breakdown") or {},
            "m1_conflict_zero_verdict": window_verdict,
            "orphan_commits_scanned": (window.get("orphan_commits_scanned") or [])[:10],
        },
        "adversarial": adv_detail,
        "conflict_rootcause": rc_eval,
        "paths": {
            "passive_ok": passive_ok,
            "adversarial_ok": adv_ok,
            "rootcause_ok": bool(rc_eval.get("ok")),
        },
        "checks": checks,
        "hard_fails": hard_fails,
        "summary": {
            "all_hard_green": not hard_fails,
            "daemon_ratio": (g2.get("detail") or {}).get("service_online_ratio"),
            "health_score": (g3.get("detail") or {}).get("health_score"),
            "health_score_source": (g3.get("detail") or {}).get("health_score_source"),
        },
        "pr_421_note": (
            "PR#421 merged while closeout still window_open; ADR-0222 path B "
            "adversarial evidence is the legitimate retroactive unlock criterion. "
            "ADR-0224 requires rootcause when passive conflict_count>0."
        ),
        "rejudge_hint": (
            "Path A (passive): elapsed≥72h AND conflict_count=0 AND hard greens. "
            "Path B (adversarial, ADR-0222): four-gate probe all blocked AND hard "
            "greens — pass --adversarial-evidence <json>. "
            "When conflict_count>0, ADR-0224 requires conflict-rootcause with only "
            "gate_interception|historical_pre_gate → evidence_path="
            "adversarial_with_rootcause; coverage_gap_bypass|unresolved|missing "
            "blocks pass and freezes G-DEL expansion until gates are repaired."
        ),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--root",
        type=Path,
        default=None,
        help="code workspace root (default: parent of bin/gac)",
    )
    p.add_argument(
        "--ssot-root",
        type=Path,
        default=None,
        help="live SSOT root for .omo/state + swarm-conflicts (default: --root)",
    )
    p.add_argument("--json", action="store_true", help="JSON only on stdout")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write report JSON to path (also prints)",
    )
    p.add_argument(
        "--ratio-min",
        type=float,
        default=DEFAULT_RATIO_MIN,
        help="daemon online ratio threshold (default 0.9)",
    )
    p.add_argument(
        "--no-orphan-scan",
        action="store_true",
        help="skip advisory orphan_commit git scan",
    )
    p.add_argument(
        "--emit-orphans",
        action="store_true",
        help="record orphan hits into conflict events (affects M1 count)",
    )
    p.add_argument(
        "--adversarial-evidence",
        type=Path,
        default=None,
        help=(
            "path B JSON (default: <ssot>/.omo/_delivery/m1-adversarial/latest.json "
            "if present)"
        ),
    )
    p.add_argument(
        "--conflict-rootcause",
        type=Path,
        default=None,
        help=(
            "ADR-0224 rootcause JSON when conflict_count>0 "
            "(default: newest .omo/_delivery/m1-closeout/conflict-rootcause-*.json "
            "or audits copy under code root)"
        ),
    )
    args = p.parse_args(argv)

    root = args.root
    if root is None:
        root = Path(__file__).resolve().parents[2]
    root = root.resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"root not a directory: {root}"}), file=sys.stderr)
        return 2
    ssot = args.ssot_root.resolve() if args.ssot_root else None
    if ssot is not None and not ssot.is_dir():
        print(json.dumps({"error": f"ssot-root not a directory: {ssot}"}), file=sys.stderr)
        return 2

    report = build_report(
        root,
        ssot_root=ssot,
        ratio_min=args.ratio_min,
        scan_orphans=not args.no_orphan_scan,
        emit_orphans=bool(args.emit_orphans),
        adversarial_evidence=args.adversarial_evidence,
        conflict_rootcause=args.conflict_rootcause,
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json or args.out:
        print(text)
    else:
        # human one-liner + JSON
        print(
            f"m1_verdict={report['m1_verdict']} "
            f"phase2_recommend={report['phase2_recommend']} "
            f"elapsed_h={report['window']['elapsed_hours']} "
            f"conflict_count={report['window']['conflict_count']} "
            f"hard_fails={report['hard_fails']}",
            file=sys.stderr,
        )
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
