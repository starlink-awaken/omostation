from __future__ import annotations

import subprocess
import sys
from os.path import relpath
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-domain-index.py"


def _manifest(root: Path, domain_id: str, display_name: str) -> Path:
    root.mkdir(parents=True)
    manifest = root / "DOMAIN.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "l4/v1",
                "kind": "DomainManifest",
                "id": domain_id,
                "display_name": display_name,
                "archetype": "operational",
                "space_ref": "personal-space",
                "root": ".",
                "owners": ["personal-space-owner"],
                "principal_ref": "personal-space-owner",
                "default_sensitivity": "private",
                "default_visibility": "private",
                "sharing_policy": "deny",
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
    return manifest


def _registry(tmp_path: Path) -> Path:
    control = tmp_path / "Documents" / "@公共" / "_control"
    control.mkdir(parents=True)
    alpha = _manifest(tmp_path / "Documents" / "alpha", "alpha", "Alpha")
    beta = _manifest(tmp_path / "Documents" / "beta", "beta", "Beta")
    registry = control / "L4-DOMAIN-REGISTRY.yaml"
    registry.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "l4/v1",
                "kind": "DomainRegistry",
                "id": "documents-test",
                "display_name": "Documents test",
                "space_ref": "personal-space",
                "status": "active",
                "path_base": "registry_file_parent",
                "manifests": [
                    {"id": "alpha", "path": relpath(alpha, control)},
                    {"id": "beta", "path": relpath(beta, control)},
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return registry


def _run(registry: Path, index: Path, command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            command,
            "--domain-registry",
            str(registry),
            "--index-path",
            str(index),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_check_fails_when_index_is_not_the_current_registry_projection(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    index = tmp_path / "DOMAIN-INDEX.md"
    index.write_text(
        "# Documents domain index\n\n<!-- AUTOGEN:L4-DOMAIN-MANIFESTS BEGIN -->\n"
        "| ID | 名称 | Archetype | Authority | 路径 |\n|---|---|---|---|---|\n"
        "| stale | Stale | operational | canonical_write | /tmp/stale |\n"
        "<!-- AUTOGEN:L4-DOMAIN-MANIFESTS END -->\n",
        encoding="utf-8",
    )

    result = _run(registry, index, "check")

    assert result.returncode == 1
    assert "DOMAIN-INDEX projection drift" in result.stderr


def test_write_and_check_project_only_validated_manifests(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    index = tmp_path / "DOMAIN-INDEX.md"
    index.write_text(
        "# Documents domain index\n\n<!-- AUTOGEN:L4-DOMAIN-MANIFESTS BEGIN -->\n"
        "<!-- AUTOGEN:L4-DOMAIN-MANIFESTS END -->\n",
        encoding="utf-8",
    )

    write = _run(registry, index, "write")
    check = _run(registry, index, "check")

    assert write.returncode == 0, write.stderr
    assert check.returncode == 0, check.stderr
    rendered = index.read_text(encoding="utf-8")
    assert "## 2 个已验证 Documents 域" in rendered
    assert "| alpha | Alpha | operational | canonical_write |" in rendered
    assert "| beta | Beta | operational | canonical_write |" in rendered
    assert "stale" not in rendered


def test_write_migrates_the_legacy_generated_block(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    index = tmp_path / "DOMAIN-INDEX.md"
    index.write_text(
        "# Documents domain index\n\n> old source: registry.py\n\n"
        "<!-- AUTOGEN:DOMAIN-TABLES BEGIN (domain-sync.py --write · 勿手改) -->\n"
        "legacy projection\n"
        "<!-- AUTOGEN:DOMAIN-TABLES END -->\n",
        encoding="utf-8",
    )

    write = _run(registry, index, "write")

    assert write.returncode == 0, write.stderr
    rendered = index.read_text(encoding="utf-8")
    assert "<!-- AUTOGEN:L4-DOMAIN-MANIFESTS BEGIN -->" in rendered
    assert "AUTOGEN:DOMAIN-TABLES" not in rendered
    assert "old source: registry.py" not in rendered
    assert "Manifest Registry" in rendered


def test_required_phase_gate_covers_registry_index_projection() -> None:
    workflow = (ROOT / ".github" / "workflows" / "phase-gate-enforce.yml").read_text(
        encoding="utf-8"
    )

    assert "bin/gac/documents-domain-index.py" in workflow
    assert "tests/test_documents_domain_index.py" in workflow
