import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def test_a9_same_generation_ignores_previous_stale_dashboard(
    tmp_path, monkeypatch
) -> None:
    spec = importlib.util.spec_from_file_location("panorama_a9_race", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "DATA_JSON", tmp_path / "data.json")
    (tmp_path / "data.json").write_text(
        json.dumps({"generated_at": "2020-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )

    report = module.collect_a9_gate(payload={}, dashboard_live=True)

    assert report["verdict"] == "PARTIAL"
    assert "dashboard_live" not in report["detail"]
