"""驾驶舱契约守卫的覆盖面判据 —— 从 template.html 扩到全部被服务的 JS 资产。

缺陷（T10-364 实测）：发布器的契约守卫 `_check_template_data_consistency` 只扫
`template.html` 一个文件，而被服务的前端资产是 11 个 JS。资产层读 `D.<field>`
的缺席字段没有任何判据覆盖 —— 正是 T10-354 那类缺陷（页面渲染为空 / NaN）的
复发入口。实测线上 payload（114 顶层键）缺 `live_sources` / `events` /
`submodules_summary` / `safety_boundaries` / `local_server` /
`pending_publications`，资产侧全部读得到、全部读不出。

判据自证：`test_asset_scan_quiet_when_payload_provides_field` 在把守卫的扫描
面退回 template.html 之后必须变红，否则「资产被扫到」可能只是检测器没接上。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _load():
    spec = importlib.util.spec_from_file_location("panorama_asset_contract_guard", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _surface(tmp_path: Path, *, template: str = "", asset: str = "") -> Path:
    root = tmp_path / "dashboard"
    root.mkdir()
    if template:
        (root / "template.html").write_text(template, encoding="utf-8")
    if asset:
        (root / "demo_ui.js").write_text(asset, encoding="utf-8")
    return root


def test_asset_scan_reports_field_missing_from_payload(tmp_path):
    module = _load()
    root = _surface(tmp_path, asset="const D = window.D || {};\nD.live_sources?.catalog;\n")

    missing = module._scan_dashboard_asset_contract({"gates": []}, root)

    assert missing == {"demo_ui.js": ["live_sources"]}


def test_asset_scan_quiet_when_payload_provides_field(tmp_path):
    module = _load()
    root = _surface(tmp_path, asset="const D = window.D || {};\nD.live_sources?.catalog;\n")

    missing = module._scan_dashboard_asset_contract({"live_sources": {"catalog": {}}}, root)

    assert missing == {}


def test_null_payload_field_counts_as_missing(tmp_path):
    module = _load()
    root = _surface(tmp_path, asset="D.live_sources;\n")

    missing = module._scan_dashboard_asset_contract({"live_sources": None}, root)

    assert missing == {"demo_ui.js": ["live_sources"]}


def test_guard_prints_asset_warning_for_served_asset(tmp_path, monkeypatch, capsys):
    module = _load()
    root = _surface(tmp_path, asset="D.live_sources;\n")
    monkeypatch.setenv("ZHIXING_DASHBOARD_CODE_ROOT", str(root))

    module._check_template_data_consistency({"gates": []})

    out = capsys.readouterr().out
    assert "asset-data consistency: demo_ui.js" in out
    assert "live_sources" in out


def test_guard_still_reports_template_fields(tmp_path, monkeypatch, capsys):
    module = _load()
    root = _surface(tmp_path, template="<script>const R = D.reconciliation_candidates || [];</script>")
    monkeypatch.setenv("ZHIXING_DASHBOARD_CODE_ROOT", str(root))

    module._check_template_data_consistency({"gates": []})

    out = capsys.readouterr().out
    assert "template-data consistency" in out
    assert "reconciliation_candidates" in out
