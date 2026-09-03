#!/usr/bin/env python3
"""Audit the bin/scripts convergence manifest against the working tree.

The manifest is the decision SSOT; the execution report is evidence only.
This command makes that distinction executable and provides a conservative
reconciliation path for entries whose retirement is explicitly documented.
"""

from __future__ import annotations

import argparse
import json
from typing import Any
from collections import Counter
from pathlib import Path

DEFAULT_MANIFEST = Path(".omo/_archive/operations-2026H1/bin-scripts-convergence-manifest.json")
DEFAULT_EXECUTION_REPORT = Path(".omo/_archive/operations-2026H1/bin-scripts-close-duplicate-exec.md")


def parse_execution_report(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or "removed" not in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 7 or cells[4] != "removed":
            continue
        rows[cells[0]] = {"status": cells[4], "bin": cells[5], "scripts": cells[6]}
    return rows


def _load_json_tolerant(path: Path) -> Any:
    # staleness 管线会给 .json 盖 last-reviewed frontmatter, 读侧剥掉再解析
    # (2026-08-26: 6251163a5 之后 manifest 头部出现 --- 包裹, json.loads 直接崩)
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:].lstrip("\n")
    return json.loads(text)


def audit(root: Path, manifest_path: Path, execution_path: Path) -> dict[str, object]:
    manifest = _load_json_tolerant(manifest_path)
    entries = manifest.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("manifest.entries must be a list")

    execution = parse_execution_report(execution_path)
    counts = Counter(str(entry.get("name", "")) for entry in entries)
    findings: list[dict[str, object]] = []

    for name, count in sorted(counts.items()):
        if name and count > 1:
            findings.append({"kind": "duplicate-manifest-key", "name": name, "count": count})

    for entry in entries:
        name = str(entry.get("name", ""))
        bin_rel = str(entry.get("bin", ""))
        scripts_rel = str(entry.get("scripts", ""))
        action = str(entry.get("action", ""))
        bin_exists = bool(bin_rel) and (root / bin_rel).is_file()
        scripts_exists = bool(scripts_rel) and (root / scripts_rel).is_file()
        report = execution.get(name)

        if not bin_exists:
            findings.append({"kind": "missing-bin-master", "name": name, "path": bin_rel})
        if report and scripts_exists:
            findings.append(
                {
                    "kind": "reported-removed-but-present",
                    "name": name,
                    "path": scripts_rel,
                }
            )
        if "scripts-compat-shim" in action and not scripts_exists:
            findings.append({"kind": "missing-compat-shim", "name": name, "path": scripts_rel})
        if action == "close-duplicate-gap-first" and scripts_exists:
            findings.append({"kind": "open-duplicate", "name": name, "path": scripts_rel})
        if action == "close-duplicate-gap-first" and not scripts_exists and report:
            findings.append(
                {
                    "kind": "execution-confirmed-manifest-stale",
                    "name": name,
                    "path": scripts_rel,
                }
            )
        if not bin_exists and scripts_exists:
            findings.append({"kind": "scripts-only-entry", "name": name, "path": scripts_rel})

    return {
        "schema": "bin-scripts-convergence-audit/v1",
        "manifest": str(manifest_path),
        "execution_report": str(execution_path),
        "summary": {
            "manifest_entries": len(entries),
            "unique_names": len(counts),
            "reported_removed": len(execution),
            "findings": len(findings),
            "blocking_findings": len(findings),
        },
        "findings": findings,
    }


def reconcile_manifest(root: Path, manifest_path: Path, execution_path: Path) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("entries", [])
    execution = parse_execution_report(execution_path)
    output: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    reconciled = 0
    deduplicated = 0

    for entry in entries:
        name = str(entry.get("name", ""))
        key = (name, str(entry.get("bin", "")), str(entry.get("scripts", "")))
        if key in seen:
            deduplicated += 1
            continue
        seen.add(key)
        scripts_rel = str(entry.get("scripts", ""))
        if (
            entry.get("action") == "close-duplicate-gap-first"
            and name in execution
            and scripts_rel
            and not (root / scripts_rel).is_file()
        ):
            entry = dict(entry)
            entry["action"] = "bin-master, scripts-retired"
            entry["note"] = (
                "Execution report confirms retirement of the scripts duplicate; "
                "bin remains the single implementation."
            )
            evidence = dict(entry.get("evidence", {}))
            evidence["active_files"] = [str(entry.get("bin", ""))]
            evidence["retired_files"] = [scripts_rel]
            evidence["execution_report"] = str(execution_path)
            entry["evidence"] = evidence
            reconciled += 1
        output.append(entry)

    manifest["entries"] = output
    manifest["reconciliation"] = {
        "deduplicated_entries": deduplicated,
        "retired_entries": reconciled,
        "source": str(execution_path),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"reconciled: retired={reconciled} deduplicated={deduplicated}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--execution-report", default=str(DEFAULT_EXECUTION_REPORT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--reconcile", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    manifest = (root / args.manifest).resolve()
    execution = (root / args.execution_report).resolve()
    if args.reconcile:
        return reconcile_manifest(root, manifest, execution)
    payload = audit(root, manifest, execution)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        summary = payload["summary"]
        print(
            "bin/scripts convergence: "
            f"entries={summary['manifest_entries']} unique={summary['unique_names']} "
            f"reported_removed={summary['reported_removed']} findings={summary['findings']}"
        )
        for finding in payload["findings"]:
            print(f"  {finding['kind']}: {finding['name']}")
    return 1 if args.check and payload["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
