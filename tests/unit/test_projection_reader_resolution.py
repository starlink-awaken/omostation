"""Projection path resolution stays aligned with the runtime registry."""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT_MODULE = ROOT / "bin" / "lib" / "repo_root.py"
REGISTRY = ROOT / ".omo" / "_truth" / "registry" / "runtime-projections.yaml"


def _load_repo_root():
    spec = importlib.util.spec_from_file_location("projection_repo_root", REPO_ROOT_MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_projection_registry_is_the_single_source_of_repository_mappings():
    module = _load_repo_root()
    registry_docs = yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8"))
    registry = next(doc["projections"] for doc in registry_docs if isinstance(doc, dict) and "projections" in doc)
    expected = {
        name: (entry["canonical"], entry["legacy"])
        for name, entry in registry.items()
        if "canonical" in entry and "legacy" in entry
    }

    assert module._projection_registry(ROOT) == expected


def test_projection_read_prefers_canonical_then_legacy_and_reports_absent(tmp_path):
    module = _load_repo_root()
    name = "health"
    canonical_rel, legacy_rel = module.projection_rels(name, registry_root=ROOT)
    canonical = tmp_path / canonical_rel
    legacy = tmp_path / legacy_rel
    canonical.parent.mkdir(parents=True)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("canonical", encoding="utf-8")
    legacy.write_text("legacy", encoding="utf-8")

    selected, source = module.projection_read(tmp_path, name, registry_root=ROOT)
    assert (selected, source) == (canonical, "canonical")

    canonical.unlink()
    selected, source = module.projection_read(tmp_path, name, registry_root=ROOT)
    assert (selected, source) == (legacy, "legacy")

    legacy.unlink()
    selected, source = module.projection_read(tmp_path, name, registry_root=ROOT)
    assert (selected, source) == (legacy, "legacy")
    assert not selected.exists()


def test_projection_read_uses_the_audited_workspace_registry(tmp_path):
    module = _load_repo_root()
    custom_root = tmp_path / "workspace"
    registry = custom_root / module.PROJECTIONS_REGISTRY_RELATIVE
    registry.parent.mkdir(parents=True)
    registry.write_text(
        "projections:\n  health:\n    canonical: state/new-health.yaml\n"
        "    legacy: state/old-health.yaml\n",
        encoding="utf-8",
    )

    selected, source = module.projection_read(
        custom_root, "health", registry_root=custom_root
    )
    assert selected == custom_root / "state/old-health.yaml"
    assert source == "legacy"


def test_projection_read_uses_state_root_for_canonical_and_checkout_for_legacy(tmp_path):
    module = _load_repo_root()
    checkout = tmp_path / "checkout"
    runtime = tmp_path / "runtime"
    _write_projection_registry(checkout)
    canonical = runtime / "state/new/health.yaml"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("canonical", encoding="utf-8")

    selected, source = module.projection_read(
        checkout, "health", registry_root=checkout, state_root=runtime
    )
    assert (selected, source) == (canonical, "canonical")

    canonical.unlink()
    legacy = checkout / ".omo/state/health.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("legacy", encoding="utf-8")
    selected, source = module.projection_read(
        checkout, "health", registry_root=checkout, state_root=runtime
    )
    assert (selected, source) == (legacy, "legacy")


def test_missing_projection_registry_uses_packaged_fallback(tmp_path):
    module = _load_repo_root()

    assert module.projection_rels("health", registry_root=tmp_path) == (
        ".omo/state/runtime/health.yaml",
        ".omo/state/health.yaml",
    )


def test_omo_projection_path_resolves_registry_and_legacy_fallback(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "projects/omo/src"))
    omo_paths = importlib.import_module("omo.omo_paths")
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "projections:\n  health:\n"
        "    canonical: .omo/state/runtime/custom-health.yaml\n"
        "    legacy: .omo/state/custom-health.yaml\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(omo_paths, "RUNTIME_PROJECTIONS_REGISTRY", registry)
    monkeypatch.setattr(omo_paths, "STATE_ROOT", tmp_path)
    monkeypatch.setattr(omo_paths, "WORKSPACE_ROOT", tmp_path)

    legacy = tmp_path / ".omo/state/custom-health.yaml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("legacy", encoding="utf-8")
    assert omo_paths.projection_path("health") == legacy

    canonical = tmp_path / ".omo/state/runtime/custom-health.yaml"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("canonical", encoding="utf-8")
    assert omo_paths.projection_path("health") == canonical


