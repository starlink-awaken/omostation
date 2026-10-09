"""L0 接线豁免清单回归测试 — 钉住 2026-10-09 L0 debt closeout 的三类处置.

背景 (BET 2026-10-09, L0 governance debt closeout):
  覆盖率清单 (check-rule-wiring-coverage.py) 报告 L0-constraints(子仓) 63 条
  未接线候选。逐条分类后:
    (a) 7 条规范散文 (CR-ENG-*) 移出可执行注册表 → L0-norms.yaml (非执行家),
        L0-constraints.yaml 留 pointer;
    (b) 9 条真实不变量 (P 谓词可验但无执行宿主) 保留为候选, 等人类排期;
    (c) 20 条前提已失效 (OPC 退役 / eCOS-v6 工具归档 / AGT 被拒) 标注
        lifecycle: removed + superseded_by (ADR/commit 可查), 并从候选分离;
    (d) 27 条"实现但换了名字"补 alias 映射 (registry-alias-map.yaml),
        evidence 指向真实宿主文件。

本文件按仓库既有约定钉住"测量集 == 评审清单" (参照
tests/unit/test_resident_write_plane_split.py::test_exact_root_split_pairs_are_the_reviewed_list):
  - 测量集来自工具真实输出 (或注册表真实内容), 评审清单是本文常量;
  - 任何一侧漂移 (新增未接线规则 / 新增 alias / 改 retired 集合 /
    改 relocated 集合) 都会让断言当场红, 迫使作者更新评审清单并说明理由。
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin/gac/check-rule-wiring-coverage.py"
ALIAS_MAP = ROOT / "bin/gac/registry-alias-map.yaml"
L0_REGISTRY = ROOT / "projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml"
L0_NORMS = ROOT / "projects/ecos/src/ecos/ssot/registry/L0-norms.yaml"

# 评审清单 (2026-10-09 人工逐条核定): 仅剩的真实不变量 = 待接线候选人。
REVIEWED_L0_UNREFERENCED = {
    "CR-MCP-LAZY-01",
    "CR-VIBEOPS-01",
    "CR-VIBEOPS-02",
    "X2-C02",
    "X2-C04",
    "X3-C02",
    "CR-C2G-V3-01",
    "CR-MOF-VERSION-COUPLED-01",
    "CR-GOV-CLOSED-LOOP-01",
}

# 评审清单: 本次 closeout 补 alias 的 L0 canonical 集合 (27 条, 见 alias map)。
REVIEWED_L0_ALIAS_CANONICALS = {
    "CR-CI-01", "CR-OMO-DIRECT-IO-01", "CR-C2G-INGRESS-01", "X4-C02",
    "CR-TRIGGER-01", "CR-TRIGGER-02", "CR-TRIGGER-03", "CR-TRIGGER-04",
    "CR-TRIGGER-05", "CR-TRIGGER-06", "CR-MOF-ALIAS-01", "CR-MOF-BIDIR-01",
    "CR-MOF-BRIDGE-01", "CR-MOF-STATE-BRIDGE-01", "CR-C2G-V3-02", "CR-C2G-V3-03",
    "CR-STRATEGY-02", "CR-STRATEGY-03", "CR-OMNIBUS-01", "CR-OMNIBUS-02",
    "CR-OMNIBUS-03", "CR-DEBT-CLOSURE-EVIDENCE-01", "CR-CROSS-PROJECT-LINT-01",
    "CR-GOV-FRONTMATTER-SCHEMA-01", "CR-GOV-DOC-CATEGORY-01",
    "CR-GAC-M1-INSTANCE-DRIFT-01", "CR-KOS-CONSENSUS-RAG-01",
}

# 评审清单: 本次 closeout 标 removed 的 L0 集合 (20 条)。
REVIEWED_L0_RETIRED = {
    "CR-CADENCE-01", "CR-INDEX-LOCK-01", "CR-MODE-ENV-01", "CR-TIME-ENV-01",
    "CR-MODE-COPY-01", "CR-DRIFT-LOOP-01", "CR-AUDIT-5REPOS-01",
    "CR-OMLX-MESH-GATE-01", "CR-C2G-INGRESS-PRECHECK-01", "CR-KOS-ONTOLOGY-DRIFT-01",
    "CR-AGT-ASI-01", "CR-AGT-ASI-02", "CR-AGT-ASI-03", "CR-AGT-ASI-04",
    "CR-AGT-ASI-05", "CR-AGT-ASI-06", "CR-AGT-ASI-07", "CR-AGT-ASI-08",
    "CR-AGT-ASI-09", "CR-AGT-ASI-10",
}

# 评审清单: 本次 closeout 移出可执行注册表的规范准则 (7 条)。
REVIEWED_L0_RELOCATED = {
    "CR-GOV-DIMENSION-SATURATION-01", "CR-ENG-BUG-CHAIN-01",
    "CR-ENG-CWD-ABSOLUTE-01", "CR-ENG-TOOL-GREP-01", "CR-ENG-SRP-INCREMENTAL-01",
    "CR-ENG-TEST-ISOLATION-01", "CR-ENG-LOOP-HONESTY-01",
}


def _load_tool():
    spec = importlib.util.spec_from_file_location("rule_cov", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rule_cov"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_alias_map() -> dict:
    with ALIAS_MAP.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_l0_registry() -> dict:
    with L0_REGISTRY.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _l0_rules(reg: dict) -> list[dict]:
    out: list[dict] = []
    for section in reg:
        if isinstance(reg[section], list):
            for entry in reg[section]:
                if isinstance(entry, dict) and "id" in entry:
                    out.append(entry)
    return out


def _path_tokens(text: str) -> list[str]:
    """从 evidence 字符串里提取看起来像仓内路径的 token."""
    return re.findall(r"(?:projects|x? :?bin|\.githooks|docs|feedback_p6)[\w./-]*", text)


def _evidence_path_exists(text: str) -> bool:
    for tok in _path_tokens(text):
        if tok.startswith(("projects/", "bin/", ".githooks/")):
            p = ROOT / tok
            if p.exists():
                return True
    return False


# ── 测量集 == 评审清单 ──────────────────────────────────


def test_l0_unreferenced_set_matches_reviewed_list():
    """覆盖率工具的真实 L0 候选 == 已评审的 9 条真实不变量.

    任何新增未接线规则 / 新增 alias / 改 retired / 改 relocated 都会红。
    """
    mod = _load_tool()
    inv = mod.inventory()
    got = set(inv["candidates_unwired"]["L0-constraints"])
    assert got == REVIEWED_L0_UNREFERENCED, (
        f"L0 候选漂移: got={sorted(got)} expected={sorted(REVIEWED_L0_UNREFERENCED)}"
    )


def test_l0_alias_groups_match_reviewed_set():
    """alias map 中『L0 canonical』集合 == 评审清单 (27 条)."""
    am = _load_alias_map()
    canonicals = {g["canonical"] for g in am["aliases"]}
    l0_canons = {c for c in canonicals if c in REVIEWED_L0_RELOCATED.union(
        REVIEWED_L0_RETIRED, REVIEWED_L0_UNREFERENCED, REVIEWED_L0_ALIAS_CANONICALS)}
    assert l0_canons == REVIEWED_L0_ALIAS_CANONICALS, (
        f"L0 alias 集合漂移: got={sorted(l0_canons)} expected={sorted(REVIEWED_L0_ALIAS_CANONICALS)}"
    )


def test_l0_retired_set_matches_reviewed_list():
    """alias map retired 中属于 L0 的 id == 评审清单 (20 条)."""
    am = _load_alias_map()
    retired = set(am.get("retired", []))
    l0_retired = retired & (
        REVIEWED_L0_RETIRED | REVIEWED_L0_ALIAS_CANONICALS
        | REVIEWED_L0_UNREFERENCED | REVIEWED_L0_RELOCATED)
    assert l0_retired == REVIEWED_L0_RETIRED, (
        f"L0 retired 漂移: got={sorted(l0_retired)} expected={sorted(REVIEWED_L0_RETIRED)}"
    )


def test_l0_relocated_pointers_match_reviewed_list():
    """L0-constraints.yaml 的 pointer 条目 == 评审清单 (7 条), 且目标文件存在."""
    reg = _load_l0_registry()
    ptrs = set()
    for section in reg:
        if isinstance(reg[section], list):
            for entry in reg[section]:
                if isinstance(entry, dict) and "pointer_to" in entry:
                    ptrs.add(entry["pointer_to"])
    assert ptrs == REVIEWED_L0_RELOCATED, (
        f"pointer 集合漂移: got={sorted(ptrs)} expected={sorted(REVIEWED_L0_RELOCATED)}"
    )
    assert L0_NORMS.is_file(), "L0-norms.yaml 必须存在 (非执行家)"
    norms = yaml.safe_load(L0_NORMS.read_text(encoding="utf-8"))
    norms_ids = {n["id"] for n in norms["norms"]}
    assert norms_ids == REVIEWED_L0_RELOCATED


# ── 每条豁免的理由必须指向真实文件 ─────────────────────────


def test_each_l0_alias_evidence_points_at_real_file():
    """每条 L0 alias 的 evidence 必须至少指向一个存在文件."""
    am = _load_alias_map()
    for g in am["aliases"]:
        if g["canonical"] not in REVIEWED_L0_ALIAS_CANONICALS:
            continue
        ev = g.get("evidence", {})
        blob = " ".join(str(v) for v in ev.values())
        assert _evidence_path_exists(blob), (
            f"{g['canonical']} evidence 未指向真实文件: {blob}"
        )


def test_each_l0_retired_rule_has_registry_annotation():
    """每条 retired L0 规则必须在注册表里带 lifecycle: removed + superseded_by."""
    reg = _load_l0_registry()
    by_id = {r["id"]: r for r in _l0_rules(reg)}
    for rid in REVIEWED_L0_RETIRED:
        rule = by_id.get(rid)
        assert rule is not None, f"{rid} 不在注册表"
        assert rule.get("lifecycle") == "removed", f"{rid} 缺 lifecycle: removed"
        assert rule.get("superseded_by"), f"{rid} 缺 superseded_by 引用"
        assert rule.get("superseded_reason"), f"{rid} 缺 superseded_reason"


def test_alias_map_parses_and_reviewed_ids_present():
    """alias map schema 完整性 (ref: tests/bin/test_registry_alias_resolver.py)."""
    am = _load_alias_map()
    canonicals = {g["canonical"] for g in am["aliases"]}
    assert "CR-CI-01" in canonicals
    assert "CR-TRIGGER-06" in canonicals
    assert len(am["retired"]) >= 20