"""G-CONV.3 ISC-3: execution-surface governance + de-false-positive ratio + single-source."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "bin/compass_radar.py"
    spec = importlib.util.spec_from_file_location("compass_radar", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_isc3_weights_runtime_dominant():
    m = _load()
    score, bd = m._composite_health_score(100, 1.0, 100, True)
    assert bd["weights"]["runtime"] == 0.5
    assert bd["weights"]["governance"] == 0.3
    assert bd["weights"]["freshness"] == 0.2
    assert score == 100


def test_governance_execution_surface_can_drop():
    m = _load()
    surface = {
        "orphan_worktrees": 2,
        "adr_renumber_events": 1,
        "concurrent_conflicts": 1,
        "weights": {
            "orphan_worktrees": 4,
            "adr_renumber_events": 5,
            "concurrent_conflicts": 8,
        },
    }
    # 100 - (2*4 + 1*5 + 1*8) = 100 - 21 = 79
    score, detail = m.governance_score_from_execution(100, surface)
    assert score == 79
    assert detail["execution_deduction"] == 21
    assert score < 100


def test_governance_zero_surface_stays_at_anomaly_base():
    m = _load()
    surface = {
        "orphan_worktrees": 0,
        "adr_renumber_events": 0,
        "concurrent_conflicts": 0,
        "weights": {
            "orphan_worktrees": 4,
            "adr_renumber_events": 5,
            "concurrent_conflicts": 8,
        },
    }
    score, detail = m.governance_score_from_execution(85, surface)
    assert score == 85
    assert detail["execution_deduction"] == 0


def test_healthy_probe_counts_online(tmp_path):
    m = _load()
    import yaml

    sh = {
        "services": {
            "agora-gateway": {
                "type": "daemon",
                "health_check": "healthy (probe)",
                "runtime": {"status": "running"},
            },
            "agora-sse": {
                "type": "daemon",
                "health_check": "healthy",
                "runtime": {"status": "running"},
            },
            "cron-service": {
                "type": "daemon",
                "health_check": "healthy",
                "runtime": {"status": "running"},
            },
            "ollama": {
                "type": "daemon",
                "health_check": "healthy",
                "runtime": {"status": "idle"},
            },
            "gbrain": {"type": "cli", "health_check": "n/a"},
        }
    }
    state = tmp_path / ".omo" / "state"
    state.mkdir(parents=True)
    (state / "system_health.yaml").write_text(yaml.dump(sh), encoding="utf-8")
    ratio, summary = m.collect_runtime_health(tmp_path)
    assert ratio == 1.0
    assert summary["total_daemons"] == 4
    assert summary["online_daemons"] == 4
    assert summary["ratio"] == 1.0


def test_system_projection_single_source_ratio():
    m = _load()
    report = {
        "health_score": 96,
        "governance_anomaly_score": 79,
        "service_online_ratio": 1.0,
        "runtime_summary": {
            "online_daemons": 4,
            "total_daemons": 4,
            "online_services": 4,
            "total_services": 4,
            "ratio": 1.0,
        },
        "generated_at": "2026-07-17T12:00:00Z",
    }
    updates = m.build_system_projection_updates(ROOT, report)
    assert updates["service_online_ratio"] == 1.0
    assert updates["runtime_health_summary"]["ratio"] == 1.0
    assert updates["runtime_health_summary"]["online_services"] == 4
    assert updates["runtime_health_summary"]["total_services"] == 4
    assert updates["health_score_source"] == "compass_radar_composite_isc3"
