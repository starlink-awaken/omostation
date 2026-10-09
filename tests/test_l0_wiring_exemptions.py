"""L0 接线豁免清单回归测试 — 钉住 L0 debt closeout 的处置 (2026-10-09) 及
adversarial audit 收口 (2026-10-10, F1-F6).

背景:
  覆盖率清单 (check-rule-wiring-coverage.py) 报告 L0-constraints(子仓) 63 条
  未接线候选。逐条分类后 (2026-10-09):
    (a) 7 条规范散文 (CR-ENG-*) 移出可执行注册表 → L0-norms.yaml (非执行家),
        L0-constraints.yaml 留 pointer;
    (b) 9 条真实不变量 (P 谓词可验但无执行宿主) 保留为候选, 等人类排期;
    (c) 20 条前提失效规则逐条生命周期标注并从候选分离;
    (d) 27 条"实现但换了名字"补 alias 映射 (registry-alias-map.yaml)。

  2026-10-10 adversarial audit 收口 (逐条再分类, 不以数字为唯一目标):
    - F2/F3: 7 条『伪接线』取下退回候选集 (CR-TRIGGER-01..06, CR-STRATEGY-02),
      逐条带 wiring_note (L0-constraints.yaml);
    - F2: CR-OMO-DIRECT-IO-01 重指向真实宿主 (contract_gatekeeper); 编译器恒绿分支标注;
    - F3(i): CR-OMNIBUS-01 (plane 合取强化), CR-KOS-CONSENSUS-RAG-01 (阈值门禁);
    - F3(iii): CR-GOV-FRONTMATTER-SCHEMA-01 双宿主 (doc-governance-check 逐字段);
    - F4: 9 条 removed 改判 suspended, AGT 10 条改判 rejected (逐条例证);
    - F5: retired 上限 + 同变更新 ID 必须进评审清单 + 每条须有注释理由;
    - F6: alias 必须有 anchor (宿主内真实符号) + token 在可执行上下文出现。

本文件按仓库既有约定钉住"测量集 == 评审清单" (参照
tests/unit/test_resident_write_plane_split.py::test_exact_root_split_pairs_are_the_reviewed_list):
  - 测量集来自工具真实输出 (或注册表真实内容), 评审清单是本文常量;
  - 任何一侧漂移都会让断言当场红, 迫使作者更新评审清单并说明理由。
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

# 评审清单 (2026-10-10 人工逐条核定): 待接线候选 = 真实不变量 (b) + 审计取下 (7 条)。
REVIEWED_L0_UNREFERENCED = {
    # (b) 真实不变量 — 谓词可验但无执行宿主
    "CR-MCP-LAZY-01",        # 无宿主
    "CR-VIBEOPS-01",         # 无实现
    "CR-VIBEOPS-02",         # 无宿主 (target 已并入 aetherforge)
    "X2-C02",                # compiler 无协议老化分支
    "X2-C04",                # compiler 无 half_life 分支
    "X3-C02",                # compiler value_tier 分支缺 cost_attribution
    "CR-C2G-V3-01",          # 无 ssot write-back 实现
    "CR-MOF-VERSION-COUPLED-01",  # 无 4 路径耦合检查
    "CR-GOV-CLOSED-LOOP-01",      # 无 post-commit 校验宿主
    # (ii) 审计取下退回候选集 — 有管理面/数据流但无强制检查 (wiring_note 在注册表)
    "CR-TRIGGER-01",         # management surface, 非检查
    "CR-TRIGGER-02",         # 五步 pipeline 无 gate
    "CR-TRIGGER-03",         # derivation_engine 只查已声明依赖健康
    "CR-TRIGGER-04",         # 每次执行审计无 gate
    "CR-TRIGGER-05",         # M2 不要求 health_check
    "CR-TRIGGER-06",         # detect_drift 为管理面 advisory
    "CR-STRATEGY-02",        # vector 默认值使谓词 trivially satisfiable
}

# 评审清单: L0 alias canonical 集合 (2026-10-10 审计后保留 21 条,
# 含 T10-07 批次四预存在的 CR-DEBT-GATE-ENUM-01).
REVIEWED_L0_ALIAS_CANONICALS = {
    "CR-CI-01", "CR-OMO-DIRECT-IO-01", "CR-C2G-INGRESS-01", "X4-C02",
    "CR-MOF-ALIAS-01", "CR-MOF-BIDIR-01", "CR-MOF-BRIDGE-01",
    "CR-MOF-STATE-BRIDGE-01", "CR-C2G-V3-02", "CR-C2G-V3-03",
    "CR-STRATEGY-03", "CR-OMNIBUS-01", "CR-OMNIBUS-02", "CR-OMNIBUS-03",
    "CR-DEBT-CLOSURE-EVIDENCE-01", "CR-CROSS-PROJECT-LINT-01",
    "CR-GOV-FRONTMATTER-SCHEMA-01", "CR-GOV-DOC-CATEGORY-01",
    "CR-GAC-M1-INSTANCE-DRIFT-01", "CR-KOS-CONSENSUS-RAG-01",
    "CR-DEBT-GATE-ENUM-01",
}

# F4: 生命周期判定 (2026-10-10 审计收口)
REVIEWED_L0_SUSPENDED = {  # 执行器被归档/迁移 (非作废), 恢复时须重新接线
    "CR-CADENCE-01", "CR-INDEX-LOCK-01", "CR-MODE-ENV-01", "CR-TIME-ENV-01",
    "CR-MODE-COPY-01", "CR-DRIFT-LOOP-01", "CR-AUDIT-5REPOS-01",
    "CR-C2G-INGRESS-PRECHECK-01", "CR-KOS-ONTOLOGY-DRIFT-01",
}
REVIEWED_L0_REJECTED = {  # 镜像被拒提案 (ADR-0415), 非工具退役
    "CR-AGT-ASI-01", "CR-AGT-ASI-02", "CR-AGT-ASI-03", "CR-AGT-ASI-04",
    "CR-AGT-ASI-05", "CR-AGT-ASI-06", "CR-AGT-ASI-07", "CR-AGT-ASI-08",
    "CR-AGT-ASI-09", "CR-AGT-ASI-10",
}
REVIEWED_L0_REMOVED = {  # 显式决策移除 (ADR-0423 归档 + gate 移除)
    "CR-OMLX-MESH-GATE-01",
}
REVIEWED_L0_RETIRED = (
    REVIEWED_L0_SUSPENDED | REVIEWED_L0_REJECTED | REVIEWED_L0_REMOVED
)

# F5: retired 评审宇宙 —— 所有当前 retired ID 必须出现在本文评审常量里。
# 原 18 条 gov retired (2026-10-09 前已存在, 本文一次性纳入评审基线)。
GOV_BASELINE_RETIRED = {
    "CR-AGE-BOS-01", "CR-AGE-POLICY-01", "CR-AGE-MEMORY-01", "CR-AGE-REPLAY-01",
    "CR-AGE-EVENT-01", "CR-P76-6-5-LLM-DEFERRAL", "CR-P77-2-1-PRINCIPLE-FORMALIZATION",
    "CR-P77-2-2-CATALOG-SSOT", "CR-BIN-RETIREMENT-CHECKLIST", "CR-L2-TASK-DELIVERABLE",
    "CR-L0-SSOT-PATH-NORM", "CR-X1-POLICIES-SSOT", "CR-X2-FRESHNESS-SSOT",
    "CR-EVIDENCE-DECLARED", "CR-EVIDENCE-SHA-FRESHNESS", "CR-GIT-STAGE-SUBMODULE-PIN",
    "CR-L4-DOMAIN-REGISTRY-FRESHNESS", "CR-X3-DEBT-TIER",
}
REVIEWED_RETIRED_UNIVERSE = REVIEWED_L0_RETIRED | GOV_BASELINE_RETIRED

# F5: retired 上限 (增长即需评审; 超过则测试红, 迫使逐条 justify 或拆出)。
MAX_RETIRED = 60

# 评审清单: 移出可执行注册表的规范准则 (7 条, 2026-10-09 未变)。
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


def _primary_executor_path(evidence: dict) -> Path | None:
    """bin_executor 第一段路径 (路径 token 的第一个文件, 去掉行号/箭头/括号注释)."""
    blob = str(evidence.get("bin_executor", ""))
    m = re.search(r"\b(?:projects/|bin/|\.githooks/)[\w./-]+", blob)
    return ROOT / m.group(0) if m else None


def _file_text_without_comments(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    # 去掉整行/行尾注释 (F6: 注释里出现 token 不算接线证据)
    return re.sub(r"#.*$", "", text, flags=re.M)


def _anchor_present(path: Path, anchor: str) -> bool:
    """anchor 必须作为真实定义/调用出现在宿主文件里 (F6)."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    return bool(
        re.search(
            rf"(?m)(^[\t ]*(?:async\s+)?def\s+{re.escape(anchor)}\b|^[\t ]*class\s+{re.escape(anchor)}\b|(?<![\w.]){re.escape(anchor)}\()",
            text,
        )
    )


