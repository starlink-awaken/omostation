from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-domain-owner-job.py"


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    documents = tmp_path / "Documents"
    creative = documents / "@创意创作"
    registry_dir = documents / "@公共" / "_control"
    creative.mkdir(parents=True)
    registry_dir.mkdir(parents=True)
    manifest = creative / "DOMAIN.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "l4/v1",
                "kind": "DomainManifest",
                "id": "creative",
                "display_name": "@创意创作",
                "archetype": "operational",
                "space_ref": "personal-space",
                "root": ".",
                "owners": ["personal-space-owner"],
                "principal_ref": "personal-space-owner",
                "default_sensitivity": "private",
                "default_visibility": "private",
                "sharing_policy": "explicit_publish",
                "retention": "permanent",
                "authority_policy": "canonical_write",
                "harness_profile_ref": "harness://operational/v1",
                "lifecycle": "active",
                "policy_refs": [],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    registry = registry_dir / "L4-DOMAIN-REGISTRY.yaml"
    registry.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "l4/v1",
                "kind": "DomainRegistry",
                "id": "test-domains",
                "display_name": "Test domains",
                "space_ref": "personal-space",
                "status": "active",
                "path_base": "registry_file_parent",
                "manifests": [
                    {"id": "creative", "path": os.path.relpath(manifest, registry_dir)}
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    project = tmp_path / "documents-domain-projects.yaml"
    project.write_text(
        yaml.safe_dump(
            {
                "domain_registry": {
                    "documents_relative_ref": "@公共/_control/L4-DOMAIN-REGISTRY.yaml"
                },
                "runtime_jobs": [
                    {
                        "id": "creative-manifest-check",
                        "domain_id": "creative",
                        "owner": "l4-kernel",
                        "action": "validate_manifest",
                        "schedule": "manual",
                        "timeout_seconds": 10,
                        "reads": ["domain_registry", "registered_manifests"],
                        "writes": [],
                        "evidence_path": "manifest-validation.json",
                        "fail_closed": True,
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return documents, registry, project, tmp_path / "state"


def _run(
    documents: Path,
    registry: Path,
    project: Path,
    state: Path,
    owner: Path,
    *extra: str,
    job_id: str = "creative-manifest-check",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            job_id,
            "--documents-root",
            str(documents),
            "--domain-registry",
            str(registry),
            "--project-registry",
            str(project),
            "--state-root",
            str(state),
            "--l4-executable",
            str(owner),
            "--json",
            *extra,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _owner(tmp_path: Path, exit_code: int = 0) -> Path:
    path = tmp_path / f"l4-owner-{exit_code}"
    path.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' '{{\"ok\": {str(exit_code == 0).lower()}}}'\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root)).encode("utf-8")
        digest.update(relative)
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_owner_job_dry_run_resolves_binding_without_writes(tmp_path: Path) -> None:
    documents, registry, project, state = _fixture(tmp_path)
    missing_owner = tmp_path / "not-executed"

    result = _run(
        documents,
        registry,
        project,
        state,
        missing_owner,
        "--dry-run",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "dry_run"
    assert not state.exists()


def test_owner_job_rejects_facts_audit_binding_before_execution(tmp_path: Path) -> None:
    documents, registry, project, state = _fixture(tmp_path)
    facts_root = documents / "@工作文档" / "卫健委"
    facts_root.mkdir(parents=True)
    facts_manifest = facts_root / "DOMAIN.yaml"
    manifest_payload = yaml.safe_load(
        (documents / "@创意创作" / "DOMAIN.yaml").read_text(encoding="utf-8")
    )
    manifest_payload.update({"id": "work-weijian", "display_name": "@工作文档/卫健委"})
    facts_manifest.write_text(
        yaml.safe_dump(manifest_payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    registry_payload = yaml.safe_load(registry.read_text(encoding="utf-8"))
    registry_payload["manifests"].append(
        {
            "id": "work-weijian",
            "path": os.path.relpath(facts_manifest, registry.parent),
        }
    )
    registry.write_text(
        yaml.safe_dump(registry_payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    raw = yaml.safe_load(project.read_text(encoding="utf-8"))
    raw["runtime_jobs"].append(
        {
            "id": "documents-weijian-facts-audit",
            "domain_id": "work-weijian",
            "owner": "runtime-facts",
            "action": "audit_structured_facts",
            "schedule": "manual",
            "timeout_seconds": 60,
            "reads": ["@工作文档/卫健委/_entities/facts"],
            "writes": [],
            "evidence_relative_path": "control/evidence/documents-weijian-facts-audit/documents-weijian-facts-audit.json",
            "evidence_schema": "runtime.documents-facts-audit.evidence.v1",
            "fail_closed": True,
        }
    )
    project.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = _run(
        documents,
        registry,
        project,
        state,
        tmp_path / "not-executed",
        "--dry-run",
        job_id="documents-weijian-facts-audit",
    )

    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "status": "failed",
        "error": "runtime job is not a manifest validation job: documents-weijian-facts-audit",
    }
    assert not state.exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="Runtime isolation is macOS-only")
def test_owner_job_succeeds_repeats_and_never_writes_documents(tmp_path: Path) -> None:
    documents, registry, project, state = _fixture(tmp_path)
    owner = _owner(tmp_path)
    before = _tree_digest(documents)

    first = _run(documents, registry, project, state, owner)
    second = _run(documents, registry, project, state, owner)

    assert first.returncode == second.returncode == 0
    assert json.loads(first.stdout)["status"] == "succeeded"
    second_payload = json.loads(second.stdout)
    assert second_payload["status"] == "succeeded"
    evidence = Path(second_payload["evidence_path"])
    assert evidence.is_relative_to(state)
    assert json.loads(evidence.read_text(encoding="utf-8"))["status"] == "succeeded"
    assert _tree_digest(documents) == before


@pytest.mark.skipif(sys.platform != "darwin", reason="Runtime isolation is macOS-only")
def test_owner_job_preserves_nonzero_owner_result_and_receipt(tmp_path: Path) -> None:
    documents, registry, project, state = _fixture(tmp_path)
    owner = _owner(tmp_path, exit_code=7)
    before = _tree_digest(documents)

    result = _run(documents, registry, project, state, owner)

    assert result.returncode == 7
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["exit_code"] == 7
    assert (
        json.loads(Path(payload["evidence_path"]).read_text(encoding="utf-8"))[
            "exit_code"
        ]
        == 7
    )
    assert _tree_digest(documents) == before
