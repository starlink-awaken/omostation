# ---
# status: active
# lifecycle: active
# owner: governance-agent
# ssot: .omo/_truth/registry/document-governance.yaml
# verifier: pytest tests/test_check_doc_claims.py
# ---
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/check-doc-claims.py"
SPEC = importlib.util.spec_from_file_location("check_doc_claims", MODULE_PATH)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _rules(findings: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(f["rule"], f["detail"]) for f in findings}


def test_dead_link_is_reported(tmp_path: Path) -> None:
    doc = tmp_path / "AGENTS.md"
    doc.write_text("# t\n\n[x](./nope.md)\n", encoding="utf-8")
    hits = MOD.check_doc(doc, tmp_path, tmp_path, set())
    assert ("dead_link", "./nope.md") in _rules(hits)


def test_existing_link_is_not_reported(tmp_path: Path) -> None:
    (tmp_path / "real.md").write_text("x", encoding="utf-8")
    doc = tmp_path / "AGENTS.md"
    doc.write_text("# t\n\n[x](./real.md)\n", encoding="utf-8")
    assert not _rules(MOD.check_doc(doc, tmp_path, tmp_path, set()))


def test_missing_path_reports_but_accepts_workspace_relative(tmp_path: Path) -> None:
    """仓内文档两种写法都存在: 相对子模块根 与 相对工作区根。

    只按其中一个解析会大量误报 —— 2026-11-27 首轮审计就踩了这个, 86 条命中里
    有一批是这种误报, 故这条判据必须双向都认。
    """
    ws = tmp_path
    sub = ws / "projects" / "demo"
    sub.mkdir(parents=True)
    (ws / "docs" / "registry.yaml").parent.mkdir(parents=True)
    (ws / "docs" / "registry.yaml").write_text("x", encoding="utf-8")
    doc = sub / "AGENTS.md"
    doc.write_text("# t\n\n`docs/registry.yaml`\n", encoding="utf-8")
    assert not _rules(MOD.check_doc(doc, sub, ws, set()))

    doc.write_text("# t\n\n`docs/nope.yaml`\n", encoding="utf-8")
    hits = MOD.check_doc(doc, sub, ws, set())
    assert ("missing_path", "docs/nope.yaml") in _rules(hits)


def test_runtime_state_paths_are_not_findings(tmp_path: Path) -> None:
    """.omo/state/** 是运行态、本就不入库, 链过去不算失真（AGENTS.md §7）。"""
    doc = tmp_path / "AGENTS.md"
    doc.write_text(
        "# t\n\n[`../../.omo/state/system.yaml`](../../.omo/state/system.yaml)\n",
        encoding="utf-8",
    )
    assert not _rules(MOD.check_doc(doc, tmp_path, tmp_path, set()))


def test_unregistered_uri_and_wildcard(tmp_path: Path) -> None:
    doc = tmp_path / "BOUNDARY.md"
    doc.write_text("# t\n\n`bos://acme/tool`\n`bos://acme/*`\n", encoding="utf-8")
    known = {"bos://acme/other", "https://x"}
    hits = MOD.check_doc(doc, tmp_path, tmp_path, known)
    rules = _rules(hits)
    # 精确未登记 -> 报; 通配有同域条目 -> 不报
    assert ("unregistered_uri", "bos://acme/tool") in rules
    assert ("unregistered_uri", "bos://acme/*") not in rules


def test_suppression_entries_are_explicit() -> None:
    """每条抑制都必须写理由, 且理由不得为空 —— 例外不能匿名。"""
    assert MOD.SUPPRESSIONS, "抑制清单不应为空（为空说明判据或文档已变，需复核）"
    for key, reason in MOD.SUPPRESSIONS.items():
        assert len(key) == 2 and all(key)
        assert reason.strip(), key


def test_repo_self_check_has_no_unsuppressed_findings() -> None:
    """对当前检出跑一遍: 要么零命中, 要么命中全部落在显式抑制里。"""
    report, rc = MOD.run(workspace=MOD.REPO_ROOT)
    assert rc == 0
    assert report["findings"] == [], report["findings"]
    assert report["registry_loaded"] is True
