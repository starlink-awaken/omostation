#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mof_contract_agent.py — Phase 3 (BOS Contract Linter Autonomy 作战包)

A dedicated agent for BOS Contract analysis and repair.

Can be invoked by other agents with:
  - "Analyze the BOS service at bos://governance/omo/audit"
  - "Fix the INTERNAL_MODULE_NOT_FOUND error in projects/agora/etc/bos-services.yaml"
  - "Diagnose this mof contract-lint error: <error_log>"

Phase 3 v0.1 (P110+):
- analyze_service(): Real subprocess call to `mof-contract-lint --impact --json`,
  no mock data (Phase 3 C2 adjustment vs proposal mock).
- diagnose_error(): Imports Phase 2 v0.2 `explain_error()` for 4 IDs (vs 2 in proposal).
  Plus direct string match on error log for robust ID extraction.
- main(): Two CLI subcommands — `analyze <uri>` and `diagnose <error_log>`.

Usage:
  mof-contract-agent analyze "bos://governance/omo/audit" [--bos-yaml <path>]
  mof-contract-agent diagnose "INTERNAL_MODULE_NOT_FOUND: bos://..."

Exit codes:
  0 = success (analysis/diagnosis output)
  1 = error (subprocess failed, JSON parse failed, or unknown error_id)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# Reuse Phase 2 v0.2 explain_error for 4 error IDs (vs proposal 2)
from ecos.ssot.tools.mof_contract_lint import explain_error

# Known error IDs (same as v0.2)
KNOWN_ERROR_IDS = [
    "INTERNAL_MODULE_NOT_FOUND",
    "INVALID_SCOPE",
    "SCOPE_VALIDATION_SKIPPED",
    "ACTION_NAMING_CONVENTION",
]


def _extract_error_id(error_log: str) -> str | None:
    """Extract first known error_id from error log text.

    Robust to rich/emoji/color codes (Phase 3 C3 adjustment).
    Strategy: substring match for each known ID.
    """
    for eid in KNOWN_ERROR_IDS:
        if eid in error_log:
            return eid
    return None


def analyze_service(uri: str, bos_yaml: Path | None = None) -> dict[str, Any]:
    """Analyze a single BOS service URI using mof-contract-lint --impact --json.

    Phase 3 C2: Parse real subprocess --json output, NOT mock data.
    Returns:
        dict with keys: uri, direct_dependencies, affected_files, match_found,
        error (only on failure).
    """
    cmd = ["uv", "run", "mof-contract-lint", "--impact", uri, "--json"]
    if bos_yaml is not None:
        cmd.extend(["--bos-yaml", str(bos_yaml)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd="projects/ecos",
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"error": "subprocess timeout (>30s)", "uri": uri}
    except Exception as e:  # defensive fallback
        return {"error": f"subprocess exception: {e}", "uri": uri}

    # v0.2 --impact returns exit 0 (match) or 1 (no-mapping), both with JSON output
    if result.returncode not in (0, 1):
        return {
            "error": f"mof-contract-lint unexpected exit: {result.returncode}",
            "uri": uri,
            "stderr": result.stderr[:200],
        }

    try:
        impact_report = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return {
            "error": f"JSON parse failed: {e}",
            "uri": uri,
            "raw_stdout": result.stdout[:200],
        }

    return {
        "uri": uri,
        "status": "analyzed",
        "direct_dependencies": impact_report.get("direct_dependencies", []),
        "affected_files": impact_report.get("affected_files", []),
        "match_found": impact_report.get("match_found", False),
    }


def diagnose_error(error_log: str) -> dict[str, Any]:
    """Diagnose an error log and return actionable insights.

    Phase 3 C3: Reuse Phase 2 v0.2 explain_error for 4 IDs (vs proposal 2).
    Plus extract structured fields (error_id, suggested_fix) from explanation.
    """
    error_id = _extract_error_id(error_log)
    if error_id is None:
        return {
            "error": f"Unknown error_id. Known IDs: {', '.join(KNOWN_ERROR_IDS)}",
            "hint": "Use `mof-contract-lint --explain <ID>` for details",
        }

    text, found = explain_error(error_id)
    if not found:
        return {"error": f"explain_error returned not-found for {error_id}"}

    # Extract first actionable suggestion from explanation
    suggested_fix = _extract_first_action(text)

    return {
        "error_id": error_id,
        "explanation": text,
        "suggested_fix": suggested_fix,
    }


def _extract_first_action(explanation: str) -> str:
    """Extract first numbered step from 'How to fix it:' section."""
    lines = explanation.split("\n")
    in_howto = False
    for line in lines:
        if "**How to fix it:**" in line:
            in_howto = True
            continue
        if in_howto and line.strip().startswith(("1.", "2.", "3.", "4.", "5.")):
            return line.strip()
        if in_howto and line.strip().startswith("**"):
            break  # next section
    return "See `mof-contract-lint --explain <ID>` for full guidance"


def main() -> int:
    """CLI entry point for mof-contract-agent."""
    parser = argparse.ArgumentParser(
        description="mof-contract-agent — BOS Contract analysis and repair (Phase 3)."
    )
    parser.add_argument(
        "command",
        choices=["analyze", "diagnose"],
        help="Subcommand: analyze (URI impact) or diagnose (error log).",
    )
    parser.add_argument(
        "target",
        help="URI (for analyze) or error log string (for diagnose).",
    )
    parser.add_argument(
        "--bos-yaml",
        type=Path,
        default=None,
        help="Path to bos-services.yaml (Phase 3 C6: explicit path recommended).",
    )
    args = parser.parse_args()

    if args.command == "analyze":
        result = analyze_service(args.target, args.bos_yaml)
    elif args.command == "diagnose":
        result = diagnose_error(args.target)
    else:
        print(f"ERROR: Unknown command '{args.command}'", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    sys.exit(main())