def _validate_alias_group(group: dict) -> list[str]:
    """F6: 校验单条 alias group —— 返回问题列表 (空 = 通过)."""
    problems: list[str] = []
    rid = group.get("canonical", "")
    ev = group.get("evidence", {})
    if "anchor" not in group:
        problems.append(f"{rid}: missing anchor")
        return problems
    prim = _primary_executor_path(ev)
    if prim is None or not prim.is_file():
        problems.append(f"{rid}: bin_executor 无主执行文件 ({prim})")
        return problems
    if not _anchor_present(prim, str(group["anchor"])):
        problems.append(f"{rid}: anchor {group['anchor']!r} 不存在于 {prim}")
        return problems
    stripped = _file_text_without_comments(prim)
    tokens = [rid] + list(group.get("aliases", []))
    if not any(tok in stripped for tok in tokens if isinstance(tok, str)):
        problems.append(f"{rid}: 主执行文件 {prim} 可执行上下文里找不到 id/alias token")
    return problems


# ── 测量集 == 评审清单 ──────────────────────────────────


def test_l0_unreferenced_set_matches_reviewed_list():
    """覆盖率工具的真实 L0 候选 == 评审清单 (16 条)."""
    mod = _load_tool()
    inv = mod.inventory()
    got = set(inv["candidates_unwired"]["L0-constraints"])
    assert got == REVIEWED_L0_UNREFERENCED, (
        f"L0 候选漂移: got={sorted(got)} expected={sorted(REVIEWED_L0_UNREFERENCED)}"
    )


