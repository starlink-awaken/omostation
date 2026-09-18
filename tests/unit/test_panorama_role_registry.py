import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_role_registry_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record(role_id: str, state: str = "admitted", *, digest: str | None = None) -> dict:
    body = {
        "schema": "omo-role-registry/v1",
        "role_id": role_id,
        "capabilities": ["semantic.plan"],
        "admission_state": state,
        "version": 2,
        "updated_at": "2026-09-17T00:00:00+00:00",
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    data = dict(body)
    data["digest"] = digest or ("sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest())
    return data


def test_collect_role_registry_projects_valid_runtime_state(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    store = tmp_path / ".omo/state/agent-cell/semantic/roles.jsonl"
    store.parent.mkdir(parents=True)
    roles = [_record("role:beta"), _record("role:alpha", "pending")]
    store.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in roles), encoding="utf-8")

    report = module.collect_role_registry()

    assert report["schema"] == "panorama-role-registry/v1"
    assert report["available"] is True
    assert report["verdict"] == "PASS"
    assert report["total"] == 2
    assert report["by_state"] == {"pending": 1, "admitted": 1}
    assert [item["role_id"] for item in report["records"]] == ["role:alpha", "role:beta"]
    assert all(item["intact"] for item in report["records"])


def test_collect_role_registry_fail_closed_on_tampered_record(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    store = tmp_path / ".omo/state/agent-cell/semantic/roles.jsonl"
    store.parent.mkdir(parents=True)
    tampered = _record("role:alpha", digest="sha256:invalid")
    store.write_text(json.dumps(tampered, ensure_ascii=False) + "\n", encoding="utf-8")

    report = module.collect_role_registry()

    assert report["verdict"] == "DEGRADED"
    assert report["total"] == 0
    assert report["integrity_ok"] is False
    assert report["errors"] == ["line:1:digest-mismatch:role:alpha"]


def test_collect_role_registry_reports_missing_store(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)

    report = module.collect_role_registry()

    assert report["available"] is False
    assert report["verdict"] == "UNAVAILABLE"
    assert report["errors"] == ["registry_file_missing"]
