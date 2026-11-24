"""Tests for bos-uri-verify manual on-demand HTTP capability handling."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "ssot" / "bos-uri-verify.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("bos_uri_verify", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_load_manual_disabled_uris_parses_multidoc_yaml(tmp_path: Path) -> None:
    mod = _load_module()
    reg = tmp_path / "services.yaml"
    reg.write_text(
        "status: active\n"
        "lifecycle: ssot\n"
        "---\n"
        "services:\n"
        "- id: bos.memory.kems.status\n"
        "  enabled: false\n"
        "  scheduler: manual\n"
        "  trigger: on_demand\n"
        "  uri: bos://memory/kems/status\n"
        "- id: bos.active.daemon\n"
        "  enabled: true\n"
        "  scheduler: launchd\n"
        "  uri: bos://memory/active/daemon\n"
        "- id: bos.manual.enabled\n"
        "  enabled: true\n"
        "  scheduler: manual\n"
        "  uri: bos://memory/manual/enabled\n"
        "- id: bos.disabled.daemon\n"
        "  enabled: false\n"
        "  scheduler: launchd\n"
        "  uri: bos://memory/disabled/daemon\n",
        encoding="utf-8",
    )

    got = mod.load_manual_disabled_uris(reg)
    assert got == {"bos://memory/kems/status"}


def test_verify_all_skips_manual_disabled_http_but_probes_active_http(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mod = _load_module()
    reg = tmp_path / "services.yaml"
    reg.write_text(
        "status: active\n"
        "---\n"
        "services:\n"
        "- id: bos.memory.kems.status\n"
        "  enabled: false\n"
        "  scheduler: manual\n"
        "  trigger: on_demand\n"
        "  uri: bos://memory/kems/status\n"
        "- id: bos.nonhttp.manual\n"
        "  enabled: false\n"
        "  scheduler: manual\n"
        "  trigger: on_demand\n"
        "  uri: bos://tools/inline/helper\n",
        encoding="utf-8",
    )
    bos_services = [
        {
            "uri": "bos://memory/kems/status",
            "transport": "http",
            "status": "active",
            "http_url": "http://localhost:8090/api/kems/status",
        },
        {
            "uri": "bos://memory/active/daemon",
            "transport": "http",
            "status": "active",
            "http_url": "http://localhost:8091/health",
        },
        {
            "uri": "bos://tools/inline/helper",
            "transport": "inline",
            "status": "active",
        },
    ]
    probed_http: list[str] = []
    probed_internal: list[str] = []

    monkeypatch.setattr(mod, "load_bos_services", lambda: bos_services)
    monkeypatch.setattr(
        mod,
        "check_http",
        lambda svc: probed_http.append(svc["uri"]) or {"status": "ok"},
    )
    monkeypatch.setattr(
        mod,
        "check_internal",
        lambda svc: probed_internal.append(svc["uri"]) or {"status": "ok"},
    )

    results = mod.verify_all(services_path=reg)

    assert probed_http == ["bos://memory/active/daemon"]
    assert probed_internal == ["bos://tools/inline/helper"]
    assert results["by_status"] == {
        "ok": 2,
        "external": 0,
        "error": 0,
        "unreachable": 0,
        "skipped": 1,
    }
    by_uri = {d["uri"]: d for d in results["details"]}
    assert by_uri["bos://memory/kems/status"]["status"] == "skipped"
    assert by_uri["bos://memory/active/daemon"]["status"] == "ok"
    assert by_uri["bos://tools/inline/helper"]["status"] == "ok"


def test_real_services_registry_marks_kems_uris_manual_disabled() -> None:
    mod = _load_module()
    manual_uris = mod.load_manual_disabled_uris()
    for expected in (
        "bos://memory/kems/status",
        "bos://memory/kems/graph",
        "bos://memory/kems/ocr-queue",
        "bos://analysis/kems/forecast",
    ):
        assert expected in manual_uris
