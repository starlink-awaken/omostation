"""Tests for the bos_yaml_lint linter that guards the bos-services.yaml registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from agora.mcp.tools.bos_yaml_lint import _lint, _load, main


REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_REGISTRY = REPO_ROOT / "etc" / "bos-services.yaml"


def test_main_lints_default_registry_clean():
    rc = main([str(DEFAULT_REGISTRY)])
    assert rc == 0


def test_load_returns_service_dicts():
    services = _load(DEFAULT_REGISTRY)
    assert services, "registry should not be empty"
    assert all(isinstance(s, dict) for s in services)


def test_lint_flags_duplicate_uri():
    services = _load(DEFAULT_REGISTRY)
    duplicate_uri = services[0]["uri"]
    services.append({**services[0], "uri": duplicate_uri})
    errors = _lint(services)
    assert any("duplicate URI" in e and duplicate_uri in e for e in errors)


def test_lint_flags_missing_required_field():
    services = _load(DEFAULT_REGISTRY)
    broken = dict(services[0])
    broken.pop("description", None)
    errors = _lint(services + [broken])
    assert any("missing 'description'" in e for e in errors)


def test_lint_flags_uri_without_bos_scheme():
    services = _load(DEFAULT_REGISTRY)
    broken = dict(services[0])
    broken["uri"] = "http://invalid"
    errors = _lint([broken])
    assert any("must start with 'bos://'" in e for e in errors)


def test_lint_treats_internal_transport_as_no_command():
    services = _load(DEFAULT_REGISTRY)
    broken = dict(services[0])
    broken["uri"] = "bos://test/internal/noop"
    broken["domain"] = "test"
    broken["action"] = "noop"
    broken["transport"] = "inline"
    broken["command"] = ""
    broken["package"] = "test"
    broken["description"] = "test"
    # No command + inline transport is fine.
    errors = _lint([broken])
    assert not any("missing 'command'" in e for e in errors)


def test_lint_treats_http_transport_as_no_command():
    services = _load(DEFAULT_REGISTRY)
    broken = dict(services[0])
    broken["uri"] = "bos://test/http/noop"
    broken["domain"] = "test"
    broken["action"] = "noop"
    broken["transport"] = "http"
    broken["http_url"] = "http://localhost:8080"
    broken["package"] = "test"
    broken["description"] = "test"
    errors = _lint([broken])
    assert not any("missing 'command'" in e for e in errors)
