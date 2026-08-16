"""Tech Radar 单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from minerva.tech_radar.analyzer import analyze_items, score_item
from minerva.tech_radar.fetcher import TechItem, _parse_github_trending
from minerva.tech_radar.kos_writer import _make_entity_id
from minerva.tech_radar.reporter import generate_report
from minerva.tech_radar.runner import _default_output_path, _resolve_workspace_root

# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def sample_items() -> list[TechItem]:
    return [
        TechItem(
            title="Multi-agent orchestration with MCP tool use",
            description="Agent RAG pipelines with knowledge graph and ontology",
            url="https://arxiv.org/abs/1",
            source="arxiv",
            tags=["cs.AI", "cs.MA"],
        ),
        TechItem(
            title="Weather deep learning forecast",
            description="Climate prediction using transformer models",
            url="https://test.com/2",
            source="arxiv",
            tags=["cs.LG"],
        ),
        TechItem(
            title="LLM reasoning with embedding vector search",
            description="Ontology-based RAG semantic search and retrieval",
            url="https://github.com/test/repo",
            source="github",
            tags=["python"],
        ),
    ]


# ── analyzer tests ────────────────────────────────────────────────────────


def test_score_item_high_relevance():
    item = TechItem(
        title="Multi-agent MCP tool use orchestration",
        description="knowledge graph RAG embedding vector",
        url="https://test.com",
        source="arxiv",
    )
    score = score_item(item)
    assert score >= 0.4, f"Expected high score, got {score}"


def test_score_item_low_relevance():
    item = TechItem(
        title="Sports score prediction model",
        description="Football match outcome forecasting",
        url="https://test.com",
        source="arxiv",
    )
    score = score_item(item)
    assert score < 0.3, f"Expected low score, got {score}"


def test_score_item_noise_penalty():
    item = TechItem(
        title="Drug discovery RAG knowledge graph",
        description="Medical imaging with agent orchestration",
        url="https://test.com",
        source="arxiv",
    )
    score_with_noise = score_item(item)
    clean = TechItem(
        title="RAG knowledge graph agent orchestration",
        description="semantic search retrieval",
        url="https://test.com",
        source="arxiv",
    )
    score_clean = score_item(clean)
    # noise 词惩罚应使分数降低
    assert score_with_noise < score_clean


def test_score_bounded():
    item = TechItem(
        title="agent multi-agent mcp tool-use knowledge graph ontology rag retrieval-augmented embedding vector reasoning",
        description="orchestration workflow pipeline scheduler llm language model transformer planning",
        url="https://test.com",
        source="arxiv",
    )
    score = score_item(item)
    assert 0.0 <= score <= 1.0


def test_analyze_items_filters_threshold(sample_items):
    # threshold=0.8 应该过滤掉气象预测
    result = analyze_items(sample_items, threshold=0.8)
    titles = [i.title for i in result]
    assert not any("Weather" in t for t in titles)


def test_analyze_items_sorted_by_score(sample_items):
    result = analyze_items(sample_items, threshold=0.0)
    scores = [i.relevance_score for i in result]
    assert scores == sorted(scores, reverse=True)


def test_analyze_items_upgrade_candidate_flag(sample_items):
    result = analyze_items(sample_items, threshold=0.0)
    candidates = [i for i in result if i.upgrade_candidate]
    # 至少高相关度的那条应该被标记
    assert len(candidates) >= 1
    for c in candidates:
        assert c.relevance_score >= 0.4


# ── reporter tests ────────────────────────────────────────────────────────


def test_generate_report_structure(sample_items):
    scored = analyze_items(sample_items, threshold=0.0)
    report = generate_report(scored, run_date="2026-06-05")
    assert "# 技术雷达简报" in report
    assert "2026-06-05" in report
    assert "升级候选" in report
    assert "ArXiv" in report or "arxiv" in report.lower()


def test_generate_report_empty_items():
    report = generate_report([], run_date="2026-06-05")
    assert "0" in report
    assert "暂无高优先级" in report


# ── fetcher unit tests (no network) ──────────────────────────────────────


def test_parse_github_trending_empty_html():
    items = _parse_github_trending("<html></html>", "python")
    assert items == []


def test_parse_github_trending_mock_html():
    html = """
    <article class="Box-row">
      <h2><a href="/owner/awesome-agent">awesome-agent</a></h2>
      <p class="col-9 color-fg-muted my-1 pr-4">Multi-agent framework for Python</p>
    </article>
    <article class="Box-row">
      <h2><a href="/test/mcp-server">mcp-server</a></h2>
      <p class="col-9 color-fg-muted my-1 pr-4">MCP protocol implementation</p>
    </article>
    """
    items = _parse_github_trending(html, "python")
    assert len(items) >= 1
    assert any("owner/awesome-agent" in i.title or "test/mcp-server" in i.title for i in items)
    for item in items:
        assert item.source == "github"
        assert "github.com" in item.url


# ── KOS writer tests ──────────────────────────────────────────────────────


def test_make_entity_id_uses_kos_prefix():
    """KOS 实体 ID 必须以合法前缀（CON-）开头，否则 store.put_entity 会拒绝。"""
    item = TechItem(title="test", description="d", url="https://x.com", source="arxiv")
    entity_id = _make_entity_id(item)
    assert entity_id.startswith("CON-"), f"Invalid KOS prefix: {entity_id}"
    # 格式: CON-TR-<12位hash> = 4 + 3 + 12 = 19
    assert len(entity_id) == len("CON-TR-") + 12


def test_make_entity_id_deterministic():
    """同一 TechItem 必须产生相同 ID（KOS put_entity 幂等性要求）。"""
    item = TechItem(title="t", description="d", url="https://x.com/1", source="github")
    assert _make_entity_id(item) == _make_entity_id(item)


def test_make_entity_id_collision_free_per_source():
    """不同 source 的相同 URL 不应碰撞。"""
    item1 = TechItem(title="t", description="d", url="https://x.com/1", source="arxiv")
    item2 = TechItem(title="t", description="d", url="https://x.com/1", source="github")
    assert _make_entity_id(item1) != _make_entity_id(item2)


def test_make_entity_id_matches_hashlib():
    """ID 后缀必须等于 sha256 源 key 的前 12 字符。"""
    import hashlib as _hl

    item = TechItem(title="t", description="d", url="https://x.com/abc", source="arxiv")
    key = f"tech-radar:{item.source}:{item.url or item.title}"
    expected_suffix = _hl.sha256(key.encode()).hexdigest()[:12]
    assert _make_entity_id(item) == f"CON-TR-{expected_suffix}"


# ── Path resolution tests ─────────────────────────────────────────────────


def test_resolve_workspace_root_finds_omostation():
    """从子目录向上搜应能找到 Workspace 根（含 .omo/_delivery）。"""
    root = _resolve_workspace_root()
    assert root is not None
    assert (root / ".omo" / "_delivery").is_dir()
    # 应是**最深**匹配（不是中间层的 projects/）
    # 测试从 kairon/packages/minerva 向上搜，最深应是 Workspace 根目录
    assert "Workspace" in str(root) or "projects" in str(root)


def test_default_output_path_points_to_omostation_delivery():
    """默认报告应写到 omostation 根 .omo/_delivery/，不是 cwd 的子目录。"""
    path = _default_output_path("2026-06-05")
    assert path.name == "tech-radar-2026-06-05-report.md"
    assert ".omo/_delivery" in str(path)
    # 父目录应存在
    assert path.parent.exists()
    # 应该是根 .omo/_delivery（最深），不是中间层
    assert "Workspace" in str(path)


def test_resolve_workspace_root_env_override(monkeypatch):
    """OMOSTATION_ROOT 环境变量应优先于 cwd 向上搜。"""
    fake_root = Path("/tmp/fake-omostation")
    (fake_root / ".omo" / "_delivery").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OMOSTATION_ROOT", str(fake_root))
    try:
        root = _resolve_workspace_root()
        assert root == fake_root
    finally:
        import shutil

        shutil.rmtree(fake_root)
