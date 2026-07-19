#!/usr/bin/env python3
"""Phase gate hard check (ADR-0223 + ADR-0225 caliber) — stdlib + optional PyYAML.

CI-friendly: does NOT import m1-closeout-report or swarm_discipline.
Reads:
  - .omo/_truth/registry/phase-scope.yaml   (paths + unlock keys + metrics_caliber)
  - .omo/_truth/registry/phase-verdict.yaml (committed unlock SSOT)
  - optional escape files under .omo/_delivery/phase-escape/
  - optional G-DEL metrics JSON (--metrics) for sim-vs-physical consistency

Usage:
  python3 bin/gac/phase-gate-check.py --base origin/main
  python3 bin/gac/phase-gate-check.py --files bin/delivery/x.py
  python3 bin/gac/phase-gate-check.py --metrics path/to/measure.json --check-caliber
  python3 bin/gac/phase-gate-check.py --json
  PHASE_ESCAPE_ID=... python3 bin/gac/phase-gate-check.py ...

Exit:
  0  allow
  1  blocked (phase not unlocked or caliber violation)
  2  config error
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# sim markers aligned with bin/delivery/caliber.py (stdlib-only copy for CI)
_SIM_MARKERS = (
    "in-process",
    "simulation",
    "not physical",
    "process-local",
    "logical node",
    "in_process_simulation",
)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        docs = [d for d in yaml.safe_load_all(text) if d]
        if not docs:
            return {}
        last = docs[-1]
        return last if isinstance(last, dict) else {}
    except Exception:
        # minimal fallback: not used for complex yaml
        return {}


def nested_get(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def path_matches(path: str, patterns: list[str]) -> bool:
    path = path.replace("\\", "/").lstrip("./")
    for pat in patterns:
        pat = pat.replace("\\", "/").lstrip("./")
        if fnmatch.fnmatch(path, pat):
            return True
        if pat.endswith("/**"):
            prefix = pat[:-3]
            if path == prefix.rstrip("/") or path.startswith(prefix):
                return True
        if path == pat or path.startswith(pat.rstrip("*").rstrip("/")):
            if fnmatch.fnmatch(path, pat) or path.startswith(pat.rstrip("*")):
                return True
    return False


def git_changed_files(root: Path, base: str) -> list[str]:
    # Prefer merge-base with base ref
    cmds = [
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        ["git", "diff", "--name-only", f"{base}..HEAD"],
        ["git", "diff", "--name-only", "--cached"],
        ["git", "diff", "--name-only", "HEAD~1"],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
        if r.returncode == 0 and r.stdout.strip():
            return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    return []


def list_escapes(escape_dir: Path) -> list[dict[str, Any]]:
    if not escape_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(escape_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            data["_file"] = str(p)
            out.append(data)
    return out


def find_escape(
    escapes: list[dict[str, Any]],
    *,
    phase_id: str,
    escape_id: str | None,
    pr: str | None,
) -> dict[str, Any] | None:
    for e in escapes:
        if not e.get("active", True):
            continue
        if e.get("phase") != phase_id:
            continue
        if escape_id and e.get("id") == escape_id:
            return e
        if pr and str(e.get("pr") or "") in {pr, f"#{pr}", f"PR{pr}", f"pr/{pr}"}:
            return e
        # allow PR number match from GITHUB_REF
        if pr and str(e.get("pr_number") or "") == str(pr):
            return e
    return None


def _metric_env_is_sim(metric: dict[str, Any]) -> bool:
    ec = str(metric.get("env_class") or "").lower().replace("-", "_")
    if "physical" in ec and "sim" not in ec:
        return False
    if "sim" in ec or "in_process" in ec or "inprocess" in ec:
        return True
    text = str(metric.get("env") or "").lower()
    return any(m in text for m in _SIM_MARKERS) or not text


def check_metrics_caliber(
    report: dict[str, Any],
    caliber: dict[str, Any] | None,
) -> dict[str, Any]:
    """ADR-0225: sim-labeled metrics must not claim physical gate pass.

    Pure function — inject labeled dicts in tests; no network.
    """
    if not caliber:
        return {
            "ok": True,
            "skipped": True,
            "reason": "no metrics_caliber in phase-scope",
            "violations": [],
        }
    physical_gates = caliber.get("physical_gates") or []
    violations: list[dict[str, Any]] = []

    for pg in physical_gates:
        if not isinstance(pg, dict):
            continue
        keys = list(pg.get("metric_keys") or [])
        only_fields = list(pg.get("physical_only_true_fields") or ["meets_physical_gate", "meets_gate"])
        for mk in keys:
            metric = report.get(mk)
            if not isinstance(metric, dict):
                # also allow nested under report["metrics"][mk]
                metrics_block = report.get("metrics")
                if isinstance(metrics_block, dict):
                    metric = metrics_block.get(mk)
            if not isinstance(metric, dict):
                continue
            if not _metric_env_is_sim(metric):
                # physical-labeled: ok if claims physical pass
                continue
            for field in only_fields:
                if metric.get(field) is True:
                    violations.append(
                        {
                            "rule": "no-sim-in-physical-fields",
                            "metric_key": mk,
                            "gate": pg.get("gate") or pg.get("id"),
                            "field": field,
                            "env": metric.get("env"),
                            "env_class": metric.get("env_class"),
                            "message": (
                                f"{mk}.{field}=true under simulation env; "
                                f"physical-only field (ADR-0225)"
                            ),
                        }
                    )

    # Rollup: all_physical_gates_pass / all_gates_pass true with sim env_class at top
    top_class = str(report.get("env_class") or "").lower()
    top_is_sim = (
        "sim" in top_class
        or "in_process" in top_class
        or "inprocess" in top_class
        or (not top_class and any(
            isinstance(report.get(k), dict) and _metric_env_is_sim(report[k])
            for k in ("g_del_1", "g_del_3")
        ))
    )
    if top_is_sim:
        for field in ("all_physical_gates_pass",):
            if report.get(field) is True:
                violations.append(
                    {
                        "rule": "no-sim-in-physical-fields",
                        "metric_key": field,
                        "field": field,
                        "message": f"report.{field}=true under simulation (ADR-0225)",
                    }
                )

    ok = len(violations) == 0
    return {
        "ok": ok,
        "skipped": False,
        "violations": violations,
        "scheme": caliber.get("scheme"),
        "adr": caliber.get("adr"),
    }


def check_phases(
    root: Path,
    changed: list[str],
    *,
    escape_id: str | None = None,
    pr: str | None = None,
) -> dict[str, Any]:
    scope_path = root / ".omo/_truth/registry/phase-scope.yaml"
    verdict_path = root / ".omo/_truth/registry/phase-verdict.yaml"
    scope = load_yaml(scope_path)
    verdict = load_yaml(verdict_path)
    if not scope.get("phases"):
        return {
            "ok": False,
            "error": f"missing or empty phase-scope: {scope_path}",
            "exit": 2,
        }
    if not verdict.get("phases"):
        return {
            "ok": False,
            "error": f"missing or empty phase-verdict: {verdict_path}",
            "exit": 2,
        }

    escape_rel = scope.get("escape_dir") or ".omo/_delivery/phase-escape"
    # committed escapes (CI-visible) + runtime delivery (local)
    escape_dirs = [
        root / escape_rel,
        root / ".omo/_truth/registry/phase-escapes",
    ]
    for extra in scope.get("escape_dirs") or []:
        escape_dirs.append(root / str(extra))
    escapes: list[dict[str, Any]] = []
    seen_files: set[str] = set()
    for ed in escape_dirs:
        for e in list_escapes(ed):
            f = e.get("_file") or ""
            if f in seen_files:
                continue
            seen_files.add(f)
            escapes.append(e)

    blocks: list[dict[str, Any]] = []
    allowed: list[dict[str, Any]] = []

    phases = scope.get("phases") or {}
    # phases may be dict keyed by id
    if isinstance(phases, dict):
        phase_items = list(phases.values()) if phases and isinstance(next(iter(phases.values()), None), dict) else []
        if not phase_items and phases:
            # keyed map of phase objects
            phase_items = [v for v in phases.values() if isinstance(v, dict)]
    else:
        phase_items = [p for p in phases if isinstance(p, dict)]

    for phase in phase_items:
        pid = str(phase.get("id") or "")
        patterns = list(phase.get("paths") or [])
        hits = [f for f in changed if path_matches(f, patterns)]
        if not hits:
            continue
        unlock = phase.get("unlock") or {}
        key = str(unlock.get("verdict_key") or f"phases.{pid}.unlocked")
        unlocked = nested_get(verdict, key)
        expect = unlock.get("equals", True)
        is_unlocked = unlocked == expect
        if is_unlocked:
            allowed.append({"phase": pid, "files": hits, "reason": "unlocked"})
            continue
        esc = find_escape(escapes, phase_id=pid, escape_id=escape_id, pr=pr)
        if esc:
            allowed.append(
                {
                    "phase": pid,
                    "files": hits,
                    "reason": "escape",
                    "escape_id": esc.get("id"),
                    "escape_file": esc.get("_file"),
                }
            )
            continue
        blocks.append(
            {
                "phase": pid,
                "name": phase.get("name"),
                "files": hits,
                "verdict_key": key,
                "unlocked": unlocked,
                "required": expect,
                "hint": (
                    f"Phase {pid} not unlocked. Update phase-verdict.yaml only with "
                    f"evidence, or register escape under {escape_rel}/ with PR rationale."
                ),
            }
        )

    ok = len(blocks) == 0
    return {
        "ok": ok,
        "exit": 0 if ok else 1,
        "changed": changed,
        "blocks": blocks,
        "allowed": allowed,
        "escape_id": escape_id,
        "pr": pr,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--base", default="origin/main", help="git base for diff")
    ap.add_argument("--files", nargs="*", default=None, help="explicit file list")
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--metrics",
        type=Path,
        default=None,
        help="G-DEL measure JSON to validate against metrics_caliber (ADR-0225)",
    )
    ap.add_argument(
        "--check-caliber",
        action="store_true",
        help="require metrics caliber check (loads --metrics or runs measure_all)",
    )
    ap.add_argument(
        "--escape-id",
        default=os.environ.get("PHASE_ESCAPE_ID") or os.environ.get("SWARM_ESCAPE_ID"),
    )
    ap.add_argument(
        "--pr",
        default=os.environ.get("PHASE_ESCAPE_PR")
        or os.environ.get("GITHUB_PR_NUMBER")
        or "",
    )
    args = ap.parse_args(argv)
    root = (args.root or Path(__file__).resolve().parents[2]).resolve()

    if args.files is not None and len(args.files) > 0:
        changed = [f.replace("\\", "/") for f in args.files]
    else:
        # On PRs GitHub sets base; fetch may be needed
        changed = git_changed_files(root, args.base)
        if not changed and os.environ.get("GITHUB_EVENT_PATH"):
            # fallback: empty diff = allow
            changed = []

    # GITHUB_REF refs/pull/N/merge → N
    pr = args.pr or ""
    if not pr:
        ref = os.environ.get("GITHUB_REF") or ""
        m = re.search(r"refs/pull/(\d+)/", ref)
        if m:
            pr = m.group(1)

    result = check_phases(
        root,
        changed,
        escape_id=args.escape_id or None,
        pr=pr or None,
    )

    # ADR-0225 caliber
    scope = load_yaml(root / ".omo/_truth/registry/phase-scope.yaml")
    caliber = scope.get("metrics_caliber") if isinstance(scope, dict) else None
    caliber_result: dict[str, Any] | None = None
    metrics_path = args.metrics
    if args.check_caliber or metrics_path is not None:
        report: dict[str, Any] | None = None
        if metrics_path is not None and metrics_path.is_file():
            try:
                report = json.loads(metrics_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                result["ok"] = False
                result["exit"] = 2
                result["error"] = f"metrics unreadable: {exc}"
                report = None
        elif args.check_caliber:
            # run measure_all as subprocess for real path
            measure = root / "bin/delivery/measure_all.py"
            if measure.is_file():
                r = subprocess.run(
                    [sys.executable, str(measure)],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                try:
                    report = json.loads(r.stdout)
                except json.JSONDecodeError:
                    result["ok"] = False
                    result["exit"] = 2
                    result["error"] = f"measure_all non-JSON: {r.stderr[:200]}"
            else:
                result["ok"] = False
                result["exit"] = 2
                result["error"] = "measure_all.py missing for --check-caliber"
        if report is not None:
            caliber_result = check_metrics_caliber(report, caliber if isinstance(caliber, dict) else None)
            result["caliber"] = caliber_result
            if not caliber_result.get("ok"):
                result["ok"] = False
                result["exit"] = 1
                result.setdefault("blocks", []).append(
                    {
                        "phase": "metrics_caliber",
                        "name": "ADR-0225 sim≠physical",
                        "files": [str(metrics_path)] if metrics_path else ["measure_all"],
                        "hint": "Simulation metrics cannot set physical gate fields true",
                        "violations": caliber_result.get("violations"),
                    }
                )

    if args.json or True:
        # always print JSON for CI logs
        print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result.get("ok"):
        if result.get("error"):
            print(f"[phase-gate] ❌ {result['error']}", file=sys.stderr)
        for b in result.get("blocks") or []:
            print(
                f"[phase-gate] ❌ phase={b['phase']} blocked files={b.get('files')}",
                file=sys.stderr,
            )
            print(f"[phase-gate]    {b.get('hint')}", file=sys.stderr)
        return int(result.get("exit") or 1)
    print("[phase-gate] ✅ allow", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
