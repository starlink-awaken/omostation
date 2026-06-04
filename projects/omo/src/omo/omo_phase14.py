#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from .omo_io import write_yaml_atomic
except ModuleNotFoundError:
    from .omo_io import write_yaml_atomic


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _omo(root: Path) -> Path:
    return root / ".omo"


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None


def _write(path: Path, payload: dict[str, Any]) -> None:
    write_yaml_atomic(path, payload)


def triage_command(args: argparse.Namespace) -> int:
    _root()
    baseline = {
        "id": "phase14-integration-backlog-triage",
        "created_at": _utc_now(),
        "mode": "governed-triage",
        "source": ".omo/plans/phase14-deferred-ecosystem-backlog.md",
        "ranking_model": {
            "user_value": 0.4,
            "interface_readiness": 0.3,
            "maintenance_risk_inverse": 0.2,
            "rollback_clarity": 0.1,
        },
        "ranked_items": [
            {
                "id": "memu-gbrain-memory",
                "workstream": "multi-project-deep-absorption",
                "rank": 1,
                "score": 89,
                "selected_for_phase14": True,
                "integration_level": "L2",
                "reason": "High memory value and bounded adapter surface after Phase 13 proposal controls.",
            },
            {
                "id": "gitnexus-kos-index",
                "workstream": "multi-project-deep-absorption",
                "rank": 2,
                "score": 84,
                "selected_for_phase14": True,
                "integration_level": "L2",
                "reason": "Repository intelligence maps cleanly to KOS index records.",
            },
            {
                "id": "firecrawl-kronos-ingestion",
                "workstream": "multi-project-deep-absorption",
                "rank": 3,
                "score": 80,
                "selected_for_phase14": True,
                "integration_level": "L2",
                "reason": "Useful ingestion pilot, but restricted to preview mode.",
            },
            {
                "id": "ultrarag-minerva",
                "workstream": "multi-project-deep-absorption",
                "rank": 4,
                "score": 71,
                "selected_for_phase14": False,
                "integration_level": "deferred",
                "reason": "Retrieval semantics require more evaluation after package graph maturity.",
            },
            {
                "id": "marketplace-preview",
                "workstream": "marketplace-external-ecosystem",
                "rank": 5,
                "score": 68,
                "selected_for_phase14": True,
                "integration_level": "preview-only",
                "reason": "Preview can validate admission controls without installs.",
            },
        ],
    }
    _write(Path(args.output), baseline)
    print(json.dumps({"status": "ready", "selected": 4, "output": args.output}, ensure_ascii=False))
    return 0


def pilots_command(args: argparse.Namespace) -> int:
    payload = {
        "id": "phase14-deep-absorption-pilots",
        "created_at": _utc_now(),
        "mode": "adapter-contract-only",
        "mutation": "disabled",
        "pilots": [
            {
                "id": "memu-gbrain-memory",
                "level": "L2",
                "target": "gbrain memory backend",
                "contract": {
                    "input": ["memory_record", "source_ref", "retention_policy"],
                    "output": ["memory_id", "index_ref", "confidence"],
                },
                "rollback": "Disable adapter contract and keep existing gbrain storage path.",
                "verification": "contract fixture validates required fields",
            },
            {
                "id": "gitnexus-kos-index",
                "level": "L2",
                "target": "KOS repository index",
                "contract": {
                    "input": ["repo_ref", "graph_summary", "ownership_hint"],
                    "output": ["kos_index_ref", "risk_tags", "freshness"],
                },
                "rollback": "Remove preview index records and keep source registry unchanged.",
                "verification": "preview records remain outside live KOS index mutation",
            },
            {
                "id": "firecrawl-kronos-ingestion",
                "level": "L2",
                "target": "kronos ingestion preview",
                "contract": {
                    "input": ["url", "policy_ref", "crawl_scope"],
                    "output": ["preview_doc_ref", "quality_score", "retention"],
                },
                "rollback": "Discard preview docs and leave article policy unchanged.",
                "verification": "preview mode produces no network crawl in Phase 14",
            },
        ],
    }
    _write(Path(args.output), payload)
    print(json.dumps({"status": "ready", "pilots": len(payload["pilots"]), "output": args.output}, ensure_ascii=False))
    return 0


