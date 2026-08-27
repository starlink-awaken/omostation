from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-domain-owner-job.py"


def _documents(tmp_path: Path, *, state_date: str = "2026-08-20", review_date: str = "2026-08-20") -> Path:
    documents = tmp_path / "Documents"
    shared = documents / "@公共" / "_control"
    domain = documents / "@个人" / "_control"
    shared.mkdir(parents=True)
    domain.mkdir(parents=True)
    (shared / "L4-DOMAIN-REGISTRY.yaml").write_text(
        yaml.safe_dump(
            {
                "apiVersion": "l4/v1",
                "kind": "DomainRegistry",
                "manifests": [
                    {"id": "shared", "path": "../DOMAIN.yaml"},
                    {"id": "personal", "path": "../../@个人/DOMAIN.yaml"},
                ],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (documents / "@公共" / "DOMAIN.yaml").write_text("id: shared\n", encoding="utf-8")
    (documents / "@个人" / "DOMAIN.yaml").write_text("id: personal\n", encoding="utf-8")
    (documents / "@公共" / "CLAUDE.md").write_text(f"下次审查：{review_date}\n", encoding="utf-8")
    (documents / "@个人" / "CLAUDE.md").write_text(f"下次审查：{review_date}\n", encoding="utf-8")
    (shared / "STATE.md").write_text(f"last-reviewed: {state_date}\n", encoding="utf-8")
    (domain / "STATE.md").write_text(f"last-reviewed: {state_date}\n", encoding="utf-8")
    return documents


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "freshness-audit", *args, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_healthy_audit_returns_zero_and_stable_domain_order(tmp_path: Path) -> None:
    documents = _documents(tmp_path, state_date="2026-08-27", review_date="2026-08-27")

    result = _run("--documents-root", str(documents), "--today", "2026-08-27")

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["schema"] == "documents.freshness-audit.v1"
    assert payload["status"] == "ok"
    assert [item["domain_id"] for item in payload["domains"]] == ["personal", "shared"]
    assert all(set(item) == {"claude_review", "domain_id", "state_reviewed", "status", "claude_age_days", "state_age_days"} for item in payload["domains"])


def test_stale_and_invalid_findings_return_one_without_content_leak(tmp_path: Path) -> None:
    documents = _documents(tmp_path, state_date="not-a-date", review_date="2026-08-01")
    (documents / "@个人" / "_control" / "STATE.md").write_text("last-reviewed: 2026-08-01\n", encoding="utf-8")

    result = _run("--documents-root", str(documents), "--today", "2026-08-27")

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["status"] == "findings"
    assert {item["status"] for item in payload["domains"]} == {"invalid", "stale"}
    assert "not-a-date" not in result.stdout
    assert "last-reviewed" not in result.stdout


def test_invalid_registry_path_returns_two_and_does_not_write_documents(tmp_path: Path) -> None:
    documents = _documents(tmp_path)
    registry = documents / "@公共" / "_control" / "L4-DOMAIN-REGISTRY.yaml"
    before = registry.read_bytes()
    before_mtime = registry.stat().st_mtime_ns
    registry.write_text("apiVersion: l4/v1\nmanifests:\n  - id: bad\n    path: ../../../outside/DOMAIN.yaml\n", encoding="utf-8")
    changed = registry.read_bytes()
    changed_mtime = registry.stat().st_mtime_ns

    result = _run("--documents-root", str(documents), "--today", "2026-08-27")

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["status"] == "unavailable"
    assert changed != before
    assert changed_mtime >= before_mtime


def test_evidence_is_workspace_only_and_documents_bytes_remain_unchanged(tmp_path: Path) -> None:
    documents = _documents(tmp_path, state_date="2026-08-27", review_date="2026-08-27")
    workspace = tmp_path / "workspace"
    evidence = workspace / "evidence" / "freshness.json"
    snapshot = {
        path.relative_to(documents).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in documents.rglob("*")
        if path.is_file()
    }

    result = _run(
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(workspace),
        "--evidence",
        str(evidence),
        "--today",
        "2026-08-27",
    )

    assert result.returncode == 0
    assert evidence.is_file()
    assert json.loads(evidence.read_text(encoding="utf-8"))["schema"] == "documents.freshness-audit.v1"
    assert snapshot == {
        path.relative_to(documents).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in documents.rglob("*")
        if path.is_file()
    }
    assert not os.path.commonpath((documents, evidence)).startswith(str(documents))
