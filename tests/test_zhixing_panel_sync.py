"""zhixing-panel-sync — 场景面板版本化资产的幂等注入与漂移自愈.

对应 2026-09-17 实证: ~/.local/share/zhixing-dashboard/ 不受版本控制,
多 agent 并发编辑 template.html 互相覆盖 (本面板被覆盖丢 2 次).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_MIN_TEMPLATE = """<html><body>
<nav>
<a href="#knowledge-memory" class="nav-item-engineering">知识记忆</a>
<a href="#skills-inventory" class="nav-item-engineering">技能清单</a>
</nav>
<section id="skills-inventory" class="section"><h1>技能</h1></section>
<script>
function refreshPanorama(){
  fetch('/__panorama_data__').then(function(r){return r.json()}).then(function(d){
    renderPanorama(d);
  });
}
function renderPanorama(D){}
document.addEventListener('DOMContentLoaded',function(){renderPanorama(1);});
</script>
<script>
window.addEventListener('hashchange',()=>go());
</script>
</body></html>
"""


def _load():
    spec = importlib.util.spec_from_file_location(
        "panel_sync", ROOT / "bin/gac/zhixing-panel-sync.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["panel_sync"] = module
    spec.loader.exec_module(module)
    return module


def _sandbox(tmp_path: Path):
    mod = _load()
    tpl = tmp_path / "template.html"
    tpl.write_text(_MIN_TEMPLATE, encoding="utf-8")
    mod.DASHBOARD_DIR = tmp_path
    mod.TEMPLATE = tpl
    return mod, tpl


def test_check_detects_drift_on_fresh_template(tmp_path):
    mod, tpl = _sandbox(tmp_path)
    assert mod.check() == 1
    info = mod.status()
    assert info["exists"] is True
    assert info["scene_panel"] is False


def test_ensure_injects_all_fragments(tmp_path):
    mod, tpl = _sandbox(tmp_path)
    result = mod.ensure()
    assert result["ok"] is True
    html = tpl.read_text(encoding="utf-8")
    assert 'href="#scene-system"' in html
    assert 'id="scene-system"' in html
    assert "function renderSceneSystem" in html
    assert "renderSceneSystem(D);" in html
    assert "renderSceneSystem(d);" in html
    assert mod.check() == 0


def test_ensure_is_idempotent(tmp_path):
    mod, tpl = _sandbox(tmp_path)
    mod.ensure()
    first = tpl.read_text(encoding="utf-8")
    second_run = mod.ensure()
    assert second_run["changed"] is False
    assert tpl.read_text(encoding="utf-8") == first


def test_self_heals_after_overwrite(tmp_path):
    """模拟被其他 agent 覆盖 → check 检出 → ensure 自愈."""
    mod, tpl = _sandbox(tmp_path)
    mod.ensure()
    html = tpl.read_text(encoding="utf-8")
    html = re.sub(r'<a href="#scene-system".*?</a>\n', '', html, flags=re.S)
    html = re.sub(r'<section id="scene-system".*?</section>\n', '', html, flags=re.S)
    html = re.sub(r"function renderSceneSystem\(D\)\{.*?\n\}\n", '', html, flags=re.S, count=1)
    html = re.sub(r"^\s*renderSceneSystem\([Dd]\);\n", "", html, flags=re.M)
    tpl.write_text(html, encoding="utf-8")
    assert mod.check() == 1

    assert mod.ensure()["ok"] is True
    healed = tpl.read_text(encoding="utf-8")
    for marker in ('href="#scene-system"', 'id="scene-system"',
                   "function renderSceneSystem", "renderSceneSystem(D);"):
        assert marker in healed, f"自愈缺失: {marker}"
    assert mod.check() == 0


def test_preserves_unrelated_content(tmp_path):
    mod, tpl = _sandbox(tmp_path)
    mod.ensure()
    html = tpl.read_text(encoding="utf-8")
    # 既有内容未被破坏
    assert 'id="skills-inventory"' in html
    assert "function renderPanorama" in html
    assert "知识记忆" in html


def test_missing_template_is_failure(tmp_path):
    mod, _ = _sandbox(tmp_path)
    mod.TEMPLATE = tmp_path / "nope.html"
    result = mod.ensure()
    assert result["ok"] is False and result["reason"] == "template_missing"
    assert mod.check() == 1
