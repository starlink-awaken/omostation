#!/usr/bin/env python3
"""
governance-migration.py — Backfill owner/expected fields in governance-checks.yaml.

Usage:
  uv run python3 bin/ssot/governance-migration.py --dry-run
  uv run python3 bin/ssot/governance-migration.py --apply
"""

import argparse
import os
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOVERNANCE_CHECKS = REPO_ROOT / ".omo" / "_truth" / "registry" / "governance-checks.yaml"


def infer_owner(check_id: str, description: str, check_type: str, dimension: str) -> str:
    desc = description.lower()
    cid = check_id.lower()
    if "health" in cid or "health" in desc:
        return "governance-team"
    if "freshness" in cid or "freshness" in desc:
        return "governance-team"
    if "stale" in cid or "staleness" in desc:
        return "governance-team"
    if "silent" in cid or "silent" in desc:
        return "governance-team"
    if "drift" in cid or "drift" in desc:
        return "governance-team"
    if "concurrent" in cid or "concurrent" in desc:
        return "governance-team"
    if "submodule" in cid or "submodule" in desc:
        return "governance-team"
    if "layer" in cid or "layer" in desc:
        return "governance-team"
    if "l0" in cid or "l0" in desc:
        return "ecos-team"
    if "mof" in cid or "mof" in desc:
        return "ecos-team"
    if "agent" in cid or "agent" in desc:
        return "governance-team"
    if "workflow" in cid or "workflow" in desc:
        return "governance-team"
    if "resident" in cid or "resident" in desc:
        return "omo-team"
    if "bcos" in cid or "bcos" in desc:
        return "omo-team"
    if "scene" in cid or "scene" in desc:
        return "omo-team"
    if "journey" in cid or "journey" in desc:
        return "omo-team"
    if "doc" in cid or "document" in desc:
        return "governance-team"
    if "link" in cid or "link" in desc:
        return "governance-team"
    if "ssot" in cid or "ssot" in desc:
        return "governance-team"
    if "state" in cid or "state" in desc:
        return "governance-team"
    if "test" in cid or "test" in desc:
        return "governance-team"
    if "security" in cid or "security" in desc:
        return "governance-team"
    if "mutation" in cid or "mutation" in desc:
        return "governance-team"
    if "ingress" in cid or "ingress" in desc:
        return "omo-team"
    if "memory" in cid or "memory" in desc:
        return "omo-team"
    if "external" in cid or "external" in desc:
        return "agora-team"
    if "bus" in cid or "bus" in desc:
        return "bus-team"
    if "capability" in cid or "capability" in desc:
        return "agora-team"
    if "model" in cid or "model" in desc:
        return "model-driven-team"
    if "l4" in cid or "l4" in desc:
        return "l4-kernel-team"
    if "family" in cid or "family" in desc:
        return "family-hub-team"
    if "observability" in cid or "observability" in desc:
        return "observability-team"
    if "runtime" in cid or "runtime" in desc:
        return "runtime-team"
    if "aetherforge" in cid or "aetherforge" in desc:
        return "aetherforge-team"
    if "cockpit" in cid or "cockpit" in desc:
        return "cockpit-team"
    if "agora" in cid or "agora" in desc:
        return "agora-team"
    if "meta" in cid or "meta" in desc:
        return "metaos-team"
    if "knowledge" in cid or "knowledge" in desc:
        return "knowledge-team"
    if "omo" in cid or "omo" in desc:
        return "omo-team"
    if "ecos" in cid or "ecos" in desc:
        return "ecos-team"
    return "governance-team"


def infer_expected(check_id: str, check_type: str, target: str) -> str:
    ct = check_type.lower()
    if "ssot_pointer" in ct:
        return f"{target} is the unique source of truth; no markdown or other file may duplicate this value"
    if "port_hardcode" in ct:
        return f"No hardcoded port values in source; all ports must come from {target or 'port-registry.yaml'}"
    if "import_nucleus" in ct:
        return f"Imports from {target or 'higher layers'} are prohibited unless explicitly exempted"
    if "direct_omo_io" in ct:
        return f"Direct .omo/ writes are prohibited; all mutations must flow through approved brokers"
    if "broad_except" in ct:
        return f"Broad except clauses must not swallow all exceptions without logging"
    if "state_plane_asset" in ct:
        return f"Runtime assets must not be stored in state plane directories"
    if "mutation_surface" in ct:
        return f"Mutation surfaces must be registered and audited"
    if "doc_lifecycle" in ct:
        return f"Documents must have valid frontmatter and lifecycle metadata"
    if "layer_contract" in ct:
        return f"Cross-layer imports must comply with layer-contract.yaml"
    if "test_coverage" in ct:
        return f"Test coverage must meet project thresholds"
    if "ssot_lint" in ct:
        return f"SSOT references in markdown must point to valid files"
    if "registry_integrity" in ct:
        return f"Registry files must be valid YAML and match schema"
    if "consistency_drift" in ct:
        return f"No unexplained drift between declared and actual state"
    return f"Check {check_id} must pass without violations"


