"""Documents content-plane migration registry coverage tests."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-content-plane-migration-check.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "documents_content_plane_migration_check", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _family(family_id: str, pattern: str, sample: str) -> dict:
    return {
        "id": family_id,
        "source_globs": [pattern],
        "artifact_kind": ["runtime", "cache"],
        "disposition": "migrate",
        "owner": "runtime",
        "replacement": f"workspace://{family_id}",
        "consumer_refs": ["consumer://example"],
        "rollback": "Keep the source until target verification passes.",
        "confirmation_gate": "before_write",
        "status": "pending",
        "major_surface": family_id == "one",
        "sample": sample,
    }


def _write_registry(path: Path, families: list[dict] | None = None) -> Path:
    families = families or [
        _family("one", "one/**", "one/a.py"),
        _family("two", "two/**", "two/b.sqlite"),
    ]
    payload = {
        "apiVersion": "workspace.omostation/v1",
        "kind": "DocumentsContentPlaneMigrations",
        "id": "documents-content-plane-migrations",
        "owner": "governance-team",
        "candidate_kinds": ["runtime", "cache"],
        "major_surfaces": [
            item["id"] for item in families if item.get("major_surface")
        ],
        "coverage_samples": [
            {
                "relative_path": item.pop("sample"),
                "kind": "runtime",
                "family": item["id"],
            }
            for item in families
        ],
        "families": families,
    }
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return path


def test_samples_prove_each_family_has_one_non_overlapping_match(tmp_path):
    module = _load_module()
    registry = _write_registry(tmp_path / "registry.yaml")

    report = module.check_migrations(registry)

    assert report["ok"] is True
    assert report["mode"] == "samples"
    assert report["candidate_count"] == 2
    assert report["family_counts"] == {"one": 1, "two": 1}


def test_workspace_registry_samples_pass():
    module = _load_module()
    registry = (
        ROOT
        / ".omo"
        / "_truth"
        / "registry"
        / "documents-content-plane-migrations.yaml"
    )

    report = module.check_migrations(registry)

    assert report["ok"] is True
    assert report["candidate_count"] == 15
    assert set(report["family_counts"]) == {
        "family-dashboard-app",
        "toolbox-staging",
        "career-code-archives",
        "zotero-app-data",
        "family-content-archives",
        "family-runtime-kems",
        "learning-content-archives",
        "learning-runtime",
        "work-content-archives",
        "work-runtime",
        "public-runtime",
        "cockpit-runtime",
        "opc-tools",
        "creative-content-archives",
        "root-oneoff-assets",
    }


def test_zero_match_fails_closed(tmp_path):
    module = _load_module()
    registry = _write_registry(tmp_path / "registry.yaml")

    report = module.check_migrations(
        registry,
        candidates=[{"relative_path": "three/orphan.py", "kind": "runtime"}],
    )

    assert report["ok"] is False
    assert any("zero matches" in error for error in report["errors"])


def test_multiple_matches_fail_closed(tmp_path):
    module = _load_module()
    families = [
        _family("one", "shared/**", "shared/one.py"),
        _family("two", "shared/**", "shared/two.py"),
    ]
    registry = _write_registry(tmp_path / "registry.yaml", families)

    report = module.check_migrations(
        registry,
        candidates=[{"relative_path": "shared/runtime.py", "kind": "runtime"}],
    )

    assert report["ok"] is False
    assert any("multiple matches" in error for error in report["errors"])


def test_owner_and_replacement_are_required(tmp_path):
    module = _load_module()
    families = [_family("one", "one/**", "one/a.py")]
    families[0]["owner"] = ""
    families[0]["replacement"] = ""
    registry = _write_registry(tmp_path / "registry.yaml", families)

    report = module.check_migrations(registry)

    assert report["ok"] is False
    assert any("owner must be non-empty" in error for error in report["errors"])
    assert any("replacement must be non-empty" in error for error in report["errors"])


def test_illegal_or_unproven_completion_status_fails(tmp_path):
    module = _load_module()
    families = [
        _family("one", "one/**", "one/a.py"),
        _family("two", "two/**", "two/b.py"),
        _family("three", "three/**", "three/c.py"),
    ]
    families[0]["status"] = "done"
    families[1]["status"] = "retired"
    families[2]["status"] = "verified"
    families[2]["evidence"] = {field: "" for field in module._EVIDENCE_FIELDS}
    registry = _write_registry(tmp_path / "registry.yaml", families)

    report = module.check_migrations(registry)

    assert report["ok"] is False
    assert any("unsupported status: done" in error for error in report["errors"])
    assert (
        sum("terminal status requires evidence" in error for error in report["errors"])
        == 2
    )


def test_live_candidates_report_kind_and_family_counts(tmp_path):
    module = _load_module()
    registry = _write_registry(tmp_path / "registry.yaml")

    report = module.check_migrations(
        registry,
        candidates=[
            {"relative_path": "one/job.py", "kind": "runtime"},
            {"relative_path": "two/cache.sqlite", "kind": "cache"},
        ],
    )

    assert report["ok"] is True
    assert report["mode"] == "live"
    assert report["kind_counts"] == {"cache": 1, "runtime": 1}


def test_nonempty_documents_root_cannot_succeed_with_zero_audited_artifacts(
    tmp_path, monkeypatch, capsys
):
    module = _load_module()
    registry = _write_registry(tmp_path / "registry.yaml")
    documents_root = tmp_path / "Documents"
    documents_root.mkdir()
    (documents_root / "note.md").write_text("content", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "_audit_candidates",
        lambda _root: ([], {"artifact_count": 0, "counts": {}}),
    )

    rc = module.main(
        [
            "--registry",
            str(registry),
            "--documents-root",
            str(documents_root),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["ok"] is False
    assert any("audit returned zero artifacts" in error for error in payload["errors"])


def test_nonterminal_families_cannot_succeed_when_live_candidates_vanish(
    tmp_path, monkeypatch, capsys
):
    module = _load_module()
    registry = _write_registry(tmp_path / "registry.yaml")
    documents_root = tmp_path / "Documents"
    documents_root.mkdir()
    (documents_root / "note.md").write_text("content", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "_audit_candidates",
        lambda _root: (
            [],
            {"artifact_count": 1, "counts": {"content": 1}},
        ),
    )

    rc = module.main(
        [
            "--registry",
            str(registry),
            "--documents-root",
            str(documents_root),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["ok"] is False
    assert any(
        "zero migration candidates while non-terminal families remain" in error
        for error in payload["errors"]
    )
