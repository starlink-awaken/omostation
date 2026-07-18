#!/usr/bin/env python3
"""Phase gate hard check (ADR-0223) — stdlib + optional PyYAML.

CI-friendly: does NOT import m1-closeout-report or swarm_discipline.
Reads:
  - .omo/_truth/registry/phase-scope.yaml   (paths + unlock keys)
  - .omo/_truth/registry/phase-verdict.yaml (committed unlock SSOT)
  - optional escape files under .omo/_delivery/phase-escape/

Usage:
  python3 bin/gac/phase-gate-check.py --base origin/main
  python3 bin/gac/phase-gate-check.py --files bin/delivery/x.py
  python3 bin/gac/phase-gate-check.py --json
  PHASE_ESCAPE_ID=... python3 bin/gac/phase-gate-check.py ...

Exit:
  0  allow
  1  blocked (phase not unlocked)
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
    if args.json or True:
        # always print JSON for CI logs
        print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result.get("ok"):
        if result.get("error"):
            print(f"[phase-gate] ❌ {result['error']}", file=sys.stderr)
        for b in result.get("blocks") or []:
            print(
                f"[phase-gate] ❌ phase={b['phase']} blocked files={b['files']}",
                file=sys.stderr,
            )
            print(f"[phase-gate]    {b.get('hint')}", file=sys.stderr)
        return int(result.get("exit") or 1)
    print("[phase-gate] ✅ allow", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
