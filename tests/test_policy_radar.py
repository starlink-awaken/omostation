"""BET-Y1Q4-T7-03 policy radar: 打标/提取/降级/渲染。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("policy_radar", ROOT / "bin/bc-os/policy_radar.py")
assert spec and spec.loader
PR = importlib.util.module_from_spec(spec)
sys.modules["policy_radar"] = PR
spec.loader.exec_module(PR)


def test_tag_medical_llm_policy():
    score, tags = PR._score_and_tag("关于印发医疗大模型临床应用管理指南的通知", "policy")
    assert "医疗大模型" in tags and score >= 2


def test_tag_noise_penalized():
    score, _ = PR._score_and_tag("2026年度数据中心机房招标公告", "policy")
    assert score < 0  # 招标惩罚（零噪音契约）


def test_tag_english_paper():
    _, tags = PR._score_and_tag("Med-LLM: A Clinical Benchmark on EHR Interoperability", "paper")
    assert "医疗大模型" in tags and "数据要素互联互通" in tags


def test_extract_rss_strips_channel_title():
    sample = (
        "<rss><channel><title>cs.AI updates on arXiv.org</title>"
        "<item><title><![CDATA[Med-LLM Benchmark]]></title></item>"
        "<item><title>Data Sharing Survey</title></item></channel></rss>"
    )
    titles = PR._extract_titles(sample, "paper")
    assert "cs.AI updates on arXiv.org" not in titles and len(titles) == 2


def test_zero_score_items_filtered(monkeypatch, tmp_path):
    """白名单零分不入报（零噪音核心断言）。"""
    monkeypatch.setattr(PR, "STATE_DIR", tmp_path)
    html = '<a title="普通新闻无关键词"></a><a title="医疗大模型试点方案通知"></a>'
    monkeypatch.setattr(PR, "_fetch", lambda url, timeout=15: html)
    monkeypatch.setattr(PR, "SOURCES", [dict(PR.SOURCES[0])])
    brief = PR.collect()
    titles = [i["title"] for i in brief["items"]]
    assert "医疗大模型试点方案通知" in titles
    assert all("普通新闻" not in t for t in titles)


def test_degradation_uses_cache(monkeypatch, tmp_path):
    """网络全挂→缓存降级→is_degraded 且条目来自快照（circuit_breaker 契约）。"""
    monkeypatch.setattr(PR, "STATE_DIR", tmp_path)
    src = dict(PR.SOURCES[0])
    (tmp_path).mkdir(parents=True, exist_ok=True)
    (tmp_path / "cache.json").write_text(
        '{"sources": {"nhc": {"items": [{"title": "缓存里的医疗大模型通知", "score": 3, "tags": ["医疗大模型"]}]}}}',
        encoding="utf-8",
    )
    def boom(url, timeout=15):
        raise OSError("network down")
    monkeypatch.setattr(PR, "_fetch", boom)
    monkeypatch.setattr(PR, "SOURCES", [src])
    brief = PR.collect()
    assert brief["is_degraded"] and brief["degraded_sources"] == ["nhc"]
    assert any("缓存里的" in i["title"] for i in brief["items"])


def test_render_markdown_sections():
    brief = {"date": "2026-08-31", "is_degraded": False, "degraded_sources": [],
             "items": [{"title": "医疗大模型试点", "tags": ["医疗大模型"], "source": "测试"}]}
    md = PR.render_markdown(brief)
    assert "## 医疗大模型" in md and "医疗大模型试点" in md
