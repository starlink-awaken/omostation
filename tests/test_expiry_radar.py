"""过期雷达回归测试 — 锁住"前瞻"语义与判定器对齐.

2026-09-21 实证: 两颗 SLA 时间炸弹 (X2-C05 ≤14d / doc-governance ≤90d 的 29 项)
在**同一天**集体越界, 昨天 CI 全绿、今天所有 PR 变红。根因是判定器纯二元
(`age > sla`), 无前瞻、无 grace 档。
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "bin/gac/check-expiry-radar.py"


def _load():
    spec = importlib.util.spec_from_file_location("expiry_radar", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["expiry_radar"] = mod
    spec.loader.exec_module(mod)
    return mod


def _fake_registry(tmp_path: Path, *, patterns=None, review_days=90,
                   excludes=None) -> Path:
    """造一个最小注册表 + 文档树, 让 scan_doc_surfaces 可确定性运行."""
    reg_dir = tmp_path / ".omo" / "_truth" / "registry"
    reg_dir.mkdir(parents=True)
    (reg_dir / "document-governance.yaml").write_text(
        "surfaces:\n"
        f"- id: fake-surface\n  review_days: {review_days}\n"
        f"  patterns: {patterns or ['docs/*.md']}\n"
        f"  excludes: {excludes or []}\n",
        encoding="utf-8",
    )
    return tmp_path


def _doc(root: Path, rel: str, reviewed: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\nlast-reviewed: {reviewed}\n---\n\n# T\n", encoding="utf-8")
    return p


# ── 核心语义: remaining = 距首次 fail 的天数 ────────────


def test_age_eq_sla_is_not_yet_expired(tmp_path):
    """age == sla 时判定器仍 pass (fail 条件是 age > sla) → 明天才 fail."""
    root = _fake_registry(tmp_path, review_days=90)
    _doc(root, "docs/a.md", "2026-06-23")  # 09-21 - 06-23 = 90
    mod = _load()
    items = mod.scan_doc_surfaces(root=root, horizon=7, today=date(2026, 9, 21))
    assert len(items) == 1
    it = items[0]
    assert it["age_days"] == 90
    assert it["remaining_days"] == 1, "age==sla 时还剩 1 天才 fail"
    assert it["state"] == "imminent"


def test_age_gt_sla_is_expired(tmp_path):
    """age = sla+1 → 当天即 fail."""
    root = _fake_registry(tmp_path, review_days=90)
    _doc(root, "docs/a.md", "2026-06-22")  # 09-21 - 06-22 = 91
    mod = _load()
    items = mod.scan_doc_surfaces(root=root, horizon=7, today=date(2026, 9, 21))
    assert items[0]["age_days"] == 91
    assert items[0]["remaining_days"] == 0
    assert items[0]["state"] == "expired"


def test_within_horizon_flagged_beyond_not(tmp_path):
    root = _fake_registry(tmp_path, review_days=90)
    _doc(root, "docs/soon.md", "2026-06-22")   # remaining 0
    _doc(root, "docs/far.md", "2026-08-01")    # remaining 61
    mod = _load()
    items = mod.scan_doc_surfaces(root=root, horizon=7, today=date(2026, 9, 21))
    paths = {i["path"] for i in items}
    assert "docs/soon.md" in paths
    assert "docs/far.md" not in paths, "超出前瞻窗口的不应报"


# ── 回放验证: 本可提前发现今天的事故 ────────────────────


def test_replay_would_have_warned_seven_days_early(tmp_path):
    """核心: 09-14 跑必须点名 09-21 将越界的批次 (真实事故的回放)."""
    root = _fake_registry(tmp_path, review_days=90)
    for i in range(3):
        _doc(root, f"docs/d{i}.md", "2026-06-22")  # 与事故同批
    mod = _load()
    items = mod.scan_doc_surfaces(root=root, horizon=7, today=date(2026, 9, 14))
    assert len(items) == 3
    assert all(i["state"] == "imminent" for i in items)
    assert all(i["remaining_days"] == 7 for i in items)
    clusters = mod.cluster_by_expiry(items, today=date(2026, 9, 14))
    assert len(clusters) == 1
    assert clusters[0]["expiry_date"] == "2026-09-21", "越界日必须对上真实 fail 日"
    assert clusters[0]["count"] == 3


def test_mass_cluster_only_reports_multiple(tmp_path):
    """单项不成'集体'—— 只有 >1 才算 mass expiry."""
    root = _fake_registry(tmp_path, review_days=90)
    _doc(root, "docs/one.md", "2026-06-22")
    _doc(root, "docs/two.md", "2026-06-23")
    mod = _load()
    items = mod.scan_doc_surfaces(root=root, horizon=7, today=date(2026, 9, 21))
    clusters = [c for c in mod.cluster_by_expiry(items, today=date(2026, 9, 21))
                if c["count"] > 1]
    assert clusters == [], "不同天越界的不应聚成集体"


# ── 边界与稳健性 ─────────────────────────────────────────


def test_future_review_date_not_flagged(tmp_path):
    """last-reviewed 在未来 → 交给判定器, 雷达不误报."""
    root = _fake_registry(tmp_path, review_days=90)
    _doc(root, "docs/a.md", "2026-12-01")
    mod = _load()
    assert mod.scan_doc_surfaces(root=root, horizon=7, today=date(2026, 9, 21)) == []


def test_missing_frontmatter_skipped(tmp_path):
    root = _fake_registry(tmp_path, review_days=90)
    p = root / "docs" / "a.md"
    p.parent.mkdir(parents=True)
    p.write_text("# 没有 frontmatter\n", encoding="utf-8")
    mod = _load()
    assert mod.scan_doc_surfaces(root=root, horizon=7, today=date(2026, 9, 21)) == []


def test_excludes_honored(tmp_path):
    root = _fake_registry(tmp_path, patterns=["docs/**/*.md"],
                          excludes=["docs/generated/**"], review_days=90)
    _doc(root, "docs/a.md", "2026-06-22")
    _doc(root, "docs/generated/b.md", "2026-06-22")
    mod = _load()
    items = mod.scan_doc_surfaces(root=root, horizon=7, today=date(2026, 9, 21))
    assert [i["path"] for i in items] == ["docs/a.md"], "excludes 必须生效"


def test_missing_registry_does_not_crash(tmp_path):
    mod = _load()
    assert mod.scan_doc_surfaces(root=tmp_path, horizon=7,
                                 today=date(2026, 9, 21)) == []
    assert mod.scan_x2_rules(root=tmp_path, horizon=7,
                             today=date(2026, 9, 21)) == []


# ── CLI ──────────────────────────────────────────────────


def test_strict_exit_codes(tmp_path, monkeypatch):
    mod = _load()
    root = _fake_registry(tmp_path, review_days=90)
    # 前置咬合: 必须真有越界文档, strict rc=1 的断言才有效
    # (原版只造注册表不造文档 → 空扫描恒 rc=0, 断言从未真正咬合过)
    _doc(root, "docs/a.md", "2026-06-01")  # 09-21 口径 age=112 > 90 → expired
    monkeypatch.setattr(mod, "_ROOT", root)
    monkeypatch.setattr(mod, "DOC_GOV", root / ".omo/_truth/registry/document-governance.yaml")
    monkeypatch.setattr(mod, "X2_RULES", root / ".omo/_truth/x2-freshness-rules.yaml")

    assert mod.main(["--json", "--today", "2026-01-01"]) == 0  # 未来出生的文档 age<0 → ok
    assert mod.main(["--json", "--strict", "--today", "2026-09-21"]) == 1


# ── 真实仓库: 前瞻能力必须可见 ───────────────────────────


def test_real_repo_reports_forward_risk():
    """本仓当前确有即将越界的文档 (09-27 一批) —— 雷达必须看到."""
    mod = _load()
    r = mod.scan(horizon=14)
    assert r["sla_sources"], "必须从权威注册表读阈值"
    # 已越界或即将越界至少有一类非空 (本仓确有 06-22/06-29 两批)
    assert r["total"] > 0, "本仓存在临近 SLA 的文档, 雷达应报出"
    # 前瞻: 至少报出一个**未来**才越界的对象 (这是本工具存在的理由)
    future = [i for i in r["imminent"] if i["remaining_days"] > 0]
    assert future, "雷达的价值在于前瞻——必须能看到尚未越界的对象"


# ── X2 规则的嵌套阈值 (2026-10-21 实证的回归) ────────────


def _x2_registry(tmp_path: Path, *, threshold_days=14, nested=True) -> Path:
    """造 x2-freshness-rules.yaml —— 默认按注册表**真实结构**把阈值嵌在 freshness 下。

    旧 reader 只读顶层 `threshold_days`, 于是本 fixture 下恒返回 []; 这正是
    2026-10-21 实测的缺陷 (14/14 条规则的阈值都在 freshness 下, 顶层 0 条)。
    """
    reg_dir = tmp_path / ".omo" / "_truth"
    reg_dir.mkdir(parents=True, exist_ok=True)
    target = tmp_path / ".omo/_truth/registry/omo-governance-surfaces.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\nlast-reviewed: 2026-10-06\n---\n", encoding="utf-8")
    freshness = (f"    freshness:\n      mechanism: registry-review\n"
                 f"      threshold_days: {threshold_days}\n") if nested else ""
    top = "" if nested else f"    threshold_days: {threshold_days}\n"
    (reg_dir / "x2-freshness-rules.yaml").write_text(
        "rules:\n"
        "  - rule_id: X2-FRESH-OMO-GOVERNANCE-SURFACES\n"
        "    target: .omo/_truth/registry/omo-governance-surfaces.yaml\n"
        f"{top}{freshness}",
        encoding="utf-8",
    )
    return tmp_path


def test_x2_rule_reads_nested_threshold_days(tmp_path):
    """阈值在 `freshness.threshold_days` 下 (注册表真实结构) —— 必须读到。"""
    mod = _load()
    _x2_registry(tmp_path, threshold_days=14, nested=True)
    items = mod.scan_x2_rules(root=tmp_path, horizon=30, today=date(2026, 10, 21))
    assert [i["surface"] for i in items] == ["x2:X2-FRESH-OMO-GOVERNANCE-SURFACES"], items


def test_x2_rule_still_reads_top_level_threshold_days(tmp_path):
    """旧格式 (顶层 threshold_days) 不能被这次修复打破。"""
    mod = _load()
    _x2_registry(tmp_path, threshold_days=14, nested=False)
    items = mod.scan_x2_rules(root=tmp_path, horizon=30, today=date(2026, 10, 21))
    assert [i["surface"] for i in items] == ["x2:X2-FRESH-OMO-GOVERNANCE-SURFACES"], items


def test_x2_rule_with_no_threshold_anywhere_is_skipped(tmp_path):
    """两个位置都没有阈值 —— 仍然跳过, 不是崩。"""
    mod = _load()
    reg_dir = tmp_path / ".omo" / "_truth"
    reg_dir.mkdir(parents=True, exist_ok=True)
    (reg_dir / "x2-freshness-rules.yaml").write_text(
        "rules:\n  - rule_id: X\n    target: .omo/_truth/registry/nope.yaml\n",
        encoding="utf-8")
    assert mod.scan_x2_rules(root=tmp_path, horizon=30, today=date(2026, 10, 21)) == []


def test_real_repo_x2_rule_is_covered():
    """集成: 真实注册表的嵌套阈值必须被读到 —— 这条钉住 X2-C05 不再瞎。"""
    mod = _load()
    items = mod.scan_x2_rules(root=mod._ROOT, horizon=30)
    ids = {i["surface"] for i in items}
    assert "x2:X2-FRESH-OMO-GOVERNANCE-SURFACES" in ids, (
        f"真实 x2-freshness-rules.yaml 的嵌套阈值未被读到; 命中 {sorted(ids)}"
    )
