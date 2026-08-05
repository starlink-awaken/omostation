#!/usr/bin/env python3
"""A4 (ADR-0367) + ADR-0373: scan Python projects with pyright, collect suppression metrics, archive report.

Runs `pyright --outputjson` inside each project, aggregates diagnostics, and
writes a machine-readable report to `.omo/_knowledge/sweeps/<date>.json`.
After every successful scan, regenerates `.omo/_knowledge/sweeps/INDEX.md`
via `bin/sweep/sweep_index.py --write` (escapable with `--no-index`).

Report fields (per ADR-0367 + ADR-0373):
  errors / line_suppressions / file_suppressions / suppression_ratio
  diff_projects: [list, populated when --diff-mode]
  strict_violations: { [project_name]: count } (only with --strict)

Suppression counting matches bin/sweep/pyright.py semantics:
  - file_suppression: `# pyright: <rule>=false` header covers the rule
  - line_suppression: `# type: ignore[<rule>]` on the diagnostic line

New in ADR-0373:
  --diff-mode: project list computed from `git diff --name-only origin/main..HEAD`
               intersected with `projects/*` having pyproject.toml.
  --strict:    exit 1 if any project has file_suppressions > 0 (per-package
               hardening; supersedes the workspace-aggregate ratio).
  --no-index:  skip the post-scan sweep_index.py regeneration (rare; CI uses
               the indexed gate (CR-SWEEP-INDEX-AUTO) which runs separately).

Usage:
  python3 bin/sweep/scan.py                              # all projects + INDEX
  python3 bin/sweep/scan.py --projects c2g runtime       # subset
  python3 bin/sweep/scan.py --diff-mode                  # A4: only changed PR packages
  python3 bin/sweep/scan.py --diff-mode --strict         # A4 + per-package gate
  python3 bin/sweep/scan.py --no-index                   # skip INDEX regen
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULE = "reportGeneralTypeIssues"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--projects",
        nargs="*",
        help="Project dirs under projects/ (default: all with pyproject.toml)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / ".omo" / "_knowledge" / "sweeps",
        help="Report output dir (default: .omo/_knowledge/sweeps)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Report date (default: today, YYYY-MM-DD)",
    )
    parser.add_argument(
        "--diff-mode",
        action="store_true",
        help="A4: only scan projects touched by `git diff origin/main..HEAD`",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="A4 strict: exit 1 if any per-package file_suppressions > 0",
    )
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="Skip regenerating .omo/_knowledge/sweeps/INDEX.md after scan",
    )
    parser.add_argument(
        "--origin",
        default="origin/main",
        help="Diff base when --diff-mode (default: origin/main)",
    )
    return parser.parse_args()


def discover_projects() -> list[Path]:
    projects_dir = ROOT / "projects"
    return sorted(p for p in projects_dir.iterdir() if (p / "pyproject.toml").is_file())


def diff_projects(origin: str) -> list[Path]:
    """A4: project list derived from `git diff --name-only origin..HEAD`."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{origin}...HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    names: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split("/", 2)
        if len(parts) < 2 or parts[0] != "projects":
            continue
        names.add(parts[1])
    projects_dir = ROOT / "projects"
    return sorted(p for p in (projects_dir / n for n in names) if (p / "pyproject.toml").is_file())