def test_l0_alias_groups_match_reviewed_set():
    """alias map 中『L0 canonical』集合 == 评审清单 (20 条)."""
    am = _load_alias_map()
    canonicals = {g["canonical"] for g in am["aliases"]}
    reg = _load_l0_registry()
    l0_declared = {r["id"] for r in _l0_rules(reg)} | REVIEWED_L0_RELOCATED
    l0_canons = {c for c in canonicals if c in l0_declared}
    assert l0_canons == REVIEWED_L0_ALIAS_CANONICALS, (
        f"L0 alias 集合漂移: got={sorted(l0_canons)} expected={sorted(REVIEWED_L0_ALIAS_CANONICALS)}"
    )


def test_l0_retired_set_matches_reviewed_list():
    """alias map retired 中属于 L0 的 id == 评审清单 (20 条)."""
    am = _load_alias_map()
    retired = set(am.get("retired", []))
    l0_retired = retired - GOV_BASELINE_RETIRED
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


# ── F6: alias 必须有可证 anchor (防『指向任何真实文件+注释 token』假接线) ──


def test_each_l0_alias_has_anchor_and_executable_token():
    """每条保留的 L0 alias 必须: 有 anchor 字段, anchor 真实存在于主执行文件,
    且 id/alias token 在主执行文件的**可执行上下文**出现 (注释不算)."""
    am = _load_alias_map()
    for g in am["aliases"]:
        if g["canonical"] not in REVIEWED_L0_ALIAS_CANONICALS:
            continue
        problems = _validate_alias_group(g)
        assert not problems, "; ".join(problems)


def test_fabricated_alias_is_detected():
    """audit F6 hypothetical: 指向任何真实文件 + 注释里放 token 必须被本校验拒绝."""
    # 用不相关的真实文件 (doc-governance-check.py), anchor 不存在 → 拒绝
    fake = {
        "canonical": "CR-TRIGGER-99",
        "aliases": ["trigger_fake_99"],
        "anchor": "nonexistent_symbol_99",
        "evidence": {
            "l0_constraints": "L0-constraints.yaml",
            "bin_executor": "bin/ssot/doc-governance-check.py",
        },
    }
    problems = _validate_alias_group(fake)
    assert problems, "fabricated alias 必须被 F6 校验拒绝"
    # anchor 碰巧真实存在, 但 token 只在『注释』里 → 必须仍被拒绝
    target = ROOT / "bin/ssot/doc-governance-check.py"
    stripped = _file_text_without_comments(target)
    assert "CR-TRIGGER-99" not in stripped, "前置条件: token 不在可执行上下文"
    fake2 = dict(fake)
    fake2["anchor"] = "_load_yaml_documents"  # 真实存在的锚点
    problems2 = _validate_alias_group(fake2)
    assert problems2, "token 只在注释里 (anchor 碰巧存在) 必须仍被拒绝"


