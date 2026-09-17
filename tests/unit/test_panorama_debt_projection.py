import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_debt_projection_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _roots(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path / "runtime")
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path / "code")
    return module


def test_debt_projection_uses_code_root_and_lifecycle_state(tmp_path, monkeypatch) -> None:
    module = _roots(tmp_path, monkeypatch)
    _write(
        tmp_path / "runtime/.omo/debt/items/stale-open.yaml",
        "id: STALE-OPEN\ntitle: Stale open\nstatus: open\nseverity: high\n",
    )
    _write(
        tmp_path / "code/.omo/debt/items/legacy-closed.yaml",
        "id: LEGACY-CLOSED\ntitle: Closed\nstatus: registered\nlifecycle_state: closed\nseverity: high\n",
    )
    _write(
        tmp_path / "code/.omo/debt/items/open.yaml",
        "id: REAL-OPEN\ntitle: Real open\nstatus: open\nlifecycle_state: open\nseverity: medium\n",
    )

    report = module.collect_debt()
    alerts = module.collect_alerts()

    assert report["total"] == 2
    assert report["open"] == 1
    assert report["debts"][0]["id"] == "LEGACY-CLOSED"
    assert report["debts"][0]["status"] == "closed"
    assert alerts["total"] == 1
    assert alerts["high"] == 0
    assert alerts["alerts"][0]["msg"] == "开放债务: Real open"