def test_omo_projection_path_does_not_fallback_when_registry_omits_name(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "projects/omo/src"))
    omo_paths = importlib.import_module("omo.omo_paths")
    registry = tmp_path / "registry.yaml"
    registry.write_text("projections:\n  other:\n    canonical: a\n    legacy: b\n", encoding="utf-8")
    monkeypatch.setattr(omo_paths, "RUNTIME_PROJECTIONS_REGISTRY", registry)

    with pytest.raises(KeyError, match="Unknown runtime projection: health"):
        omo_paths.projection_path("health")


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_projection_registry(root: Path, *, canonical: str = "state/new/health.yaml"):
    path = root / ".omo/_truth/registry/runtime-projections.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"projections:\n  health:\n    canonical: {canonical}\n"
        "    legacy: .omo/state/health.yaml\n"
        "  system_health:\n"
        "    canonical: .omo/state/runtime/system_health.yaml\n"
        "    legacy: .omo/state/system_health.yaml\n"
        "  governance_data:\n"
        "    canonical: .omo/state/runtime/governance-data.json\n"
        "    legacy: .omo/_control/governance-data.json\n",
        encoding="utf-8",
    )
    return path


def test_health_consumers_use_the_audited_workspace_registry_and_allow_absence(tmp_path, monkeypatch, capsys):
    health_predict = _load_script("health_predict_projection_test", ROOT / "bin/ssot/health-predict.py")
    health_predict.WORKSPACE = tmp_path
    monkeypatch.setattr(health_predict, "runtime_state_root", lambda: tmp_path)
    _write_projection_registry(tmp_path)
    assert health_predict.health_file() == tmp_path / ".omo/state/health.yaml"
    assert health_predict.load_health_snapshot() == {}
    monkeypatch.setattr(health_predict.sys, "argv", [str(ROOT / "bin/ssot/health-predict.py"), "--json"])
    assert health_predict.main() == 0
    assert "投影未生成" in capsys.readouterr().out

    maturity_align = _load_script("maturity_align_projection_test", ROOT / "bin/gac/maturity-align.py")
    monkeypatch.setattr(maturity_align, "runtime_state_root", lambda: tmp_path)
    compass = maturity_align.collect_compass_radar(tmp_path)
    assert compass["projection_source"] == "legacy"
    assert all(compass[field] is None for field in (
        "health_score", "governance_anomaly_score", "freshness_score", "drift_score", "staleness_score"
    ))
    alignment = maturity_align.compute_reconciliation(
        compass,
        {"overall": None},
        {"completion_pct": None},
    )
    assert alignment["reconciliation_score"] is None

    external_runtime = tmp_path.parent / f"{tmp_path.name}-alignment-state"
    external_health = external_runtime / "state/new/health.yaml"
    external_health.parent.mkdir(parents=True)
    external_health.write_text("health_score: 61\n", encoding="utf-8")
    monkeypatch.setattr(maturity_align, "runtime_state_root", lambda: external_runtime)
    assert maturity_align.collect_compass_radar(tmp_path)["health_score"] == 61


