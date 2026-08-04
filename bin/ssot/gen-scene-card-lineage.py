#!/usr/bin/env python3
"""Scene Card Lineage 生成器 (ECCP N8).

扫描 scene-cards + candidates → docs/generated/scene-card-lineage.yaml (谱系图 SSOT).
对标: Backstage software catalog (关系图 + 漏斗可视化).

源:
  1. docs/scene-cards/*.yaml — 正式 scene cards (proposal / active)
  2. docs/scene-cards/candidates/*.yaml — 正式候选文件 (proposal, 待激活)
  注: docs/scene-card-candidate-seeds.yaml 是种子库 (opportunity hypothesis),
      activation forbidden, 不纳入正式 funnel.candidates.

输出漏斗: candidates → scene_cards → pending_business → active
关系图: capability_refs 反向索引 (capability → 使用它的 scene_id 列表)

用法:
  uv run --with pyyaml python bin/ssot/gen-scene-card-lineage.py
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
SCENE_CARDS_DIR = WORKSPACE / "docs/scene-cards"
CANDIDATES_DIR = SCENE_CARDS_DIR / "candidates"
OUTPUT = WORKSPACE / "docs/generated/scene-card-lineage.yaml"


def _load_scene_card_body(path: Path) -> dict:
    """加载 scene-card YAML (多文档: front matter + body), 返回 body (含 schema 的文档)."""
    docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
    if not docs:
        return {}
    for d in docs:
        schema = str(d.get("schema", ""))
        if schema.startswith("scene-card/"):
            return d
    return docs[-1]


def scan_scene_cards() -> list[dict]:
    """扫 docs/scene-cards/*.yaml (排除 candidates 子目录), 提取谱系字段."""
    scenes: list[dict] = []
    if not SCENE_CARDS_DIR.is_dir():
        return scenes
    for p in sorted(SCENE_CARDS_DIR.glob("*.yaml")):
        body = _load_scene_card_body(p)
        if not body or not body.get("scene_id"):
            continue
        caps = body.get("capability_refs") or []
        caps = [str(c).strip() for c in caps if c]
        scenes.append({
            "scene_id": body["scene_id"],
            "journey_id": body.get("journey_id", ""),
            "lifecycle": body.get("lifecycle", "unknown"),
            "approval_state": body.get("approval_state", "unknown"),
            "outcome_metric": body.get("outcome_metric", ""),
            "capability_refs": caps,
            "source": str(p.relative_to(WORKSPACE)),
        })
    return scenes


def scan_candidates() -> list[dict]:
    """扫 docs/scene-cards/candidates/*.yaml (正式候选文件, proposal 阶段)."""
    candidates: list[dict] = []
    if not CANDIDATES_DIR.is_dir():
        return candidates
    for p in sorted(CANDIDATES_DIR.glob("*.yaml")):
        body = _load_scene_card_body(p)
        if not body:
            continue
        candidates.append({
            "candidate_id": body.get("candidate_id") or body.get("scene_id", p.stem),
            "proposed_scene_id": body.get("scene_id", body.get("proposed_scene_id", "")),
            "source": str(p.relative_to(WORKSPACE)),
        })
    return candidates


def build_connector_relations(scenes: list[dict]) -> dict[str, list[str]]:
    """capability_refs 反向索引: capability → [scene_id, ...] (去重保序)."""
    rel: dict[str, list[str]] = {}
    for s in scenes:
        for cap in s["capability_refs"]:
            rel.setdefault(cap, [])
            if s["scene_id"] not in rel[cap]:
                rel[cap].append(s["scene_id"])
    return dict(sorted(rel.items()))


def emit_yaml(scenes: list[dict], candidates: list[dict], relations: dict) -> str:
    """纯字符串拼接输出 YAML (缩进风格匹配谱系图 SSOT 约定)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pending = sum(1 for s in scenes if str(s["approval_state"]).startswith("pending"))
    active = sum(1 for s in scenes if s["lifecycle"] == "active")
    lines = [
        "version: '1.0'",
        f"generated_at: '{now}'",
        "generator: bin/ssot/gen-scene-card-lineage.py",
        "funnel:",
        f"  candidates: {len(candidates)}",
        f"  scene_cards: {len(scenes)}",
        f"  pending_business: {pending}",
        f"  active: {active}",
        "scenes:",
    ]
    for s in scenes:
        lines.append(f"- scene_id: {s['scene_id']}")
        lines.append(f"  journey_id: {s['journey_id']}")
        lines.append(f"  lifecycle: {s['lifecycle']}")
        lines.append(f"  approval_state: {s['approval_state']}")
        lines.append(f"  outcome_metric: {s['outcome_metric']}")
        if s["capability_refs"]:
            lines.append("  capability_refs:")
            for c in s["capability_refs"]:
                lines.append(f"  - {c}")
        else:
            lines.append("  capability_refs: []")
        lines.append(f"  source: {s['source']}")
    if candidates:
        lines.append("candidates:")
        for c in candidates:
            lines.append(f"- candidate_id: {c['candidate_id']}")
            lines.append(f"  proposed_scene_id: {c['proposed_scene_id']}")
            lines.append(f"  source: {c['source']}")
    else:
        lines.append("candidates: []")
    if relations:
        lines.append("connector_relations:")
        for cap, scene_list in relations.items():
            lines.append(f"  {cap}:")
            for sid in scene_list:
                lines.append(f"  - {sid}")
    else:
        lines.append("connector_relations: []")
    return "\n".join(lines) + "\n"


def main() -> int:
    scenes = scan_scene_cards()
    candidates = scan_candidates()
    relations = build_connector_relations(scenes)

    yaml_text = emit_yaml(scenes, candidates, relations)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(yaml_text, encoding="utf-8")

    pending = sum(1 for s in scenes if str(s["approval_state"]).startswith("pending"))
    active = sum(1 for s in scenes if s["lifecycle"] == "active")
    binding_count = sum(len(v) for v in relations.values())
    print(f"✅ lineage 生成: {OUTPUT.relative_to(WORKSPACE)}")
    print(
        f"   funnel: candidates={len(candidates)} scene_cards={len(scenes)} "
        f"pending={pending} active={active}"
    )
    print(f"   connector_relations: {len(relations)} capabilities, {binding_count} 绑定")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