def run_pyright(project: Path) -> dict:
    """Run pyright --outputjson inside the project; return parsed payload."""
    result = subprocess.run(
        ["uv", "run", "pyright", "--outputjson"],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if result.returncode not in (0, 1):
        return {"ok": False, "error": f"pyright exit={result.returncode}: {result.stderr[:300]}"}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": f"bad pyright JSON: {result.stdout[:300]}"}
    return {"ok": True, "payload": payload}


def file_header_rules(path: Path) -> set[str]:
    """Rules disabled by `# pyright: <rule>=false` headers in the file."""
    rules: set[str] = set()
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("# pyright:"):
                for part in line.split("# pyright:")[1].split(","):
                    rule = part.split("=")[0].strip()
                    if rule:
                        rules.add(rule)
    except OSError:
        pass
    return rules


def measure(payload: dict) -> dict:
    """Compute per-project suppression metrics from a pyright payload."""
    errors = [d for d in payload.get("generalDiagnostics", []) if d.get("severity") == "error"]
    line_suppressions = 0
    file_suppressed_errors = 0
    suppressed_files: set[str] = set()

    by_file: dict[str, list[dict]] = {}
    for item in errors:
        by_file.setdefault(item["file"], []).append(item)

    for file_path, items in by_file.items():
        path = Path(file_path)
        header_rules = file_header_rules(path)
        has_header = False
        for item in items:
            rule = item.get("rule") or DEFAULT_RULE
            if rule in header_rules:
                has_header = True
                file_suppressed_errors += 1
                continue
            try:
                line_idx = item["range"]["start"]["line"]
                line = path.read_text(encoding="utf-8").splitlines()[line_idx]
            except (OSError, IndexError):
                line = ""
            if f"type: ignore[{rule}]" in line or "type: ignore" in line and rule == DEFAULT_RULE:
                line_suppressions += 1
        if has_header:
            suppressed_files.add(file_path)

    total = len(errors)
    suppressed = line_suppressions + file_suppressed_errors
    return {
        "errors": total,
        "line_suppressions": line_suppressions,
        "file_suppressions": len(suppressed_files),
        "suppression_ratio": (suppressed / total) if total else 0.0,
    }


def regenerate_index(out_dir: Path) -> tuple[int, str]:
    """Invoke `sweep_index.py --write` and return (returncode, stdout/stderr)."""
    helper = Path(__file__).resolve().parent / "sweep_index.py"
    if not helper.is_file():
        return 1, f"sweep_index.py not found next to scan.py ({helper})"
    proc = subprocess.run(
        [sys.executable, str(helper), "--write", "--out-dir", str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    combined = (proc.stdout + proc.stderr).strip()
    return proc.returncode, combined


def main() -> int:
    args = parse_args()
    if args.projects:
        projects = [ROOT / "projects" / p for p in args.projects]
    elif args.diff_mode:
        projects = diff_projects(args.origin)
    else:
        projects = discover_projects()
    date = args.date or _dt.datetime.now(tz=_dt.timezone.utc).date().isoformat()

    results = {}
    aggregate: Counter[str] = Counter()
    strict_violations: dict[str, int] = {}
    for project in projects:
        if not project.is_dir():
            print(f"⚠️  project 不存在, 跳过: {project.name}")
            continue
        run = run_pyright(project)
        if not run["ok"]:
            results[project.name] = {"ok": False, "error": run["error"]}
            if args.strict:
                strict_violations[project.name] = -1
            continue
        metrics = measure(run["payload"])
        results[project.name] = {"ok": True, **metrics}
        for key in ("errors", "line_suppressions", "file_suppressions"):
            aggregate[key] += metrics[key]
        if args.strict and metrics["file_suppressions"] > 0:
            strict_violations[project.name] = metrics["file_suppressions"]

    total_errors = aggregate["errors"]
    suppressed = aggregate["line_suppressions"] + aggregate["file_suppressions"]
    report = {
        "date": date,
        "tool": "pyright --outputjson",
        "total_errors": total_errors,
        "line_suppressions": aggregate["line_suppressions"],
        "file_suppressions": aggregate["file_suppressions"],
        "suppression_ratio": (suppressed / total_errors) if total_errors else 0.0,
        "diff_mode": args.diff_mode,
        "diff_origin": args.origin if args.diff_mode else None,
        "diff_projects": sorted(p.name for p in projects) if args.diff_mode else None,
        "strict": args.strict,
        "strict_violations": strict_violations if args.strict else {},
        "projects": results,
        "argv": sys.argv[1:],
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{date}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"errors={total_errors} line_suppressions={aggregate['line_suppressions']} "
        f"file_suppressions={aggregate['file_suppressions']} "
        f"suppression_ratio={report['suppression_ratio']:.3f} -> {out}"
    )

    if args.strict and strict_violations:
        affected = ", ".join(f"{n}={c}" for n, c in strict_violations.items())
        print(
            f"❌ --strict: file_suppressions > 0 in: {affected}",
            file=sys.stderr,
        )
        return 1

    if not args.no_index:
        rc, msg = regenerate_index(args.out_dir)
        if rc != 0:
            print(f"⚠️  INDEX.md regeneration failed (rc={rc}): {msg}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
