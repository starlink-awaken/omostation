#!/usr/bin/env python3
"""Generate a review-only inventory from Cockpit UI route declarations.

This does not decide route disposition, authorize actions, or prove runtime
parity. Unassessed mappings intentionally remain NOT_ASSESSED/HOLD.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTES_TS = ROOT / "projects/cockpit-ui/src/routes.tsx"
ROUTER_REGISTRY = ROOT / "projects/cockpit/src/cockpit/web/router_health.py"
DEFAULT_OUTPUT = ROOT / "docs/registry/dashboard-route-disposition-inventory.json"
GENERATOR = Path(__file__).resolve()

FIELD_RE = re.compile(r"\b(id|path|label|group|domain|component|purpose|whenToUse):\s*'([^']*)'")
COMPONENT_RE = re.compile(r"\bcomponent:\s*([A-Za-z_$][\w$]*)")
ALIAS_RE = re.compile(r"^\s*'([^']+)':\s*'([^']+)',?\s*$")
LAZY_IMPORT_RE = re.compile(
    r"^const\s+([A-Za-z_$][\w$]*)\s*=\s*lazy\(\(\)\s*=>\s*import\('([^']+)'\)\);$",
    re.MULTILINE,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_routes() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    source = ROUTES_TS.read_text(encoding="utf-8")
    component_sources = {name: module for name, module in LAZY_IMPORT_RE.findall(source)}

    def resolve_component_source(module: str) -> str:
        base = (ROUTES_TS.parent / module).resolve()
        candidates = [base.with_suffix(ext) for ext in (".tsx", ".ts", ".jsx", ".js")]
        candidates.extend(base / f"index{ext}" for ext in (".tsx", ".ts", ".jsx", ".js"))
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate.relative_to(ROOT))
        raise ValueError(f"lazy component module does not resolve to a source file: {module}")

    route_block = source.split("export const ROUTES: RouteConfig[] = [", 1)[1].split("\n];", 1)[0]
    routes: list[dict[str, object]] = []
    for line_number, line in enumerate(route_block.splitlines(), start=1):
        if "{ id:" not in line:
            continue
        fields = dict(FIELD_RE.findall(line))
        component = COMPONENT_RE.search(line)
        if component:
            fields["component"] = component.group(1)
        required = {"id", "path", "label", "group", "component"}
        if not required.issubset(fields):
            raise ValueError(f"could not parse route at routes.tsx block line {line_number}: {line}")
        if fields["component"] not in component_sources:
            raise ValueError(f"route component has no lazy import declaration: {fields['component']}")
        routes.append(
            {
                "id": fields["id"],
                "path": fields["path"],
                "label": fields["label"],
                "group": fields["group"],
                "domain": fields.get("domain"),
                "component": fields["component"],
                "component_source": resolve_component_source(component_sources[fields["component"]]),
                "purpose": fields.get("purpose"),
                "when_to_use": fields.get("whenToUse"),
                "hidden_from_sidebar": bool(re.search(r"\bhidden:\s*true\b", line)),
                "api_paths": ["/api/governance/panorama"] if fields["path"] == "/panorama" else [],
                "api_mapping_status": "PARTIAL" if fields["path"] == "/panorama" else "NOT_ASSESSED",
                "source_owner": "UNKNOWN",
                "persona_policy": {
                    "administrator": "UNKNOWN",
                    "agent": "UNKNOWN",
                    "business_user": "UNKNOWN",
                },
                "error_and_empty_state_parity": "UNKNOWN",
                "consumers": [],
                "migration_and_rollback": "UNKNOWN",
                "runtime_verification": "NOT_RUN",
                "disposition": "UNDECIDED",
                "gate": "HOLD",
            }
        )

    alias_block = source.split("export const ROUTE_REDIRECTS: Record<string, string> = {", 1)[1].split("\n};", 1)[0]
    aliases: list[dict[str, object]] = []
    for line in alias_block.splitlines():
        if not line.strip():
            continue
        match = ALIAS_RE.match(line)
        if not match:
            raise ValueError(f"could not parse redirect declaration: {line}")
        source_path, target_path = match.groups()
        aliases.append(
            {
                "path": source_path,
                "target_path": target_path,
                "redirect_declared": True,
                "consumer_refs": [],
                "persona_policy": {
                    "administrator": "UNKNOWN",
                    "agent": "UNKNOWN",
                    "business_user": "UNKNOWN",
                },
                "deep_link_and_query_parity": "UNKNOWN",
                "rollback": "UNKNOWN",
                "runtime_verification": "NOT_RUN",
                "disposition": "UNDECIDED",
                "gate": "HOLD",
            }
        )

    if len(routes) != 56:
        raise ValueError(f"expected 56 declared routes, found {len(routes)}")
    if len(aliases) != 15:
        raise ValueError(f"expected 15 redirect aliases, found {len(aliases)}")
    route_paths = [str(route["path"]) for route in routes]
    alias_paths = [str(alias["path"]) for alias in aliases]
    if len(set(route_paths)) != len(route_paths):
        raise ValueError("duplicate route paths found")
    if len(set(alias_paths)) != len(alias_paths):
        raise ValueError("duplicate alias paths found")
    unknown_targets = sorted({str(alias["target_path"]) for alias in aliases} - set(route_paths))
    if unknown_targets:
        raise ValueError(f"redirect aliases target undeclared routes: {unknown_targets}")
    return routes, aliases


def render() -> str:
    routes, aliases = read_routes()
    document = {
        "schema": "cockpit-route-disposition-inventory/v1",
        "review_state": "UNREVIEWED_CANDIDATE",
        "authority_note": "Generated inventory only; not a disposition decision, authorization contract, runtime proof, or retirement order.",
        "sources": {
            "generator": str(GENERATOR.relative_to(ROOT)),
            "generator_sha256": sha256(GENERATOR),
            "routes_tsx": str(ROUTES_TS.relative_to(ROOT)),
            "routes_tsx_sha256": sha256(ROUTES_TS),
            "api_router_registry": str(ROUTER_REGISTRY.relative_to(ROOT)),
            "api_router_registry_sha256": sha256(ROUTER_REGISTRY),
        },
        "summary": {
            "route_count": len(routes),
            "redirect_alias_count": len(aliases),
            "routes_with_partial_api_mapping": sum(route["api_mapping_status"] == "PARTIAL" for route in routes),
            "routes_with_unassessed_api_mapping": sum(route["api_mapping_status"] == "NOT_ASSESSED" for route in routes),
            "api_mapping_note": "NOT_ASSESSED means the route-to-request dependency closure has not been reviewed; it does not mean the route has no API.",
            "all_records_hold_until_review": True,
        },
        "routes": routes,
        "redirect_aliases": aliases,
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="write the generated candidate inventory")
    group.add_argument("--check", action="store_true", help="fail when the checked-in inventory differs")
    args = parser.parse_args()

    generated = render()
    if args.check:
        try:
            existing = args.output.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"missing inventory: {args.output}", file=sys.stderr)
            return 1
        if existing != generated:
            print(f"inventory is stale: {args.output}", file=sys.stderr)
            return 1
        print("route inventory matches source declarations")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8")
    print(f"wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
