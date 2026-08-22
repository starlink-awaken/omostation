#!/usr/bin/env python3
"""validate-human-gate.py — 校验 human gate 证据来源."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]

PROHIBITED_SOURCES = {
    "merge_event",
    "issue_comment_automation",
    "ci_pass",
    "automated_workflow",
}


def extract_evidence_refs(scene_card_path: Path) -> list[str]:
    docs = list(yaml.safe_load_all(scene_card_path.read_text(encoding="utf-8")))
    refs: list[str] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        evidence = doc.get("evidence_refs", [])
        if isinstance(evidence, list):
            refs.extend(str(item) for item in evidence)
        notes = doc.get("notes", [])
        if isinstance(notes, list):
            for note in notes:
                refs.append(str(note))
        description = str(doc.get("description", ""))
        refs.append(description)
    return refs


def validate_human_gate(scene_card_path: Path) -> dict:
    refs = extract_evidence_refs(scene_card_path)
    prohibited = []
    for ref in refs:
        for source in PROHIBITED_SOURCES:
            if source in ref.lower():
                prohibited.append({"source": source, "ref": ref[:200]})
    return {
        "scene_card": str(scene_card_path),
        "prohibited_count": len(prohibited),
        "prohibited_sources": prohibited,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate human gate evidence sources")
    parser.add_argument("--scene-card", type=Path, required=True)
    args = parser.parse_args(argv)
    report = validate_human_gate(args.scene_card)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["prohibited_count"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