# ── F4: 生命周期标注与档案一致 ──


def test_each_l0_retired_rule_has_registry_annotation():
    """每条 retired L0 规则必须在注册表里带与评审一致的生命周期标注."""
    reg = _load_l0_registry()
    by_id = {r["id"]: r for r in _l0_rules(reg)}
    for rid in REVIEWED_L0_SUSPENDED:
        rule = by_id.get(rid)
        assert rule is not None, f"{rid} 不在注册表"
        assert rule.get("lifecycle") == "suspended", f"{rid} 应为 suspended"
        assert rule.get("suspended_by"), f"{rid} 缺 suspended_by 引用"
        assert rule.get("suspended_reason"), f"{rid} 缺 suspended_reason"
    for rid in REVIEWED_L0_REJECTED:
        rule = by_id.get(rid)
        assert rule is not None, f"{rid} 不在注册表"
        assert rule.get("lifecycle") == "rejected", f"{rid} 应为 rejected"
        assert rule.get("rejected_by"), f"{rid} 缺 rejected_by 引用"
        assert rule.get("rejected_reason"), f"{rid} 缺 rejected_reason"
    for rid in REVIEWED_L0_REMOVED:
        rule = by_id.get(rid)
        assert rule is not None, f"{rid} 不在注册表"
        assert rule.get("lifecycle") == "removed", f"{rid} 应为 removed"
        assert rule.get("superseded_by"), f"{rid} 缺 superseded_by 引用"
        assert rule.get("superseded_reason"), f"{rid} 缺 superseded_reason"


def test_downgraded_rules_have_wiring_note():
    """审计取下的 7 条必须带 wiring_note (L0-constraints.yaml), 说明取下原因."""
    reg = _load_l0_registry()
    by_id = {r["id"]: r for r in _l0_rules(reg)}
    downgraded = {
        "CR-TRIGGER-01", "CR-TRIGGER-02", "CR-TRIGGER-03", "CR-TRIGGER-04",
        "CR-TRIGGER-05", "CR-TRIGGER-06", "CR-STRATEGY-02",
    }
    for rid in downgraded:
        rule = by_id.get(rid)
        assert rule is not None, f"{rid} 不在注册表"
        assert rule.get("wiring_note"), f"{rid} 缺 wiring_note (取下理由)"


# ── F5: retired 上限 + 同变更新 ID 必须评审 ──


def test_retired_cap_not_exceeded():
    """retired 清单封顶 (MAX_RETIRED). 超限 → 红, 迫使逐条 justify 或拆出."""
    am = _load_alias_map()
    retired = am.get("retired", [])
    assert len(retired) <= MAX_RETIRED, (
        f"retired 达到上限 {MAX_RETIRED} (当前 {len(retired)}): 需逐条 justify 或拆出"
    )


def test_retired_ids_are_reviewed_universe():
    """同变更把『新规则 id』塞进 retired 而不进评审清单 → 红 (F5 mute switch)."""
    am = _load_alias_map()
    retired = set(am.get("retired", []))
    unknown = retired - REVIEWED_RETIRED_UNIVERSE
    assert not unknown, (
        f"retired 含未评审 id: {sorted(unknown)} — 必须在本文评审清单中登记理由"
    )


def test_retired_entries_have_justification_comment():
    """每条 retired 条目必须带行内理由注释 (文档化 justification)."""
    lines = ALIAS_MAP.read_text(encoding="utf-8").splitlines()
    in_retired = False
    seen: list[str] = []
    for l in lines:
        if l.startswith("retired:"):
            in_retired = True
            continue
        if in_retired:
            if l.startswith(("#", "")) and not l.startswith("  - "):
                continue
            if not l.startswith("  - "):
                in_retired = False
                continue
            m = re.match(r"  - (\S+)(\s+#.*)?$", l)
            if m and not m.group(2):
                seen.append(m.group(1))
    assert not seen, f"retired 条目缺理由注释: {seen}"


def test_alias_map_parses_and_reviewed_ids_present():
    """alias map schema 完整性 (ref: tests/bin/test_registry_alias_resolver.py)."""
    am = _load_alias_map()
    canonicals = {g["canonical"] for g in am["aliases"]}
    assert "CR-CI-01" in canonicals
    assert len(am["retired"]) >= 20
