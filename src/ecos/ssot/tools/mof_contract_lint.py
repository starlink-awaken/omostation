#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mof-contract-lint.py v0.1

A static analyzer for BOS Service Contracts (Phase 0, 30-day plan).

Validates:
- internal transport module/function existence (importlib check)
- required_scopes validity against omo.scopes.ALL_SCOPES (with fallback)
- action field naming convention (warning only, lightweight)

Adaptations from proposal (P110):
- A1: importlib_metadata backport removed (Python 3.13 target)
- A2: Required dependencies already in pyproject (pyyaml, rich)
- A3: --json output without --strict flag (per proposal main())
- O1: --quiet flag added (optional improvement)

Usage:
  uv run mof contract-lint           # human-readable table
  uv run mof contract-lint --json    # JSON output (for CI)

Exit codes:
  0 = success (no errors, warnings ok)
  1 = error (one or more errors)
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError:
    print(
        "ERROR: Required dependencies (pyyaml, rich) not found. Run 'uv sync' in projects/ecos.",
        file=sys.stderr,
    )
    sys.exit(1)

console = Console()


def load_bos_services_yaml(path: Path) -> dict[str, Any] | None:
    """Load bos-services.yaml from given path."""
    if not path.exists():
        console.print(f"[red]ERROR:[/red] {path} not found.")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:  # defensive fallback
        console.print(f"[red]ERROR:[/red] Failed to parse {path}: {e}")
        return None


