#!/usr/bin/env python3
"""check-work-landed: detect run-closeouts that never reached main.

For every run yaml under `.omo/_delivery/agent-workflows/runs/` whose
`status: ok`, the run must have shipped to `origin/main` within an
SLA window. The check extracts PR numbers and commit hashes from the
run's `evidence` field (or `objective` line) and verifies that the
referenced SHA/PR actually exists in the main branch history.

SLA:
  - 3..7 days stranded: warn
  - >7 days stranded: blocking

History: this gate is the executable form of STRAT-P82 / STRAT-P85
G1.1 — the recurring "成果做完必须落 main" red line that the human
eye has missed twice already.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
RUNS_DIR = WORKSPACE / ".omo/_delivery/agent-workflows/runs"
WARN_AFTER = timedelta(days=3)
BLOCK_AFTER = timedelta(days=7)

PR_RE = re.compile(r"#(\d+)\b")
SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _read_run(path: Path) -> dict[str, Any] | None:
    try:
        return yaml_safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # K3: 不静默 (pipe-mask-failure-pattern 同族)
        print(f"[warn] _read_run {path.name}: {exc}", file=sys.stderr)
        return None


def yaml_safe_load(text: str) -> dict[str, Any] | None:
    try:
        import yaml
        return yaml.safe_load(text)
    except Exception as exc:  # K3: 不静默
        print(f"[warn] yaml_safe_load: {exc}", file=sys.stderr)
        return None


def _extract_landing_refs(run: dict[str, Any]) -> set[str]:
    """Pull all PR numbers and SHAs referenced anywhere in the run yaml
    that look like a landing reference (PR #, commit hash, 'merged')."""
    refs: set[str] = set()
    blob = " ".join(
        str(run.get(k, "")) for k in ("evidence", "objective", "summary", "result", "context")
    )
    for m in PR_RE.findall(blob):
        refs.add(f"pr:{m}")
    for m in SHA_RE.findall(blob):
        refs.add(f"sha:{m}")
    # Heuristic: any of these are present, the run "claims" landing.
    return refs


def _refs_landed(refs: set[str]) -> dict[str, bool]:
    """For each ref, ask git log origin/main whether it is present.
    PR#:  `git log origin/main --grep=#N`
    SHA:  `git log origin/main --grep=<short>`  (or a direct rev-parse)
    """
    landed: dict[str, bool] = {}
    if not refs:
        return landed
    for ref in refs:
        if ref.startswith("pr:"):
            n = ref.split(":", 1)[1]
            try:
                cp = subprocess.run(
                    ["git", "log", "origin/main", f"--grep=#{n}", "--oneline"],
                    cwd=str(WORKSPACE),
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                landed[ref] = cp.returncode == 0 and cp.stdout.strip() != ""
            except Exception as exc:  # K3: 不静默 (pipe-mask 同族)
                print(f"[warn] _refs_landed pr {ref}: {exc}", file=sys.stderr)
                landed[ref] = False
        elif ref.startswith("sha:"):
            sha = ref.split(":", 1)[1]
            short = sha[:7] if len(sha) >= 7 else sha
            try:
                cp = subprocess.run(
                    ["git", "log", "origin/main", f"--grep={short}", "--oneline"],
                    cwd=str(WORKSPACE),
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                landed[ref] = cp.returncode == 0 and cp.stdout.strip() != ""
            except Exception as exc:  # K3: 不静默
                print(f"[warn] _refs_landed sha {ref}: {exc}", file=sys.stderr)
                landed[ref] = False
    return landed


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--window-days",
        type=int,
        default=90,
        help="only consider run yamls newer than (now - window_days).",
    )
    parser.add_argument(
        "--unconditional",
        action="store_true",
        help="do not allow the 'no evidence reference' case to be ignored.",
    )
    args = parser.parse_args()

    if not RUNS_DIR.is_dir():
        print(json.dumps({"ok": True, "summary": {"closed": 0}, "findings": []}, ensure_ascii=False, indent=2))
        return 0

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=args.window_days)

    findings: list[dict[str, Any]] = []
    summary = {"closed": 0, "settled": 0, "warn": 0, "blocking": 0, "no_ref": 0}

    for path in sorted(RUNS_DIR.glob("*.yaml")):
        run = _read_run(path)
        if not run or run.get("status") != "ok":
            continue
        ts = _parse_ts(run.get("updated_at") or run.get("created_at") or "")
        if ts is None or ts < cutoff:
            continue
        summary["closed"] += 1
        refs = _extract_landing_refs(run)
        if not refs:
            summary["no_ref"] += 1
            if args.unconditional:
                age = now - ts
                kind = "blocking" if age >= BLOCK_AFTER else "warn" if age >= WARN_AFTER else "ok"
                if kind != "ok":
                    findings.append({
                        "id": run.get("run_id"),
                        "kind": f"no_evidence_ref:{kind}",
                        "age_days": age.total_seconds() / 86400,
                        "claimed_paths": [],
                        "missing_paths": [],
                    })
                    if kind == "blocking":
                        summary["blocking"] += 1
                    else:
                        summary["warn"] += 1
            continue
        landed = _refs_landed(refs)
        unlanded = [r for r, ok in landed.items() if not ok]
        if not unlanded:
            summary["settled"] += 1
            continue
        age = now - ts
        kind = "blocking" if age >= BLOCK_AFTER else "warn" if age >= WARN_AFTER else "ok"
        if kind == "ok":
            continue
        findings.append({
            "id": run.get("run_id") or path.stem,
            "kind": f"missing_landing:{kind}",
            "age_days": age.total_seconds() / 86400,
            "claimed_refs": sorted(refs),
            "unlanded_refs": sorted(unlanded),
        })
        if kind == "blocking":
            summary["blocking"] += 1
        else:
            summary["warn"] += 1

    ok = summary["blocking"] == 0
    report = {"ok": ok, "summary": summary, "findings": findings}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"check-work-landed: {'PASS' if ok else 'FAIL'}")
        print(
            f"  closed={summary['closed']} settled={summary['settled']} "
            f"no_ref={summary['no_ref']} warn={summary['warn']} "
            f"blocking={summary['blocking']}"
        )
        for f in findings:
            extra = (
                f["unlanded_refs"] if "unlanded_refs" in f else f.get("claimed_paths", [])
            )
            print(f"  - {f['id']} [{f['kind']}] age={f['age_days']:.1f}d refs={extra}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
