"""驾驶舱三板块面板资产 —— 真实性红线与注入契约测试.

对应 2026-09-18 架构迭代的两条硬约束:

1. **不造数** —— 趋势/分布不得用 ``Math.random`` / ``Math.sin`` 合成；
   无数据必须显示 NO_DATA / UNKNOWN，而不是补 0 或编造曲线。
2. **不硬编码** —— 板块内的计数必须来自 payload，不得写死数字
   （历史缺陷: 价值回路写死「3 活跃旅程 / 353 凭证 / 71 信念」）。
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PANEL_DIR = ROOT / "bin" / "panorama" / "assets" / "panels"
SYNC = ROOT / "bin" / "gac" / "zhixing-panel-sync.py"


def _load_sync():
    spec = importlib.util.spec_from_file_location("panel_sync", SYNC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["panel_sync"] = module
    spec.loader.exec_module(module)
    return module


# ── 红线 1: 不得造数 ───────────────────────────────────────────────────

def test_no_synthetic_data_generators_in_panels():
    """面板 JS 不得用随机/三角函数**生成数据序列**。

    注意: 雷达图等 SVG 用 Math.sin/cos 由角度计算坐标属于合法几何, 不算造数;
    真正要禁的是「用它拼出 data/points 数组」——历史缺陷正是
    ``data:Array.from({length:pts}, (_,i)=>Math.sin(i*0.5+seed)*…)``。
    """
    for name in ("logs", "metrics", "value"):
        src = (PANEL_DIR / f"{name}.js").read_text(encoding="utf-8")
        code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        code = re.sub(r"(?m)//.*$", "", code)
        assert "Math.random" not in code, f"{name}.js 使用了随机数造数"
        for lineno, line in enumerate(code.splitlines(), 1):
            if "Math.sin" not in line and "Math.cos" not in line:
                continue
            is_data_gen = any(tok in line for tok in ("data:", "Array.from(", "seed"))
            assert not is_data_gen, (
                f"{name}.js:{lineno} 用三角函数生成数据序列 → 合成数据: {line.strip()[:90]}")


def test_panels_read_from_payload_not_constants():
    """面板必须从 D.panel_* 读数据。"""
    assert "D.panel_events" in (PANEL_DIR / "logs.js").read_text(encoding="utf-8")
    assert "D.panel_history" in (PANEL_DIR / "metrics.js").read_text(encoding="utf-8")
    assert "D.panel_value" in (PANEL_DIR / "value.js").read_text(encoding="utf-8")


def test_no_hardcoded_counts_in_value_panel():
    """价值面板不得出现历史遗留的写死计数（353 / 71 / 3 活跃旅程）。"""
    src = (PANEL_DIR / "value.js").read_text(encoding="utf-8")
    for banned in ("353", "71 信念", "3 活跃旅程"):
        assert banned not in src, f"value.js 仍含硬编码 {banned}"


def test_metrics_trend_uses_real_series_sources():
    """趋势序列必须映射到 panel_history / panel_events 的真实键。"""
    src = (PANEL_DIR / "metrics.js").read_text(encoding="utf-8")
    for key in ("heartbeat_ok_hourly", "tick_ok_hourly", "refresh_ok_daily",
                "graph_nodes_daily", "hourly_24h", "daily_30d"):
        assert key in src, f"metrics.js 未使用真实序列 {key}"


def test_panels_expose_unknown_states_rather_than_zero():
    """无数据时必须显式 UNKNOWN / NO DATA，而不是静默 0。"""
    for name, token in (("logs", "NO DATA"), ("metrics", "NO DATA"), ("value", "UNKNOWN")):
        src = (PANEL_DIR / f"{name}.js").read_text(encoding="utf-8")
        assert token in src, f"{name}.js 缺少 {token} 诚实态"


def test_pending_authorization_ui_excludes_terminal_states():
    """已 merged/closed 的发布不得因 READY 验证缓存继续显示为待授权。"""
    template = (ROOT / "bin" / "panorama" / "assets" / "host" / "template.html").read_text(
        encoding="utf-8"
    )
    for state in ("MERGED", "CLOSED", "WITHDRAWN", "REJECTED", "SUPERSEDED"):
        assert f"{state}:1" in template
    assert "String(p.state||'').toUpperCase()" in template
    assert "terminalPublicationStates[String(p.state||'').toUpperCase()]" in template
    assert "p.verification==='READY_FOR_OPERATION_SPECIFIC_HUMAN_AUTHORIZATION'" in template


# ── 契约: 注入标记 ─────────────────────────────────────────────────────

def test_each_panel_asset_has_single_section_block():
    for name in ("logs", "metrics", "value"):
        html = (PANEL_DIR / f"{name}.html").read_text(encoding="utf-8")
        assert html.count("<section") == 1
        assert html.count("</section>") == 1
        assert f'<section id="{name}"' in html


def test_sync_registry_covers_all_three_panels():
    mod = _load_sync()
    assert set(mod.MARKER_PANELS) == {"logs", "metrics", "value"}
    # 注入顺序须保证锚点自洽: metrics 用非面板的 #health, logs 用 #metrics, value 用 #logs
    assert list(mod.MARKER_PANELS) == ["metrics", "logs", "value"]
    assert mod.SECTION_FALLBACK_ANCHOR["metrics"] == '<section id="health"'
    assert mod.SECTION_FALLBACK_ANCHOR["logs"] == '<section id="metrics"'
    assert mod.SECTION_FALLBACK_ANCHOR["value"] == '<section id="logs"' 
    for name in mod.MARKER_PANELS:
        assert (PANEL_DIR / f"{name}.html").is_file()
        assert (PANEL_DIR / f"{name}.js").is_file()


def test_migrate_section_replaces_block_with_markers():
    """未迁移时应把整个 <section> 换成带标记的资产内容。"""
    mod = _load_sync()
    html = '<html><body><section id="logs" class="section"><p>OLD</p></section></body></html>'
    out, action = mod._migrate_section(html, "logs", "<section id=\"logs\">NEW</section>", "logs")
    assert action == "migrated"
    assert "OLD" not in out
    assert mod.HTML_ANCHOR.format(name="logs") in out
    assert mod.HTML_END.format(name="logs") in out
    assert "NEW" in out


def test_migrate_section_reports_missing_anchor_only_without_any_tail():
    """连 </body> 都没有时才判 section_missing; 否则回退追加（见自愈测试）。"""
    mod = _load_sync()
    out, action = mod._migrate_section("<html><body>no section",
                                       "logs", "<section>x</section>", "logs")
    assert action == "section_missing" and out == "<html><body>no section"


def test_replace_region_is_idempotent_on_size():
    """按标记替换应稳定：二次替换后内容一致。"""
    mod = _load_sync()
    begin, end = "<!-- B -->", "<!-- E -->"
    text = f"head\n{begin}\nold\n{end}\ntail"
    once, ok1 = mod._replace_region(text, begin, end, "new-body")
    twice, ok2 = mod._replace_region(once, begin, end, "new-body")
    assert ok1 and ok2
    assert once == twice
    assert "old" not in once and "new-body" in once


def test_replace_region_rejects_broken_markers():
    mod = _load_sync()
    text = "head\n<!-- B -->\nonly begin\n"
    out, ok = mod._replace_region(text, "<!-- B -->", "<!-- E -->", "x")
    assert ok is False and out == text


def test_refresh_allowlist_patch_text_is_idempotent_marker():
    mod = _load_sync()
    assert mod.REFRESH_MARK == 'data["panel_events"]'
    for key in ("panel_events", "panel_history", "panel_value"):
        assert key in mod.REFRESH_PATCH


# ── 与 L1 采集器的字段契约 ─────────────────────────────────────────────

def test_panel_payload_keys_match_view_contract(tmp_path):
    """视图读取的字段必须由采集器产出（防止改名后页面静默空白）。"""
    spec = importlib.util.spec_from_file_location(
        "panel_collect", ROOT / "bin/panorama/panel-collect.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["panel_collect"] = mod
    spec.loader.exec_module(mod)

    tmp = tmp_path
    if True:
        events = mod.collect_event_stream(root=tmp)
        assert {"events", "events_all", "facets", "series", "sources", "summary"} <= set(events)
        assert {"by_type", "by_source", "by_status", "by_agent"} <= set(events["facets"])
        assert {"hourly_24h", "daily_7d", "daily_30d"} <= set(events["series"])
        assert {"events_24h", "events_per_hour", "failure_rate",
                "sources_live", "sources_missing"} <= set(events["summary"])

        history = mod.collect_metrics_history(root=tmp, dashboard_dir=tmp)
        for key in ("heartbeat_ok_hourly", "tick_ok_hourly", "refresh_ok_daily", "graph_nodes_daily"):
            assert key in history["series"], key
            assert "points" in history["series"][key]

        value = mod.collect_value_evidence(root=tmp)
        assert {"state", "state_reason", "samples", "stages", "thresholds",
                "vision_thresholds", "evidence"} <= set(value)


def test_restores_section_after_whole_block_deletion():
    """历史真实故障: 面板被并发覆盖整体删除, 自愈必须能重建而非只报缺失。"""
    mod = _load_sync()
    # metrics 的 section 被**整体删除**（只剩 anchor 目标 #health）
    html = '<body><section id="health">H</section></body>'
    out, action = mod._migrate_section(html, "metrics", "<section id=\"metrics\">NEW</section>", "metrics")
    assert action == "restored", action
    assert mod.HTML_ANCHOR.format(name="metrics") in out
    assert out.index(mod.HTML_ANCHOR.format(name="metrics")) < out.index('<section id="health"')

    # 三块全丢时, 按 metrics→logs→value 顺序可依次重建（锚点自洽）
    bare = '<body><section id="health">H</section></body>'
    for name in mod.MARKER_PANELS:
        bare, act = mod._migrate_section(
            bare, name, f'<section id="{name}">X</section>', name)
        assert act in ("restored", "restored_append", "migrated"), (name, act)
    order = [bare.index(f'<section id="{n}"') for n in ("value", "logs", "metrics", "health")]
    assert order == sorted(order), f"面板顺序错乱: {order}"


def test_falls_back_to_body_when_no_anchor_present():
    mod = _load_sync()
    html = '<body><div>no sections here</div></body>'
    out, action = mod._migrate_section(html, "logs", "<section id=\"logs\">X</section>", "logs")
    assert action == "restored_append"
    assert mod.HTML_ANCHOR.format(name="logs") in out
