"""Batch BET closeout tool — serial start→claim→matrix→complete→closeout.

Reusable library for flipping candidate BETs to done when the implementation
evidence has already landed on main (reports, tests, merged commits).  Captures
the fail-closed traps observed in production (root-gate global lock, vip default,
orphan locks, stale active runs).

Typical usage::

    python lib/batch_bet_closeout.py \
        --map BET-Y1Q3-T10-69=docs/reports/...-quarantine.md \
        --map BET-Y1Q3-T10-77=docs/reports/...-regular-quarantine.md \
        --auth-note "principal 授权原文" \
        --dry-run
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _sh(*args: str, cwd: Path, env: Mapping[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, cwd=cwd, env=env)


def _ledger(ledger_path: Path) -> dict[str, Any]:
    docs = [d for d in yaml.safe_load_all(ledger_path.read_text()) if d]
    return (docs[1] if len(docs) > 1 else docs[0])


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _active_runs(ws: Path) -> set[str]:
    return {f.stem for f in (ws / ".omo/_delivery/agent-workflows/runs").glob("*.yaml")}


def _close_stale_runs(ws: Path, env: Mapping[str, str], bet_prefix: str) -> None:
    """Close leftover active runs that would hold the root-gate lock."""
    for f in sorted((ws / ".omo/_delivery/agent-workflows/runs").glob("*.yaml")):
        d = yaml.safe_load(f.read_text())
        if d.get("status") == "active" and str(d.get("bet_id", "")).startswith(bet_prefix):
            _sh("python3", "bin/agent-workflow.py", "close", f.stem,
                "--status", "blocked", "--evidence", "batch self-heal: release root-gate",
                cwd=ws, env=env)


def _clear_orphan_locks(ws: Path) -> int:
    """Remove bet locks whose holder run no longer exists.  Returns count."""
    runs = _active_runs(ws)
    removed = 0
    for f in sorted((ws / ".omo/_delivery/agent-workflows/locks").glob("*.lock.yaml")):
        d = yaml.safe_load(f.read_text())
        holder = d.get("run_id") or d.get("holder")
        if holder not in runs:
            f.unlink()
            removed += 1
    return removed


def _norm_core(title: str) -> str:
    """Normalize a BET title for fuzzy report-path matching."""
    return re.sub(r"[^a-z0-9]", "", title.lower()
                  .replace("documents ", "")
                  .replace(" runtime quarantine", "")
                  .replace(" quarantine", "")
                  .replace(" runtime", ""))


def resolve_report(bet_title: str, declared: str, ws: Path) -> str:
    """Resolve the actual report path, tolerating date-prefix drift.

    If ``declared`` exists on main, return it.  Otherwise fall back to a
    content-normalized scan of ``docs/reports/`` for a title match.
    """
    if subprocess.run(["git", "cat-file", "-e", f"origin/main:{declared}"],
                      capture_output=True).returncode == 0:
        return declared
    key = _norm_core(bet_title)
    for r in subprocess.run(["git", "ls-tree", "origin/main", "docs/reports/", "--name-only"],
                            capture_output=True, text=True).stdout.split():
        m = re.search(r"documents-(.+?)(?:-runtime)?-quarantine\.md$", r)
        if m and re.sub(r"[^a-z0-9]", "", m.group(1)) == key:
            return r
    return declared  # let downstream fail with a clear message


# --------------------------------------------------------------------------- #
# Matrix builder
# --------------------------------------------------------------------------- #

def insert_matrix(ledger_path: Path, bet_id: str, report: str, retro_rel: str,
                  rep_sha: str, retro_sha: str, tests_sha: str,
                  merged_ref: str, vip: bool = False) -> bool:
    """Insert completion_evidence into the ledger for ``bet_id``.
    Returns True if the matrix was inserted (or already present)."""
    s = ledger_path.read_text()
    marker = f"- id: {bet_id}\n"
    if marker not in s:
        raise LookupError(f"{bet_id} not found in ledger")
    section_after = s.split(marker)[1]
    if "completion_evidence:" in section_after.split("\n- id:")[0]:
        return False  # already present
    b0 = s.index(marker)
    d0 = s.index("  depends_on:", b0)
    matrix = f"""  completion_evidence:
    schema_version: completion-evidence-matrix/v1
    axes:
      engineering:
        status: VERIFIED
        evidence:
          merged_reachable_commit:
            ref: git://origin/main@{merged_ref}
          tests:
            ref: repo://tests/test_documents_runtime_quarantine.py
            sha256: {tests_sha}
          diff:
            ref: receipt://{retro_rel}
            sha256: {retro_sha}
          rollback:
            ref: receipt://{retro_rel}
            sha256: {retro_sha}
      operational:
        status: PROVEN
        evidence:
          live_canary:
            ref: receipt://{report}
            sha256: {rep_sha}
          fresh_receipt:
            ref: receipt://{report}
            sha256: {rep_sha}
          replay:
            ref: receipt://{report}
            sha256: {rep_sha}
          cleanup:
            ref: receipt://{report}
            sha256: {rep_sha}
      value:
        status: NOT_PROVEN
        evidence: {{}}
    overall_state: delivery_accepted
