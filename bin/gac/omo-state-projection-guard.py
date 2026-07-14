#!/usr/bin/env python3
"""Guard for the runtime projection plane (P74 stage 2, P71 类 A 复发拦截).

Verifies that:
  1. Every canonical path declared in .omo/_truth/registry/runtime-projections.yaml
     exists in the workspace.
  2. Each declared projection is parseable YAML or JSON.
  3. Every legacy alias is either absent or equal to the canonical content
     (consistency check; allows cosmetic divergence but flags size mismatch).

Exit code: 0 when the registry is consistent, 1 otherwise. JSON output to stdout.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / ".omo/_truth/registry/runtime-projections.yaml"


def load_projection_registry() -> dict[str, dict[str, str]]:
    if not REGISTRY.exists():
        raise SystemExit(f"runtime-projections registry missing: {REGISTRY}")
    documents = [doc for doc in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if doc]
    for document in documents:
        if isinstance(document, dict) and "projections" in document:
            raw = document.get("projections") or {}
            if not isinstance(raw, dict):
                return {}
            normalized: dict[str, dict[str, str]] = {}
            for name, payload in raw.items():
                if isinstance(payload, dict):
                    state = str(payload.get("state") or "active").strip().lower()
                    if state not in {"active", "pending", "deprecated"}:
                        state = "active"
                    normalized[str(name)] = {
                        "canonical": str(payload.get("canonical") or ""),
                        "legacy": str(payload.get("legacy") or ""),
                        "lane": str(payload.get("lane") or ""),
                        "generator": str(payload.get("generator") or ""),
                        "state": state,
                    }
            return normalized
    raise SystemExit(f"runtime-projections registry has no projections document: {REGISTRY}")


def probe(path_str: str) -> dict[str, object]:
    if not path_str:
        return {"path": "", "exists": False, "kind": "missing", "size": 0}
    path = WORKSPACE / path_str
    if not path.exists():
        return {"path": path_str, "exists": False, "kind": "missing", "size": 0}
    size = path.stat().st_size
    kind = "unknown"
    if path.suffix in {".yaml", ".yml"}:
        try:
            list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
            kind = "yaml-ok"
        except yaml.YAMLError as exc:
            kind = f"yaml-error:{exc}"
    elif path.suffix == ".json":
        try:
            json.loads(path.read_text(encoding="utf-8"))
            kind = "json-ok"
        except json.JSONDecodeError as exc:
            kind = f"json-error:{exc}"
    elif path.suffix == ".md":
        kind = "markdown"
    return {"path": path_str, "exists": True, "kind": kind, "size": size}


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime projection plane guard")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args()

    registry = load_projection_registry()
    findings: list[dict[str, object]] = []
    ok = True

    for name, payload in registry.items():
        state = payload.get("state", "active")
        canonical = probe(payload["canonical"])
        if not canonical["exists"]:
            if state == "pending":
                findings.append(
                    {
                        "severity": "info",
                        "projection": name,
                        "kind": "canonical_pending",
                        "path": payload["canonical"],
                    }
                )
                continue
            ok = False
            findings.append(
                {
                    "severity": "halt",
                    "projection": name,
                    "kind": "canonical_missing",
                    "path": payload["canonical"],
                }
            )
            continue
        if isinstance(canonical["kind"], str) and canonical["kind"].startswith(("yaml-error", "json-error")):
            ok = False
            findings.append(
                {
                    "severity": "halt",
                    "projection": name,
                    "kind": "canonical_parse_error",
                    "path": payload["canonical"],
                    "detail": canonical["kind"],
                }
            )
        if payload["legacy"]:
            legacy = probe(payload["legacy"])
            if legacy["exists"] and legacy["size"] != canonical["size"]:
                findings.append(
                    {
                        "severity": "warn",
                        "projection": name,
                        "kind": "legacy_size_drift",
                        "canonical_path": payload["canonical"],
                        "legacy_path": payload["legacy"],
                        "canonical_size": canonical["size"],
                        "legacy_size": legacy["size"],
                    }
                )

    report = {
        "ok": ok,
        "projection_count": len(registry),
        "findings": findings,
    }

    if args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        status = "OK" if ok else "FAIL"
        print(f"[{status}] omo-state-projection-guard: {len(registry)} projections, {len(findings)} findings")
        for finding in findings:
            print(f"  [{finding['severity']}] {finding['kind']}: {finding}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())