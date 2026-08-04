#!/usr/bin/env python3
"""A4 (ADR-0367): scan Python projects with pyright, collect suppression metrics, archive report.

Runs `pyright --outputjson` inside each project, aggregates diagnostics, and
writes a machine-readable report to `.omo/_knowledge/sweeps/<date>.json`.

Report fields (per ADR-0367 A4):
  errors / line_suppressions / file_suppressions / suppression_ratio

Suppression counting matches bin/sweep/pyright.py semantics:
  - file_suppression: `# pyright: <rule>=false` header covers the rule
  - line_suppression: `# type: ignore[<rule>]` on the diagnostic line
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
    parser.add_argument("--date", default=None, help="Report date (default: today, YYYY-MM-DD)")
    return parser.parse_args()


def discover_projects() -> list[Path]:
    projects_dir = ROOT / "projects"
    return sorted(p for p in projects_dir.iterdir() if (p / "pyproject.toml").is_file())


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
    if result.returncode not in (0, 1):  # pyright exits 1 when diagnostics found
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


def main() -> int:
    args = parse_args()
    projects = [ROOT / "projects" / p for p in args.projects] if args.projects else discover_projects()
    date = args.date or _dt.datetime.now(tz=_dt.timezone.utc).date().isoformat()

    results = {}
    aggregate: Counter[str] = Counter()
    for project in projects:
        if not project.is_dir():
            print(f"⚠️  project 不存在, 跳过: {project.name}")
            continue
        run = run_pyright(project)
        if not run["ok"]:
            results[project.name] = {"ok": False, "error": run["error"]}
            continue
        metrics = measure(run["payload"])
        results[project.name] = {"ok": True, **metrics}
        for key in ("errors", "line_suppressions", "file_suppressions"):
            aggregate[key] += metrics[key]

    total_errors = aggregate["errors"]
    suppressed = aggregate["line_suppressions"] + aggregate["file_suppressions"]
    report = {
        "date": date,
        "tool": "pyright --outputjson",
        "total_errors": total_errors,
        "line_suppressions": aggregate["line_suppressions"],
        "file_suppressions": aggregate["file_suppressions"],
        "suppression_ratio": (suppressed / total_errors) if total_errors else 0.0,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