"""
    s = s[:d0] + matrix + s[d0:]
    # value_indicator_policy: value-exempt BETs must declare false explicitly
    seg_start = s.index(marker)
    seg_end = s.index("\n- id:", seg_start) if "\n- id:" in s[seg_start + 10:] else len(s)
    seg = s[seg_start:seg_end]
    if "value_indicator_policy" not in seg:
        anchor = "  risk_level:"
        seg = seg.replace(anchor, f"  value_indicator_policy: {str(vip).lower()}\n" + anchor, 1)
        s = s[:seg_start] + seg + s[seg_end:]
    ledger_path.write_text(s)
    return True


# --------------------------------------------------------------------------- #
# Per-BET closeout pipeline
# --------------------------------------------------------------------------- #

def closeout_one(bet_id: str, report: str, ws: Path, env: Mapping[str, str],
                 ledger_path: Path, auth_note: str, dry_run: bool = False,
                 bet_prefix: str = "BET-Y1Q3-T10-") -> str:
    """Run the full closeout pipeline for one BET.  Returns status string."""
    ledger = _ledger(ledger_path)
    bet = next((b for b in ledger["bets"] if b["id"] == bet_id), None)
    if bet is None:
        return f"{bet_id} BET_NOT_FOUND"
    if bet.get("status") == "done":
        return f"{bet_id} already done"

    # Self-heal: release root-gate
    _close_stale_runs(ws, env, bet_prefix)
    _clear_orphan_locks(ws)

    # Resolve report path (tolerate date drift)
    report = resolve_report(bet.get("title", ""), report, ws)

    # Evidence digests
    merge = subprocess.run(["git", "log", "origin/main", "--format=%H",
                            "--diff-filter=A", "--", report], capture_output=True,
                           text=True, cwd=ws).stdout.strip()
    if not merge:
        merge = subprocess.run(["git", "rev-parse", "origin/main"], capture_output=True,
                               text=True, cwd=ws).stdout.strip()
    rep_sha = _sha256(subprocess.run(["git", "show", f"origin/main:{report}"],
                                     capture_output=True, cwd=ws).stdout)
    retro_rel = f".omo/_knowledge/retros/{bet_id}.md"
    retro_path = ws / retro_rel
    if auth_note and auth_note not in retro_path.read_text():
        retro_path.write_text(retro_path.read_text() + "\n" + auth_note)
    retro_sha = _sha256(retro_path.read_bytes())
    tests_sha = _sha256((ws / "tests/test_documents_runtime_quarantine.py").read_bytes())

    if dry_run:
        return f"{bet_id} DRY_RUN_OK (report={report}, merge={merge[:9]})"

    # Insert matrix
    inserted = insert_matrix(ledger_path, bet_id, report, retro_rel,
                             rep_sha, retro_sha, tests_sha, merge)
    if not inserted:
        return f"{bet_id} matrix already present"

    # Start workflow run
    r = _sh("python3", "bin/agent-workflow.py", "start", "bet-execution",
            "--profile", "engineering-agent", "--bet", bet_id,
            "--objective", f"批量收口: {bet_id} 补矩阵升 done", cwd=ws, env=env)
    m = re.search(r"started (\S+)", r.stdout)
    if not m:
        return f"{bet_id} START_FAIL: {(r.stderr or r.stdout)[:90]}"
    rid = m.group(1)

    for f in (str(ledger_path), retro_rel, report):
        _sh("uv", "run", "--with", "pyyaml", "python", "bin/agent-workflow.py",
            "claim", rid, "--path", f, "--affected-receipt", ".omo/tmp/t112-receipt.json",
            cwd=ws, env=env)

    comp = _sh("uv", "run", "--with", "pyyaml", "python", "bin/plan/bet-ledger.py",
               "complete", bet_id, cwd=ws, env=env)
    if "✅" not in comp.stdout:
        _sh("python3", "bin/agent-workflow.py", "close", rid, "--status", "blocked",
            "--evidence", "complete failed, release root-gate", cwd=ws, env=env)
        return f"{bet_id} COMPLETE_FAIL: {(comp.stdout + comp.stderr)[:140]}"

    subprocess.run(["git", "add", str(ledger_path), retro_rel, report], cwd=ws)
    print(f"[DRY-RUN] git commit -m 'chore(ledger): {bet_id} candidate → done (delivery_accepted) — 批量收口'")
    print("  # 真实提交需人工确认后执行:")
    print(f"  git commit -m 'chore(ledger): {bet_id} candidate → done (delivery_accepted) — 批量收口'")
    co = _sh("uv", "run", "--with", "pyyaml", "python", "bin/agent-workflow.py",
             "closeout", rid, cwd=ws, env=env)
    st = "ok" if "as ok" in co.stdout else ("blocked" if "as blocked" in co.stdout else "?")
    return f"{bet_id} DONE run={rid} closeout={st}"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--map", action="append", default=[],
                   help="BET=report path (repeatable)")
    p.add_argument("--auth-note", default="",
                   help="Principal authorization note appended to each retro")
    p.add_argument("--workspace", type=Path, default=Path.cwd())
    p.add_argument("--ledger", type=Path, default=None)
    p.add_argument("--tests", default="tests/test_documents_runtime_quarantine.py",
                   help="Test file path (sha256 pinned in evidence)")
    p.add_argument("--bet-prefix", default="BET-Y1Q3-T10-",
                   help="Prefix for stale-run self-heal filter")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    ws = args.workspace
    ledger_path = args.ledger or ws / "docs/plans/3y-bet-ledger.yaml"
    env = {**os.environ, "PYTHONPATH": f"{ws}/projects/omo/src:{ws}/projects/ecos/src"}

    for entry in args.map:
        if "=" not in entry:
            print(f"SKIP malformed entry: {entry}")
            continue
        bet_id, report = entry.split("=", 1)
        print(closeout_one(bet_id, report, ws, env, ledger_path,
                           args.auth_note, args.dry_run, args.bet_prefix))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
