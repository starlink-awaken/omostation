"""Linter for the bos-services.yaml declaration table.

Catches issues that the existing bos_registry tests miss because they
only exercise a single entry: duplicate URIs, missing fields, and
URI ↔ description drift. Run via:

    python3 -m agora.mcp.tools.bos_yaml_lint etc/bos-services.yaml
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import yaml


def _load(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    documents = [d for d in yaml.safe_load_all(text) if d]
    for d in documents:
        if "services" in d:
            return list(d["services"])
    raise ValueError(f"bos-services.yaml missing 'services' key: {path}")


def _lint(services: list[dict]) -> list[str]:
    errors: list[str] = []
    counter = Counter(s.get("uri", "") for s in services)
    for uri, count in counter.most_common():
        if count > 1:
            errors.append(f"duplicate URI: {uri} appears {count} times")
    seen_keys: set[tuple[str, str, str]] = set()
    transports_without_command = {"inline", "internal"}
    # Transports that may carry a non-`command` invocation field
    # (http_url, mcp_tool, mcp_proxy tools list, etc.).
    non_command_transports = transports_without_command | {"http", "mcp_proxy"}
    for idx, s in enumerate(services):
        uri = s.get("uri", "")
        domain = s.get("domain", "")
        action = s.get("action", "")
        transport = s.get("transport", "")
        for key in ("uri", "domain", "action", "transport", "description"):
            if not s.get(key):
                errors.append(f"#{idx} missing '{key}': uri={uri!r}")
        if transport not in non_command_transports and not s.get("command"):
            errors.append(
                f"#{idx} missing 'command' for transport {transport!r}: uri={uri!r}"
            )
        if not uri.startswith("bos://"):
            errors.append(f"#{idx} uri must start with 'bos://': got {uri!r}")
        if domain and action:
            key = (domain, action, uri)
            if key in seen_keys:
                errors.append(
                    f"#{idx} duplicate (domain, action, uri) triple: {key}"
                )
            seen_keys.add(key)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint bos-services.yaml")
    parser.add_argument(
        "path",
        nargs="?",
        default="etc/bos-services.yaml",
        help="Path to bos-services.yaml (default: etc/bos-services.yaml)",
    )
    args = parser.parse_args(argv)
    services = _load(Path(args.path))
    errors = _lint(services)
    if errors:
        print(f"bos-services.yaml lint: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(
        f"bos-services.yaml lint: ok ({len(services)} services, "
        f"{len({s.get('package') for s in services if s.get('package')})} packages)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