def test_unified_health_score_skips_sync_when_health_projection_is_absent(tmp_path, monkeypatch, capsys):
    scorer = _load_script("unified_health_projection_test", ROOT / "bin/gac/unified-health-score.py")
    _write_projection_registry(tmp_path)
    scorer.REPO = tmp_path
    scorer.WORKSPACE = tmp_path
    monkeypatch.setattr(scorer, "runtime_state_root", lambda: tmp_path)
    scorer.HISTORY_FILE = tmp_path / ".omo/state/history/uhs.jsonl"
    system_yaml = tmp_path / ".omo/state/system.yaml"
    system_yaml.parent.mkdir(parents=True)
    original = "health_score: 42\nkeep: true\n"
    system_yaml.write_text(original, encoding="utf-8")

    for name in ("score_tools", "score_governance", "score_scenes", "score_docs", "score_value"):
        monkeypatch.setattr(scorer, name, lambda: 80.0)
    monkeypatch.setattr(scorer.sys, "argv", [str(ROOT / "bin/gac/unified-health-score.py"), "--sync", "--json"])

    scorer.main()
    result = json.loads(capsys.readouterr().out)
    assert result["scores"]["runtime"] is None
    assert result["unscored_axes"] == ["runtime"]
    assert system_yaml.read_text(encoding="utf-8") == original


def test_unified_health_score_reads_canonical_from_separate_state_root(tmp_path, monkeypatch):
    scorer = _load_script("unified_health_external_state_test", ROOT / "bin/gac/unified-health-score.py")
    _write_projection_registry(tmp_path)
    runtime = tmp_path.parent / f"{tmp_path.name}-external-runtime"
    canonical = runtime / "state/new/health.yaml"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("service_online_ratio: 0.6\n", encoding="utf-8")
    scorer.REPO = tmp_path
    monkeypatch.setattr(scorer, "runtime_state_root", lambda: runtime)

    assert scorer.score_runtime() == 60.0


def test_unified_health_sync_targets_separate_state_root(tmp_path, monkeypatch, capsys):
    scorer = _load_script("unified_health_external_sync_test", ROOT / "bin/gac/unified-health-score.py")
    _write_projection_registry(tmp_path)
    runtime = tmp_path.parent / f"{tmp_path.name}-sync-state"
    canonical = runtime / "state/new/health.yaml"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("service_online_ratio: 0.6\n", encoding="utf-8")
    scorer.REPO = tmp_path
    scorer.WORKSPACE = tmp_path
    scorer.HISTORY_FILE = tmp_path / ".omo/state/history/uhs.jsonl"
    monkeypatch.setattr(scorer, "runtime_state_root", lambda: runtime)
    for name in ("score_tools", "score_governance", "score_scenes", "score_docs", "score_value"):
        monkeypatch.setattr(scorer, name, lambda: 80.0)
    monkeypatch.setattr(scorer.sys, "argv", [str(ROOT / "bin/gac/unified-health-score.py"), "--sync", "--json"])

    runtime_system = runtime / ".omo/state/system.yaml"
    checkout_system = tmp_path / ".omo/state/system.yaml"
    runtime_system.parent.mkdir(parents=True)
    checkout_system.parent.mkdir(parents=True)
    runtime_system.write_text("health_score: 10\n", encoding="utf-8")
    checkout_system.write_text("health_score: 20\n", encoding="utf-8")

    scorer.main()
    capsys.readouterr()
    assert "health_score: 78" in runtime_system.read_text(encoding="utf-8")
    assert checkout_system.read_text(encoding="utf-8") == "health_score: 20\n"


def test_omo_doctor_does_not_fail_when_health_projection_is_not_generated(tmp_path, monkeypatch):
    omo_src = ROOT / "projects/omo/src"
    monkeypatch.syspath_prepend(str(omo_src))
    doctor = _load_script("omo_doctor_projection_test", omo_src / "omo/omo_doctor.py")

    for rel in (
        "state/system.yaml",
        "goals/current.yaml",
        "_truth/INDEX.md",
        "_truth/registry/mof-capabilities.yaml",
        "standards/omo-governance-surfaces.md",
    ):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("present\n", encoding="utf-8")
    monkeypatch.setattr(doctor, "OMO_ROOT", tmp_path)
    monkeypatch.setattr(doctor, "projection_path", lambda _name: tmp_path / "state/runtime/health.yaml")

    result = doctor._check_key_files()
    assert result["status"] == "ok"
    assert "health projection not generated (optional)" in result["detail"]