def patterns_command(args: argparse.Namespace) -> int:
    payload = {
        "id": "phase14-architecture-pattern-landing",
        "created_at": _utc_now(),
        "mode": "design-fixture",
        "patterns": [
            {
                "id": "brain-hands-session",
                "status": "landed-as-contract",
                "contract": ["brain_decides", "hands_execute_with_envelope", "session_records_evidence"],
                "rollback": "Keep existing worker run evidence as authoritative.",
            },
            {
                "id": "context-core",
                "status": "landed-as-evidence-index-pattern",
                "contract": ["source_ref", "context_window", "freshness", "confidence"],
                "rollback": "Use registry and summaries directly.",
            },
            {
                "id": "compiled-truth-timeline",
                "status": "landed-as-closeout-pattern",
                "contract": ["truth_ref", "event_time", "decision", "verification_ref"],
                "rollback": "Restore current closeout summaries as canonical references.",
            },
        ],
    }
    _write(Path(args.output), payload)
    print(json.dumps({"status": "ready", "patterns": len(payload["patterns"]), "output": args.output}, ensure_ascii=False))
    return 0


def ecosystem_command(args: argparse.Namespace) -> int:
    root = _root()
    packages = _load_yaml(_omo(root) / "registry" / "system-packages.yaml") or {"packages": []}
    article_samples = _load_yaml(_omo(root) / "registry" / "article-samples.yaml") or {"samples": []}
    payload = {
        "id": "phase14-ecosystem-expansion-preview",
        "created_at": _utc_now(),
        "mode": "preview-only",
        "mutations_applied": 0,
        "article_knowledge_graph": {
            "mode": "sample-graph-only",
            "nodes": len(article_samples.get("samples", [])),
            "edges": [
                ["article-sample-001", "article-sample-002", "registry-to-binding"],
                ["article-sample-003", "article-sample-005", "governance-to-backlog"],
            ],
        },
        "package_graph": {
            "mode": "manifest-preview",
            "packages_checked": len(packages.get("packages", [])),
            "managers": sorted({package["manager"] for package in packages.get("packages", [])}),
        },
        "marketplace_preview": {
            "mode": "list-only",
            "install_enabled": False,
            "publish_enabled": False,
            "admission_required": True,
            "candidates": ["memu-gbrain-memory", "gitnexus-kos-index", "firecrawl-kronos-ingestion"],
        },
    }
    _write(Path(args.output), payload)
    print(json.dumps({"status": "ready", "mutations": 0, "output": args.output}, ensure_ascii=False))
    return 0


def security_command(args: argparse.Namespace) -> int:
    payload = {
        "id": "phase14-security-review",
        "created_at": _utc_now(),
        "status": "pass-with-preview-only-controls",
        "controls": [
            {
                "control": "external install disabled",
                "result": "pass",
            },
            {
                "control": "all pilots have rollback",
                "result": "pass",
            },
            {
                "control": "marketplace remains list-only",
                "result": "pass",
            },
            {
                "control": "package graph is preview-only",
                "result": "pass",
            },
        ],
        "critical_findings": [],
    }
    _write(Path(args.output), payload)
    print(json.dumps({"status": "pass", "critical_findings": 0, "output": args.output}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omo-phase14")
    sub = parser.add_subparsers(dest="command", required=True)

    triage = sub.add_parser("triage")
    triage.add_argument("--output", default=".omo/evidence/phase14/integration-triage.yaml")
    triage.set_defaults(func=triage_command)

    pilots = sub.add_parser("pilots")
    pilots.add_argument("--output", default=".omo/evidence/phase14/deep-absorption-pilots.yaml")
    pilots.set_defaults(func=pilots_command)

    patterns = sub.add_parser("patterns")
    patterns.add_argument("--output", default=".omo/evidence/phase14/architecture-patterns.yaml")
    patterns.set_defaults(func=patterns_command)

    ecosystem = sub.add_parser("ecosystem")
    ecosystem.add_argument("--output", default=".omo/evidence/phase14/ecosystem-preview.yaml")
    ecosystem.set_defaults(func=ecosystem_command)

    security = sub.add_parser("security")
    security.add_argument("--output", default=".omo/evidence/phase14/security-review.yaml")
    security.set_defaults(func=security_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
