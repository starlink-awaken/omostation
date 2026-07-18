#!/usr/bin/env python3
"""M1 closeout rejudge — ADR-0210 + ADR-0220 honest T+72 gate.

Aggregates G-CONV.1–7 evidence into a single JSON verdict. Never claims
``m1_pass`` / ``phase2_recommend=true`` while the 72h conflict window is open
or while hard greens fail (skeptic rule: evidence before assertion).

Usage:
  python3 bin/gac/m1-closeout-report.py
  python3 bin/gac/m1-closeout-report.py --ssot-root /path/to/live/workspace
  python3 bin/gac/m1-closeout-report.py --root /path/to/code --ssot-root /path/to/live
  python3 bin/gac/m1-closeout-report.py --json --out .omo/_delivery/m1-closeout/latest.json
  python3 bin/gac/m1-closeout-report.py --no-orphan-scan

``--root`` is the code tree (hooks, foundry, registry). ``--ssot-root`` is the live
runtime tree (``.omo/state``, swarm-conflicts window). Defaults: both = script workspace.
When the human Workspace branch lags main, use main-aligned code + live ``--ssot-root``.

Exit codes:
  0  report emitted (window_open / pass / fail all exit 0 — honesty is success)
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


def build_report(
    root: Path,
    *,
    ssot_root: Path | None = None,
    ratio_min: float = DEFAULT_RATIO_MIN,
    scan_orphans: bool = True,
    emit_orphans: bool = False,
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

    # Honest M1 rollup (ADR-0210 + ADR-0220)
    if window.get("window_start") is None:
        m1_verdict = "window_not_started"
    elif elapsed < target_h:
        m1_verdict = "window_open"
    elif hard_fails or conflict_count > 0 or window_verdict == "fail":
        m1_verdict = "fail"
    else:
        m1_verdict = "pass"

    phase2_recommend = m1_verdict == "pass"
    remaining = max(0.0, target_h - elapsed)

    report: dict[str, Any] = {
        "schema": "m1-closeout-report/v1",
        "generated_at": _utc_iso(),
        "root": str(code_root),
        "ssot_root": str(live),
        "adr": ["0210", "0220"],
        "m1_verdict": m1_verdict,
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
        "checks": checks,
        "hard_fails": hard_fails,
        "summary": {
            "all_hard_green": not hard_fails,
            "daemon_ratio": (g2.get("detail") or {}).get("service_online_ratio"),
            "health_score": (g3.get("detail") or {}).get("health_score"),
            "health_score_source": (g3.get("detail") or {}).get("health_score_source"),
        },
        "rejudge_hint": (
            "Re-run after window_end_target with same command; "
            "phase2_recommend flips true only when m1_verdict=pass "
            "(elapsed≥72h AND conflict_count=0 AND all hard greens). "
            "If Workspace branch lags main, pass --ssot-root <live> and keep "
            "code --root on a main-aligned tree."
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