def test_dual_track_checker_marks_missing_brief_as_skipped_not_pass(tmp_path, monkeypatch, capsys):
    checker = _load_script("dual_track_projection_test", ROOT / "bin/gac/check-dual-track-purity.py")
    monkeypatch.setattr(checker, "WORKSPACE", tmp_path)
    monkeypatch.setattr(checker, "runtime_state_root", lambda: tmp_path)
    monkeypatch.setattr(checker, "DUALTRACK_YAML", ROOT / ".omo/state/collab-dualtrack.yaml")

    assert checker._check_brief_throughput() == []
    assert checker.main(["--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "skipped"
    assert result["complete"] is False


def test_state_freshness_marks_absent_runtime_projection_optional(tmp_path, monkeypatch):
    checker = _load_script("state_freshness_projection_test", ROOT / "bin/gac/state-freshness-check.py")
    _write_projection_registry(tmp_path)
    monkeypatch.setattr(checker, "WORKSPACE", tmp_path)

    report = checker.run_check(file_filter="health")
    assert report["ok"] is True
    assert report["files_expired"] == 0
    assert report["results"][0]["optional"] is True
    assert report["results"][0]["exists"] is False

    runtime = tmp_path.parent / f"{tmp_path.name}-probe-state"
    canonical = runtime / "state/new/health.yaml"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("generated_at: 2026-09-29T00:00:00Z\n", encoding="utf-8")
    report = checker.run_check(file_filter="health", state_root=runtime)
    assert report["results"][0]["exists"] is True
    assert report["results"][0]["source"] == "canonical"


def test_meta_doctor_does_not_count_absent_projections_as_stale(tmp_path):
    doctor = _load_script("meta_doctor_projection_test", ROOT / "bin/gac/meta-doctor.py")
    _write_projection_registry(tmp_path)

    rows = doctor.check_heartbeats(tmp_path)
    projections = [row for row in rows if row["file"] in {
        ".omo/state/health.yaml",
        ".omo/state/system_health.yaml",
        ".omo/_control/governance-data.json",
    }]
    assert len(projections) == 3
    assert all(row["absent"] and not row["ok"] for row in projections)
    assert all(row["age_hours"] is None for row in projections)

    runtime = tmp_path.parent / f"{tmp_path.name}-meta-state"
    runtime_health = runtime / "state/new/health.yaml"
    runtime_health.parent.mkdir(parents=True)
    runtime_health.write_text("generated_at: 2026-09-29T00:00:00Z\n", encoding="utf-8")
    rows = doctor.check_heartbeats(tmp_path, state_root=runtime)
    external_absent = [row for row in rows if row["file"] in {
        ".omo/state/health.yaml",
        ".omo/state/system_health.yaml",
        ".omo/_control/governance-data.json",
    }]
    external_health_row = next(row for row in external_absent if row["file"] == ".omo/state/health.yaml")
    assert external_health_row["source"] == "canonical"
    assert Path(external_health_row["checked_file"]).is_absolute()
    assert all(row["absent"] for row in external_absent if row is not external_health_row)


def test_meta_doctor_reads_generated_at_out_of_json_projection(tmp_path):
    doctor = _load_script("meta_doctor_json_projection_test", ROOT / "bin/gac/meta-doctor.py")
    _write_projection_registry(tmp_path)
    target = tmp_path / ".omo/_control/governance-data.json"
    target.parent.mkdir(parents=True)

    def _row() -> dict:
        return next(
            r
            for r in doctor.check_heartbeats(tmp_path)
            if r["file"] == ".omo/_control/governance-data.json"
        )

    fresh = datetime.now(UTC).replace(microsecond=0).isoformat()
    target.write_text(json.dumps({"schema": "governance-data/v1", "generated_at": fresh}), encoding="utf-8")
    row = _row()
    assert not row["absent"] and row["exists"]
    assert row["age_hours"] is not None and row["age_hours"] < 1
    assert row["ok"] is True

    lapsed = datetime.now(UTC) - timedelta(days=30)
    target.write_text(
        json.dumps({"schema": "governance-data/v1", "generated_at": lapsed.isoformat()}),
        encoding="utf-8",
    )
    row = _row()
    assert row["ok"] is False
    assert 719 < row["age_hours"] < 721


def test_probe_heartbeat_monitor_reports_absent_projections_without_failure(tmp_path, monkeypatch):
    monitor = _load_script("probe_heartbeat_projection_test", ROOT / "bin/gac/probe-heartbeat-monitor.py")
    _write_projection_registry(tmp_path)
    matrix = tmp_path / "probe-heartbeats.yaml"
    matrix.write_text(
        "heartbeats:\n"
        "  - file: .omo/state/health.yaml\n    field: generated_at\n    sla_hours: 72\n"
        "  - file: .omo/state/system_health.yaml\n    field: last_scan\n    sla_hours: 48\n"
        "  - file: .omo/_control/governance-data.json\n    field: generated_at\n    sla_hours: 168\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(monitor, "MATRIX_FILE", matrix)
    monkeypatch.setattr(monitor, "code_root", lambda: tmp_path)
    monkeypatch.setattr(monitor, "state_root", lambda: tmp_path)

    report = monitor.check_heartbeats()
    assert report["failed_count"] == 0
    assert report["absent_count"] == 3
    assert all(row["absent"] and row["ok"] for row in report["absences"])

    runtime = tmp_path.parent / f"{tmp_path.name}-probe-state"
    canonical = runtime / "state/new/health.yaml"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("generated_at: 2026-09-29T00:00:00Z\n", encoding="utf-8")
    monkeypatch.setattr(monitor, "state_root", lambda: runtime)
    report = monitor.check_heartbeats()
    health = next(row for row in report["results"] if row["file"].endswith("health.yaml"))
    assert health["source"] == "canonical"
    assert health["checked_file"] == str(canonical)
    assert health["ok"] is True


def test_probe_heartbeat_monitor_ages_epoch_timestamps_instead_of_9999(tmp_path, monkeypatch):
    monitor = _load_script("probe_heartbeat_epoch_test", ROOT / "bin/gac/probe-heartbeat-monitor.py")
    _write_projection_registry(tmp_path)
    matrix = tmp_path / "probe-heartbeats.yaml"
    matrix.write_text(
        "heartbeats:\n"
        "  - file: .omo/state/system_health.yaml\n    field: last_scan\n    sla_hours: 48\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(monitor, "MATRIX_FILE", matrix)
    monkeypatch.setattr(monitor, "code_root", lambda: tmp_path)
    monkeypatch.setattr(monitor, "state_root", lambda: tmp_path)
    scanned = tmp_path / ".omo/state/system_health.yaml"
    scanned.parent.mkdir(parents=True)

    def _row() -> dict:
        return next(r for r in monitor.check_heartbeats()["results"] if not r["absent"])

    # 生成器写的是 epoch 浮点 (system_health.yaml::last_scan), 不是 ISO 串
    scanned.write_text(f"last_scan: {time.time() - 3600}\n", encoding="utf-8")
    assert _row()["age_hours"] == pytest.approx(1.0, abs=0.1)
    assert _row()["ok"] is True

    # epoch 支持不能顺手抹平真老化
    scanned.write_text(f"last_scan: {time.time() - 90 * 3600}\n", encoding="utf-8")
    assert _row()["ok"] is False

    # 解析不出来的仍旧红 (fail-closed), 不是缺省成新鲜
    scanned.write_text("last_scan: not-a-stamp\n", encoding="utf-8")
    assert _row()["age_hours"] == 9999
