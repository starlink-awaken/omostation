from __future__ import annotations

from types import SimpleNamespace

import yaml
from omo import omo_capability, omo_phase14


def test_load_capability_registry_prefers_new_path_and_falls_back_to_legacy(tmp_path):
    new_dir = tmp_path / ".omo" / "capabilities"
    legacy_dir = tmp_path / ".omo" / "registry"
    new_dir.mkdir(parents=True, exist_ok=True)
    legacy_dir.mkdir(parents=True, exist_ok=True)

    (legacy_dir / "projects-capabilities.yaml").write_text(
        yaml.safe_dump({"capabilities": [{"id": "legacy-only"}]}, sort_keys=False),
        encoding="utf-8",
    )
    assert omo_capability.load_capability_registry(
        tmp_path, "projects-capabilities.yaml"
    ) == {"capabilities": [{"id": "legacy-only"}]}

    (new_dir / "projects-capabilities.yaml").write_text(
        yaml.safe_dump({"capabilities": [{"id": "new-primary"}]}, sort_keys=False),
        encoding="utf-8",
    )
    assert omo_capability.load_capability_registry(
        tmp_path, "projects-capabilities.yaml"
    ) == {"capabilities": [{"id": "new-primary"}]}


def test_load_capability_registry_accepts_multi_document_yaml(tmp_path):
    new_dir = tmp_path / ".omo" / "capabilities"
    new_dir.mkdir(parents=True, exist_ok=True)
    (new_dir / "projects-capabilities.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "capabilities:\n"
        "  - id: multi-primary\n",
        encoding="utf-8",
    )

    payload = omo_capability.load_capability_registry(
        tmp_path, "projects-capabilities.yaml"
    )

    assert payload["status"] == "active"
    assert payload["capabilities"] == [{"id": "multi-primary"}]


def test_scan_command_writes_capability_registry_into_capabilities_dir(
    tmp_path, monkeypatch
):
    (tmp_path / "projects" / "kairon" / "packages" / "alpha").mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "omo").write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(omo_capability, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(omo_capability, "OMO_ROOT", tmp_path / ".omo")
    monkeypatch.setattr(
        omo_capability, "CAPABILITIES_DIR", tmp_path / ".omo" / "capabilities"
    )

    rc = omo_capability.scan_command(SimpleNamespace(write=True))  # type: ignore[reportArgumentType]

    assert rc == 0
    assert (tmp_path / ".omo" / "capabilities" / "projects-capabilities.yaml").exists()
    assert (tmp_path / ".omo" / "capabilities" / "system-packages.yaml").exists()
    assert (tmp_path / ".omo" / "capabilities" / "agent-clis.yaml").exists()
    assert not (tmp_path / ".omo" / "registry" / "projects-capabilities.yaml").exists()
    bundle_artifacts = list(
        (tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "capabilities").glob(
            "bundle-*.yaml"
        )
    )
    assert len(bundle_artifacts) == 1
    payload = yaml.safe_load(bundle_artifacts[0].read_text(encoding="utf-8"))
    assert payload["kind"] == "capability_registry_bundle_written"
    assert ".omo/capabilities/projects-capabilities.yaml" in payload["registry_refs"]
    assert payload["actor"] == "omo-capability capability scan"
    ingress_registry = yaml.safe_load(
        (
            tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "registry.yaml"
        ).read_text(encoding="utf-8")
    )
    assert (
        ingress_registry["capabilities"]["by_id"]["bundle"]["source_ref"]
        == "omo-capability:scan"
    )


def test_register_command_writes_manual_capabilities_via_ingress_artifact(
    tmp_path, monkeypatch
):
    capabilities_dir = tmp_path / ".omo" / "capabilities"
    capabilities_dir.mkdir(parents=True, exist_ok=True)
    payload_file = tmp_path / "capability.yaml"
    payload_file.write_text(
        yaml.safe_dump(
            {
                "id": "manual.demo",
                "type": "tool",
                "protocol": "cli",
                "entrypoint": "bin/demo",
                "lifecycle": "active",
                "metadata": {
                    "description": "manual demo",
                    "version": "local",
                    "tags": ["demo"],
                    "scenario_tags": ["demo"],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(omo_capability, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(omo_capability, "OMO_ROOT", tmp_path / ".omo")
    monkeypatch.setattr(omo_capability, "CAPABILITIES_DIR", capabilities_dir)

    rc = omo_capability.register_command(SimpleNamespace(file=str(payload_file)))  # type: ignore[reportArgumentType]

    assert rc == 0
    manual_registry = yaml.safe_load(
        (capabilities_dir / "manual-capabilities.yaml").read_text(encoding="utf-8")
    )
    assert manual_registry["capabilities"][0]["id"] == "manual.demo"
    artifacts = list(
        (tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "capabilities").glob(
            "manual-capabilities-*.yaml"
        )
    )
    assert len(artifacts) == 1
    artifact_payload = yaml.safe_load(artifacts[0].read_text(encoding="utf-8"))
    assert artifact_payload["kind"] == "manual_capabilities_written"
    assert (
        artifact_payload["registry_ref"] == ".omo/capabilities/manual-capabilities.yaml"
    )
    ingress_registry = yaml.safe_load(
        (
            tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "registry.yaml"
        ).read_text(encoding="utf-8")
    )
    assert (
        ingress_registry["capabilities"]["by_id"]["manual-capabilities"]["source_ref"]
        == "omo-capability:register:capability.yaml"
    )


def test_phase14_ecosystem_command_reads_new_capability_registry(tmp_path, monkeypatch):
    capabilities_dir = tmp_path / ".omo" / "capabilities"
    capabilities_dir.mkdir(parents=True, exist_ok=True)
    (capabilities_dir / "system-packages.yaml").write_text(
        yaml.safe_dump(
            {
                "packages": [
                    {
                        "id": "pkg-a",
                        "manager": "uv",
                        "manifest": "projects/demo/pyproject.toml",
                    },
                    {"id": "pkg-b", "manager": "brew", "manifest": "Brewfile"},
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (capabilities_dir / "article-samples.yaml").write_text(
        yaml.safe_dump(
            {"samples": [{"id": "article-1"}, {"id": "article-2"}]}, sort_keys=False
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(omo_capability, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(omo_capability, "OMO_ROOT", tmp_path / ".omo")
    monkeypatch.setattr(omo_capability, "CAPABILITIES_DIR", capabilities_dir)
    monkeypatch.setattr(omo_phase14, "WORKSPACE_ROOT", tmp_path)

    output = tmp_path / "ecosystem.yaml"
    rc = omo_phase14.ecosystem_command(SimpleNamespace(output=str(output)))  # type: ignore[reportArgumentType]

    assert rc == 0
    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert payload["package_graph"]["packages_checked"] == 2
    assert payload["package_graph"]["managers"] == ["brew", "uv"]
    assert payload["article_knowledge_graph"]["nodes"] == 2