def infer_remediation(check_id: str, check_type: str, target: str) -> str:
    ct = check_type.lower()
    if "ssot_pointer" in ct:
        return "Remove duplicated value from markdown; reference the SSOT file instead"
    if "port_hardcode" in ct:
        return "Replace hardcoded port with environment variable or port-registry reference"
    if "import_nucleus" in ct:
        return "Remove prohibited import or register explicit exception with ADR"
    if "direct_omo_io" in ct:
        return "Route mutation through OMO CLI/MCP or approved broker"
    if "doc_lifecycle" in ct:
        return "Add or fix frontmatter: status, type, owner, lifecycle, last-reviewed"
    if "layer_contract" in ct:
        return "Remove cross-layer import or register exception in layer-contract.yaml"
    if "test_coverage" in ct:
        return "Add tests for uncovered code or adjust coverage threshold"
    if "ssot_lint" in ct:
        return "Fix or remove broken SSOT reference"
    if "registry_integrity" in ct:
        return "Fix YAML syntax or update registry entry to match schema"
    if "consistency_drift" in ct:
        return "Align declared state with actual state; update SSOT or code"
    return "Investigate check failure and apply targeted fix"


def migrate(dry_run: bool = False) -> None:
    if not GOVERNANCE_CHECKS.exists():
        print(f"ERROR: {GOVERNANCE_CHECKS} not found")
        sys.exit(1)

    text = GOVERNANCE_CHECKS.read_text()
    data = None
    frontmatter = {}
    for doc in yaml.safe_load_all(text):
        if isinstance(doc, dict):
            if "gac" not in doc:
                frontmatter = doc
            else:
                data = doc
                break
    if not data or "gac" not in data:
        print("ERROR: Invalid governance-checks.yaml structure")
        sys.exit(1)

    rules = data["gac"].setdefault("rules", [])
    if not rules:
        print("No rules found in governance-checks.yaml")
        sys.exit(1)

    changes = []
    for rule in rules:
        rid = rule.get("id", "unknown")
        modified = False

        if "owner" not in rule:
            rule["owner"] = infer_owner(
                rid,
                rule.get("description", ""),
                rule.get("check_type", ""),
                rule.get("dimension", ""),
            )
            modified = True

        if "expected" not in rule:
            rule["expected"] = infer_expected(
                rid,
                rule.get("check_type", ""),
                rule.get("target", ""),
            )
            modified = True

        if "remediation" not in rule:
            rule["remediation"] = infer_remediation(
                rid,
                rule.get("check_type", ""),
                rule.get("target", ""),
            )
            modified = True

        if "related_runbooks" not in rule:
            rule["related_runbooks"] = []
            modified = True

        if modified:
            changes.append(rid)

    if not changes:
        print("No changes needed. All checks already have owner/expected/remediation fields.")
        return

    print(f"Changes needed: {len(changes)} checks")
    for c in changes[:20]:
        print(f"  - {c}")
    if len(changes) > 20:
        print(f"  ... and {len(changes) - 20} more")

    if dry_run:
        print("\n[dry-run] No files written.")
        return

    # Preserve frontmatter by rewriting full document
    frontmatter = {}
    for doc in yaml.safe_load_all(text):
        if isinstance(doc, dict):
            if "rules" not in doc:
                frontmatter = doc
            else:
                break

    output = ""
    if frontmatter:
        output += "---\n"
        output += yaml.dump(frontmatter, default_flow_style=False, sort_keys=False, allow_unicode=True)
        output += "---\n"
    output += yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

    GOVERNANCE_CHECKS.write_text(output)
    print(f"\nApplied: {GOVERNANCE_CHECKS}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Governance checks migration")
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.print_help()
        sys.exit(1)

    migrate(dry_run=not args.apply)


if __name__ == "__main__":
    main()