def validate_internal_transport(services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate internal transport services: module_path/func_name existence.

    Uses importlib.import_module + hasattr to verify the function is reachable.
    This catches typos in module_path/func_name BEFORE runtime.
    """
    errors: list[dict[str, Any]] = []
    for service in services:
        if service.get("transport") != "internal":
            continue
        uri = service.get("uri", "UNKNOWN")
        module_path = service.get("module_path")
        func_name = service.get("func_name")

        if not module_path or not func_name:
            errors.append(
                {
                    "uri": uri,
                    "rule": "INTERNAL_MODULE_NOT_FOUND",
                    "level": "error",
                    "message": (
                        f"INTERNAL_MODULE_NOT_FOUND: {uri} -> "
                        f"Missing 'module_path' or 'func_name'."
                    ),
                }
            )
            continue

        try:
            mod = importlib.import_module(module_path)
        except ImportError as e:
            errors.append(
                {
                    "uri": uri,
                    "rule": "INTERNAL_MODULE_NOT_FOUND",
                    "level": "error",
                    "message": (
                        f"INTERNAL_MODULE_NOT_FOUND: {uri} -> "
                        f"Cannot import module '{module_path}': {e}."
                    ),
                }
            )
            continue
        except Exception as e:  # defensive fallback
            errors.append(
                {
                    "uri": uri,
                    "rule": "INTERNAL_MODULE_NOT_FOUND",
                    "level": "error",
                    "message": (
                        f"INTERNAL_MODULE_NOT_FOUND: {uri} -> "
                        f"Unexpected error importing '{module_path}': {e}."
                    ),
                }
            )
            continue

        if not hasattr(mod, func_name):
            errors.append(
                {
                    "uri": uri,
                    "rule": "INTERNAL_MODULE_NOT_FOUND",
                    "level": "error",
                    "message": (
                        f"INTERNAL_MODULE_NOT_FOUND: {uri} -> "
                        f"Cannot find function '{func_name}' in module '{module_path}'."
                    ),
                }
            )
    return errors


def validate_required_scopes(
    services: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate required_scopes against omo.scopes.ALL_SCOPES.

    Fallback: if omo.scopes not importable, issue SCOPE_VALIDATION_SKIPPED warning
    (per proposal A1 mitigation, since omo.scopes module does not exist yet).
    """
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    try:
        from omo.scopes import ALL_SCOPES  # type: ignore[import-not-found]

        valid_scopes = set(ALL_SCOPES)
    except ImportError:
        warnings.append(
            {
                "uri": "N/A",
                "rule": "SCOPE_VALIDATION_SKIPPED",
                "level": "warning",
                "message": (
                    "SCOPE_VALIDATION_SKIPPED: omo.scopes module not available. "
                    "Skipping scope validation. (See ADR-0105 A1 mitigation.)"
                ),
            }
        )
        return warnings, errors

    for service in services:
        scopes = service.get("required_scopes", []) or []
        for scope in scopes:
            if scope not in valid_scopes:
                errors.append(
                    {
                        "uri": service.get("uri", "UNKNOWN"),
                        "rule": "INVALID_SCOPE",
                        "level": "error",
                        "message": (
                            f"INVALID_SCOPE: {service.get('uri', 'UNKNOWN')} "
                            f"uses undefined scope '{scope}'."
                        ),
                    }
                )
    return warnings, errors


def validate_action_naming(services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate action field naming convention (lightweight warning).

    Heuristic: governance actions should map to omo_<action>.py; analysis to
    minerva_<action>.py or <action>.py. This is a placeholder; real logic
    would check filesystem (deferred to Phase 1).
    """
    warnings: list[dict[str, Any]] = []
    for service in services:
        action = service.get("action")
        domain = service.get("domain")
        if not action or not domain:
            continue

        expected_files: list[str] = []
        if domain == "governance":
            expected_files = [f"omo_{action}.py"]
        elif domain == "analysis":
            expected_files = [f"minerva_{action}.py", f"{action}.py"]

        if expected_files:
            warnings.append(
                {
                    "uri": service.get("uri", "UNKNOWN"),
                    "rule": "ACTION_NAMING_CONVENTION",
                    "level": "warning",
                    "message": (
                        f"ACTION_NAMING_CONVENTION: {service.get('uri', 'UNKNOWN')} "
                        f"action '{action}' should ideally map to a backend file like "
                        f"{expected_files[0]} for consistency."
                    ),
                }
            )
    return warnings


def build_result(
    services: list[dict[str, Any]],
    internal_errors: list[dict[str, Any]],
    scope_warnings: list[dict[str, Any]],
    scope_errors: list[dict[str, Any]],
    action_warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate all results into a single report."""
    all_errors = internal_errors + scope_errors
    all_warnings = scope_warnings + action_warnings
    if all_errors:
        status = "error"
    elif all_warnings:
        status = "warning"
    else:
        status = "success"
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "summary": {
            "total_checks": len(services),
            "errors": len(all_errors),
            "warnings": len(all_warnings),
            "successes": len(services) - len(all_errors) - len(all_warnings),
        },
        "details": all_errors + all_warnings,
    }


def print_human_report(result: dict[str, Any]) -> None:
    """Pretty-print report using rich tables."""
    console.print("\n[bold blue]BOS Contract Linter v0.1 Report[/bold blue]")
    console.print(f"Timestamp: {result['timestamp']}")
    status = result["status"]
    status_color = {"success": "green", "warning": "yellow", "error": "red"}.get(
        status, "white"
    )
    console.print(
        f"Status: [bold {status_color}]{status.upper()}[/bold {status_color}]"
    )
    console.print(
        f"Summary: {result['summary']['total_checks']} checks, "
        f"{result['summary']['errors']} errors, "
        f"{result['summary']['warnings']} warnings, "
        f"{result['summary']['successes']} successes"
    )

    if result["details"]:
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("URI")
        table.add_column("Rule")
        table.add_column("Level")
        table.add_column("Message")

        for detail in result["details"]:
            level_color = "red" if detail["level"] == "error" else "yellow"
            table.add_row(
                detail["uri"] or "-",
                detail["rule"],
                f"[{level_color}]{detail['level']}[/{level_color}]",
                detail["message"],
            )
        console.print(table)

    if status == "success":
        console.print("\n[bold green]OK All BOS contracts are valid.[/bold green]")
    elif status == "warning":
        console.print(
            "\n[bold yellow]WARN Warnings detected. Please review.[/bold yellow]"
        )
    else:
        console.print(
            "\n[bold red]FAIL Errors detected. Fix them before committing.[/bold red]"
        )


def explain_error(error_id: str) -> tuple[str, bool]:
    """Return natural language explanation for a given error/warning ID.

    Returns:
        (text, found) tuple. found=True if error_id known, else False.

    Phase 2 v0.2: covers 4 IDs (vs proposal 2):
      - INTERNAL_MODULE_NOT_FOUND (error)
      - INVALID_SCOPE (error)
      - SCOPE_VALIDATION_SKIPPED (warning)
      - ACTION_NAMING_CONVENTION (warning)
    """
    explanations = {
        "INTERNAL_MODULE_NOT_FOUND": (
            "This error means you've declared a BOS service with `transport: internal`, "
            "but Python cannot find the module or function you specified.\n\n"
            "**How to fix it:**\n"
            "1. Check that the `module_path` (e.g., `omo.omo_audit`) points to a real Python file.\n"
            "2. Verify that the `func_name` (e.g., `run_governance_audit`) is defined as a function in that file.\n"
            "3. Ensure the file exists at the correct path: `projects/omo/src/omo/omo_audit.py`.\n"
            "4. If the file exists but is in a different submodule, ensure that submodule is "
            "installed (`uv pip install -e projects/<submodule>`) or on sys.path.\n\n"
            "**Common causes:**\n"
            "- Typo in `module_path` or `func_name`\n"
            "- Module not yet created (planned in roadmap)\n"
            "- Submodule not initialized (`git submodule update --recursive`)"
        ),
        "INVALID_SCOPE": (
            "This error means your service requires a permission (`required_scopes`) "
            "that has not been defined in the system.\n\n"
            "**How to fix it:**\n"
            "1. Open `projects/omo/src/omo/scopes.py`.\n"
            "2. Look for the `ALL_SCOPES` set.\n"
            "3. Add your new scope (e.g., `governance:audit`) to this set, following the "
            "`domain:action` naming pattern.\n\n"
            "**Naming convention:** Use `domain:action` format (e.g., `memory:search`, "
            "`governance:audit`). Avoid generic names like `admin` or `all`."
        ),
        "SCOPE_VALIDATION_SKIPPED": (
            "This warning means the `omo.scopes` module is not available, so scope validation "
            "was skipped entirely.\n\n"
            "**How to enable scope validation:**\n"
            "1. Create `projects/omo/src/omo/scopes.py` if it does not exist.\n"
            "2. Define `ALL_SCOPES = {'governance:audit', 'memory:search', ...}` as a set.\n"
            "3. Ensure the omo submodule is on sys.path when running this tool.\n\n"
            "**Why it matters:** Without ALL_SCOPES, we cannot detect INVALID_SCOPE errors. "
            "Until then, scope drift in bos-services.yaml will go unnoticed."
        ),
        "ACTION_NAMING_CONVENTION": (
            "This warning indicates a backend file naming inconsistency.\n\n"
            "**Convention:**\n"
            "- `domain: governance` -> `projects/omo/src/omo/omo_<action>.py`\n"
            "- `domain: analysis` -> `projects/kairon/packages/minerva/minerva_<action>.py` or `<action>.py`\n"
            "- `domain: memory` -> `projects/kairon/packages/kos/kos/cli.py`\n"
            "- `domain: capability` -> `projects/aetherforge/packages/swarm/...`\n\n"
            "**Why it matters:** Consistent naming makes refactoring and code search easier. "
            "It also enables the `--impact` analysis to find related backend files."
        ),
    }
    return explanations.get(error_id, ""), error_id in explanations


def analyze_impact(
    uri: str, services: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Analyze the impact of changing a given BOS URI.

    Returns structured report:
      - direct_dependencies: URIs that may directly depend on this one
      - affected_files: backend files likely to be affected
      - match_found: True if URI matched any (domain, action) key

    Phase 2 v0.2: 12 file_mappings (vs proposal 3, A1 adjustment).
    Heuristic rule-based analysis. Production would use graph analysis.
    """
    if services is None:
        return {"error": "No services data provided", "match_found": False}

    # Parse URI: bos://<domain>/<package>/<action>
    parts = uri.split("/")
    if len(parts) < 4 or not uri.startswith("bos://"):
        return {"error": f"Invalid URI format: {uri}", "match_found": False}

    domain = parts[2]
    action = parts[-1]

    # 12 file_mappings (A1: extended from proposal 3)
    file_mappings: dict[tuple[str, str], list[str]] = {
        ("governance", "audit"): [
            "projects/omo/src/omo/omo_audit.py",
            ".omo/_truth/x1-governance-policies.yaml",
        ],
        ("governance", "inspect"): [
            "projects/omo/src/omo/omo_inspect.py",
        ],
        ("governance", "decide"): [
            "projects/metaos/src/metaos/decide.py",
        ],
        ("governance", "gate"): [
            "projects/omo/src/omo/omo_governance.py",
            "projects/omo/src/omo/omo_governance_surfaces.py",
        ],
        ("governance", "debt"): [
            "projects/omo/src/omo/omo_debt.py",
            "projects/omo/src/omo/omo_debt_approval.py",
        ],
        ("analysis", "search"): [
            "projects/kairon/packages/minerva/minerva_search.py",
        ],
        ("analysis", "research"): [
            "projects/kairon/packages/minerva/minerva_research.py",
        ],
        ("memory", "search"): [
            "projects/kairon/packages/kos/kos/cli.py",
        ],
        ("memory", "ingest"): [
            "projects/kairon/packages/kos/kos/cli.py",
        ],
        ("memory", "all-search"): [
            "projects/agora/src/agora/mcp/bos_resolver.py",
        ],
        ("capability", "run"): [
            "projects/aetherforge/packages/swarm/src/swarm_engine/rpc.py",
        ],
        ("meta", "discover"): [
            "projects/agora/src/agora/mcp/bos_resolver.py",
        ],
    }

    impacted = {
        "uri": uri,
        "domain": domain,
        "action": action,
        "direct_dependencies": [],
        "affected_files": [],
        "match_found": False,
    }

    # Rule 1: Find services that share domain or module_path (heuristic)
    for service in services:
        svc_uri = service.get("uri", "")
        if svc_uri == uri:
            continue
        svc_domain = service.get("domain", "")
        svc_module = service.get("module_path", "")
        # Same domain (e.g., all governance services)
        if svc_domain == domain and svc_domain:
            impacted["direct_dependencies"].append(svc_uri)
        # Same module_path prefix (e.g., all omo.* services)
        elif svc_module.startswith("omo.") and uri.startswith("bos://governance/"):
            impacted["direct_dependencies"].append(svc_uri)

    # Rule 2: Map (domain, action) to backend files
    key = (domain, action)
    if key in file_mappings:
        impacted["affected_files"] = file_mappings[key]
        impacted["match_found"] = True

    return impacted


def main() -> int:
    """Main entry point for mof contract-lint subcommand."""
    parser = argparse.ArgumentParser(
        description="Validate BOS Service Contracts (Phase 0+2 tool)."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format (for CI integration).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress human-readable output (only print summary line).",
    )
    parser.add_argument(
        "--explain",
        type=str,
        metavar="ERROR_ID",
        help="Phase 2: Explain an error/warning ID with natural language guide.",
    )
    parser.add_argument(
        "--impact",
        type=str,
        metavar="URI",
        help="Phase 2: Analyze impact of changing a BOS URI (deps + files).",
    )
    parser.add_argument(
        "--bos-yaml",
        type=Path,
        default=Path("projects/agora/etc/bos-services.yaml"),
        help="Path to bos-services.yaml (default: projects/agora/etc/bos-services.yaml).",
    )
    args = parser.parse_args()

    # Phase 2: --explain <error-id> (no bos-yaml needed)
    if args.explain:
        text, found = explain_error(args.explain)
        if found:
            console.print(
                Panel(
                    text,
                    title=f"Explanation for {args.explain}",
                    border_style="blue",
                    expand=False,
                )
            )
            return 0
        else:
            console.print(f"[red]ERROR:[/red] Unknown error_id '{args.explain}'.")
            console.print("Known error_ids:")
            # Show all known IDs from all 3 validators (not via explain_error)
            console.print("  - INTERNAL_MODULE_NOT_FOUND")
            console.print("  - INVALID_SCOPE")
            console.print("  - SCOPE_VALIDATION_SKIPPED")
            console.print("  - ACTION_NAMING_CONVENTION")
            return 1

    # Phase 2: --impact <uri> (needs bos-yaml)
    if args.impact:
        services_data = load_bos_services_yaml(args.bos_yaml)
        if not services_data:
            return 1
        services = services_data.get("services", [])
        report = analyze_impact(args.impact, services)
        if "error" in report:
            if args.json:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            else:
                console.print(f"[red]ERROR:[/red] {report['error']}")
            return 1
        if args.json:
            # Phase 3: --impact --json for agent integration
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0
        console.print(f"\n[bold blue]Impact Analysis for {args.impact}[/bold blue]")
        console.print(f"Domain: {report['domain']}, Action: {report['action']}")
        if report["direct_dependencies"]:
            console.print(
                f"\n[bold]Direct Dependencies ({len(report['direct_dependencies'])}):[/bold]"
            )
            for dep in report["direct_dependencies"][:10]:  # Cap display
                console.print(f"  - {dep}")
            if len(report["direct_dependencies"]) > 10:
                console.print(
                    f"  ... and {len(report['direct_dependencies']) - 10} more"
                )
        else:
            console.print("\n[dim]No direct dependencies found.[/dim]")
        if report["affected_files"]:
            console.print(
                f"\n[bold]Affected Files ({len(report['affected_files'])}):[/bold]"
            )
            for f in report["affected_files"]:
                console.print(f"  - {f}")
        else:
            console.print(
                f"\n[yellow]WARN:[/yellow] No file_mapping for (domain={report['domain']}, action={report['action']})"
            )
            console.print(
                "  Add to file_mappings in mof_contract_lint.py or open an issue."
            )
            return 1  # A4: not-found exit 1
        return 0

    # Default behavior: run validation
    services_data = load_bos_services_yaml(args.bos_yaml)
    if not services_data:
        return 1

    services = services_data.get("services", [])
    if not isinstance(services, list):
        console.print("[red]ERROR:[/red] 'services' field must be a list.")
        return 1

    # Run validations
    internal_errors = validate_internal_transport(services)
    scope_warnings, scope_errors = validate_required_scopes(services)
    action_warnings = validate_action_naming(services)

    result = build_result(
        services, internal_errors, scope_warnings, scope_errors, action_warnings
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if result["summary"]["errors"] > 0 else 0

    if not args.quiet:
        print_human_report(result)
    else:
        # Quiet mode: just one-line summary
        s = result["summary"]
        print(
            f"BOS contracts: {s['total_checks']} checks, "
            f"{s['errors']} errors, {s['warnings']} warnings -> {result['status']}"
        )
    return 1 if result["summary"]["errors"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
