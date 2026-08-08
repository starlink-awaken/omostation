"""Backfill status=active for BOS services that have execution config but no status.

P78 triple-axis: only sets status=active when the service has command, mcp_tool,
or i0_route. Skips services that are explicitly unimplemented or deprecated.
Also fixes the misclassified bos://governance/protocols-layer/trigger
(deprecated → unimplemented, since kairon has no protocols_layer package).
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path("/Users/xiamingxing/Workspace")
BOS_YAML = REPO_ROOT / "projects" / "agora" / "etc" / "bos-services.yaml"


def has_execution_config(svc: dict) -> bool:
    """A service is reachable if it has any of:
    command (subprocess), mcp_tool (mcp_proxy), i0_route (inline),
    http_url (HTTP endpoint), tools (mcp_proxy tools list),
    or module_path+func_name (in-process Python call).
    """
    if svc.get("command") or svc.get("mcp_tool") or svc.get("i0_route") or svc.get("http_url"):
        return True
    if svc.get("module_path") and svc.get("func_name"):
        return True
    if svc.get("tools"):  # mcp_proxy: list of tools
        return True
    return False


def main() -> int:
    if not BOS_YAML.is_file():
        print(f"ERROR: {BOS_YAML} not found", file=sys.stderr)
        return 1

    text = BOS_YAML.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    services = data.get("services", [])

    added_active = 0
    flipped_deprecated = 0
    skipped_with_status = 0
    skipped_unimplemented = 0
    skipped_deprecated = 0
    no_config = 0

    for svc in services:
        uri = svc.get("uri", "?")
        status = svc.get("status", None)
        if status == "unimplemented":
            skipped_unimplemented += 1
            continue
        if status == "deprecated":
            if uri == "bos://governance/protocols-layer/trigger":
                # misclassified: never implemented
                svc["status"] = "unimplemented"
                flipped_deprecated += 1
                print(f"flipped deprecated → unimplemented: {uri}")
            else:
                skipped_deprecated += 1
            continue
        if status is not None:
            skipped_with_status += 1
            continue
        if not has_execution_config(svc):
            no_config += 1
            continue
        svc["status"] = "active"
        added_active += 1

    summary = {
        "added_active": added_active,
        "flipped_deprecated_to_unimplemented": flipped_deprecated,
        "skipped_already_has_status": skipped_with_status,
        "skipped_unimplemented": skipped_unimplemented,
        "skipped_deprecated": skipped_deprecated,
        "no_execution_config": no_config,
    }
    print()
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    # Write back
    out = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
    BOS_YAML.write_text(out, encoding="utf-8")
    print(f"\nWritten: {BOS_YAML}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
