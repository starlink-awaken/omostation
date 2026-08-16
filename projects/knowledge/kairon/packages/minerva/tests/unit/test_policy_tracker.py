"""Policy Tracker 单元测试。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from minerva.policy_tracker.analyzer import analyze_items, score_item
from minerva.policy_tracker.fetcher import (
    PolicyItem,
    _parse_nhc_html,
    _parse_nhsa_html,
    fetch_recent,
)
from minerva.policy_tracker.kos_writer import _make_entity_id, save_to_kos
from minerva.policy_tracker.reporter import generate_report
from minerva.policy_tracker.runner import _default_output_path, _resolve_workspace_root, run
from minerva.policy_tracker.seeds import SEED_POLICIES

# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def sample_policies() -> list[PolicyItem]:
    return [
        PolicyItem(
            title="关于推进基层医疗机构药品集中采购的指导意见",
            issuing_agency="国家卫健委",
            doc_number="国卫基层〔2024〕1号",
            published_at="2026-06-01",
            summary="要求基层医疗机构参加省级药品集中采购，优先使用集采中选药品。",
            url="https://www.nhc.gov.cn/test/1.html",
            tags=["#primary-care", "#drug-procurement"],
        ),
        PolicyItem(
            title="化妆品监督管理条例实施细则",
            issuing_agency="国家药监局",
            doc_number="国家药监局公告2024年第1号",
            published_at="2026-05-15",
            summary="规范化妆品生产经营活动，加强监督管理。",
            url="https://www.nmpa.gov.cn/test/2.html",
            tags=["#cosmetics"],
        ),
        PolicyItem(
            title="关于做好医保支付方式改革 DRG/DIP 工作的通知",
            issuing_agency="国家医保局",
            doc_number="医保办函〔2024〕5号",
            published_at="2026-05-20",
            summary="推进 DRG/DIP 支付方式改革，加强医保基金监管。",
            url="https://www.nhsa.gov.cn/test/3.html",
            tags=["#medical-insurance", "#drg"],
        ),
    ]


# ── fetcher tests ─────────────────────────────────────────────────────────


def test_parse_nhc_html_extracts_policy():
    """Mock HTML 抓取 NHC 列表，应能解析出至少 1 条政策。"""
    html = """
    <html><body><ul>
      <li><a href="/jwj/xwfb/202406/abc.html">国家卫健委召开新闻发布会介绍基层医改进展</a><span>2024-06-01</span></li>
      <li><a href="/jwj/xwfb/202405/def.html">关于推进分级诊疗制度建设的工作要求</a><span>2024-05-20</span></li>
    </ul></body></html>
    """
    items = _parse_nhc_html(html)
    assert len(items) >= 2
    titles = [i.title for i in items]
    assert any("基层医改" in t for t in titles)
    for item in items:
        assert item.issuing_agency == "国家卫健委"
        assert item.url.startswith("http")
        assert "#source:nhc" in item.tags


def test_parse_nhsa_html_extracts_policy():
    """Mock HTML 抓取 NHSA 列表。"""
    html = """
    <html><body><ul>
      <li><a href="/art/202406/xyz.html" target="_blank">国家组织药品集中采购和使用工作的通知</a><span>2024-06-05</span></li>
    </ul></body></html>
    """
    items = _parse_nhsa_html(html)
    assert len(items) >= 1
    assert items[0].issuing_agency == "国家医保局"
    assert "药品集中采购" in items[0].title
    assert items[0].url.startswith("https://www.nhsa.gov.cn")


# ── seeds tests ───────────────────────────────────────────────────────────


def test_seeds_load_with_recent_dates():
    """种子数据应至少 3 条，且日期在最近 30 天内。"""
    from datetime import UTC, datetime, timedelta

    assert len(SEED_POLICIES) >= 3, f"需要至少 3 条种子，实际 {len(SEED_POLICIES)}"
    cutoff = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")
    for item in SEED_POLICIES:
        assert item.published_at >= cutoff, f"种子数据日期过旧: {item.published_at}"
        assert item.title
        assert item.issuing_agency in ("国家卫健委", "国家医保局", "国家药监局")
        assert item.doc_number


# ── analyzer tests ────────────────────────────────────────────────────────


def test_analyzer_scores_relevance(sample_policies):
    """基层+集采/医保政策应高相关，化妆品应低相关。"""
    scored = analyze_items(sample_policies, threshold=0.0)
    assert len(scored) == 3
    by_title = {i.title: i.relevance_score for i in scored}

    primary_care_score = next(
        (s for t, s in by_title.items() if "基层" in t and "采购" in t),
        None,
    )
    cosmetics_score = next((s for t, s in by_title.items() if "化妆品" in t), None)
    drg_score = next((s for t, s in by_title.items() if "医保支付" in t), None)

    assert primary_care_score is not None and primary_care_score >= 0.4
    assert cosmetics_score is not None and cosmetics_score < 0.2
    assert drg_score is not None and drg_score >= 0.2

    # 排序：相关度降序
    scores = [i.relevance_score for i in scored]
    assert scores == sorted(scores, reverse=True)


def test_score_item_bounded():
    """score_item 输出应 ∈ [0, 1]。"""
    item = PolicyItem(
        title="基层药品集采 医保支付 门诊共济 分级诊疗 基本药物",
        issuing_agency="国家卫健委",
        doc_number="X号",
        published_at="2026-06-01",
        summary="关键词堆叠测试",
        url="https://test.com",
    )
    s = score_item(item)
    assert 0.0 <= s <= 1.0


def test_analyzer_filters_threshold(sample_policies):
    """threshold=0.5 应过滤掉化妆品噪声。"""
    result = analyze_items(sample_policies, threshold=0.5)
    assert all("化妆品" not in i.title for i in result)
    assert any("基层" in i.title for i in result)


# ── kos_writer tests ──────────────────────────────────────────────────────


def test_make_entity_id_uses_kos_prefix():
    """KOS 实体 ID 必须以 CON-POL- 开头，长度 = 8 + 12 = 20。"""
    item = PolicyItem(
        title="test",
        issuing_agency="国家卫健委",
        doc_number="国卫基层〔2024〕1号",
        published_at="2026-06-01",
        summary="s",
        url="https://x.com/1",
    )
    eid = _make_entity_id(item)
    assert eid.startswith("CON-POL-"), f"Invalid KOS prefix: {eid}"
    assert len(eid) == len("CON-POL-") + 12


def test_make_entity_id_deterministic():
    """同一 PolicyItem 必须产生相同 ID。"""
    item = PolicyItem(
        title="t",
        issuing_agency="国家卫健委",
        doc_number="X号",
        published_at="2026-06-01",
        summary="d",
        url="https://x.com/1",
    )
    assert _make_entity_id(item) == _make_entity_id(item)


def test_make_entity_id_collision_free():
    """不同 doc_number 的相同 agency/url 不应碰撞。"""
    a = PolicyItem(
        title="t",
        issuing_agency="国家卫健委",
        doc_number="国卫基层〔2024〕1号",
        published_at="2026-06-01",
        summary="d",
        url="https://x.com/1",
    )
    b = PolicyItem(
        title="t",
        issuing_agency="国家卫健委",
        doc_number="国卫基层〔2024〕2号",
        published_at="2026-06-01",
        summary="d",
        url="https://x.com/1",
    )
    assert _make_entity_id(a) != _make_entity_id(b)


def test_kos_writer_skips_when_kos_unavailable(monkeypatch):
    """KOS 不可用时应 gracefully skip，返回 skipped=N, saved=0。"""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("kos"):
            raise ImportError(f"simulated: {name} not available")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    items = [
        PolicyItem(
            title="t",
            issuing_agency="国家卫健委",
            doc_number="X号",
            published_at="2026-06-01",
            summary="d",
            url="https://x.com/1",
        )
    ]
    stats = save_to_kos(items)
    assert stats == {"saved": 0, "failed": 0, "skipped": 1}


# ── runner / path tests ───────────────────────────────────────────────────


def test_resolve_workspace_root_finds_omostation():
    """从子目录向上搜应能找到 Workspace 根。"""
    root = _resolve_workspace_root()
    assert root is not None
    assert (root / ".omo" / "_delivery").is_dir()


def test_default_output_path_points_to_omostation_delivery():
    """默认报告应写到 omostation 根 .omo/_delivery/。"""
    path = _default_output_path("2026-06-05")
    assert path.name == "phase28-policy-tracker-2026-06-05-report.md"
    assert ".omo/_delivery" in str(path)
    assert ".omo/_delivery" in str(path)  # 结构断言 (worktree/CI 路径无关)
    assert path.parent.exists()


def test_runner_dry_run_no_kos_write(monkeypatch):
    """dry_run 模式不调用 save_to_kos，不写文件。"""
    import minerva.policy_tracker.runner as runner_mod

    called = {"save_to_kos": 0, "save_report": 0}

    def fake_save_to_kos(items):
        called["save_to_kos"] += 1
        return {"saved": 0, "failed": 0, "skipped": 0}

    def fake_save_report(items, path, *args, **kwargs):
        called["save_report"] += 1
        return Path(path)

    monkeypatch.setattr(runner_mod, "save_to_kos", fake_save_to_kos)
    monkeypatch.setattr(runner_mod, "save_report", fake_save_report)

    async def fake_fetch_recent(*args, **kwargs):
        return (
            [
                PolicyItem(
                    title="基层药品集采",
                    issuing_agency="国家卫健委",
                    doc_number="X号",
                    published_at="2026-06-01",
                    summary="s",
                    url="https://x.com/1",
                ),
            ],
            {"nhc": "seed", "nhsa": "seed"},
        )

    monkeypatch.setattr(runner_mod, "fetch_recent", fake_fetch_recent)

    result = asyncio.run(run(dry_run=True, days=30))
    assert called["save_to_kos"] == 0
    assert called["save_report"] == 0
    assert result["kos"] == {"saved": 0, "failed": 0, "skipped": 0}
    assert result["report_path"] == ""


# ── reporter tests ────────────────────────────────────────────────────────


def test_generate_report_structure(sample_policies):
    """报告应包含核心元素。"""
    scored = analyze_items(sample_policies, threshold=0.0)
    report = generate_report(scored, source_status={"nhc": "ok", "nhsa": "seed"}, run_date="2026-06-05")
    assert "# 卫生政策简报" in report
    assert "2026-06-05" in report
    assert "国家卫健委" in report or "国家医保局" in report
    assert "数据源可用性" in report


def test_generate_report_empty():
    """空列表应生成有效报告。"""
    report = generate_report([], run_date="2026-06-05")
    assert "0" in report
    assert "暂无高相关度" in report or "未抓取到" in report


# ── integration: end-to-end fetch with seeds fallback ─────────────────────


def test_fetch_recent_falls_back_to_seeds(monkeypatch):
    """网络不可用时 fetch_recent 应回退到种子数据。"""
    import httpx

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            import httpx as _httpx

            raise _httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    items, status = asyncio.run(fetch_recent(days=30))
    assert len(items) >= 3
    assert all(s == "seed" for s in status.values())
