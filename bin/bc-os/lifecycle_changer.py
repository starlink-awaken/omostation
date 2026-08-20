#!/usr/bin/env python3
"""lifecycle_changer.py — EvolutionEngine 提案真实改变 scene card lifecycle.

修复 #1 核心问题: EvolutionEngine 是脚手架, 不改变状态.
本模块让 proposal.apply() 真的写入 scene card 的 lifecycle 字段.

设计:
- 提案 apply 时直接修改 docs/scene-cards/<scene_id>.yaml
- 写入 lifecycle + lifecycle_gate.status 字段
- 同时追加审计 trail (applied_proposals)
- 受控: 仅 L0/L1 风险可自动 apply, L2+ 需 operator 显式 --force
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCENE_CARDS_DIR = ROOT / "docs" / "scene-cards"
APPLIED_LOG = ROOT / ".omo" / "state" / "applied-proposals.json"

LIFECYCLE_ORDER = ["draft", "shadow", "assisted", "routine"]
AUTO_APPLY_MAX_RISK = "L1"  # 仅 L0/L1 自动 apply


def read_scene_card(scene_id: str) -> dict:
    """读取 scene card YAML (frontmatter + body 双文档)."""
    import yaml
    # 同时检查顶层和 v2 目录
    for pattern in ("*.yaml", "v2/*.yaml"):
        for f in SCENE_CARDS_DIR.glob(pattern):
            try:
                docs = list(yaml.safe_load_all(f.read_text()))
            except Exception:
                continue
            # frontmatter 是第一个 dict 文档
            for doc in docs:
                if isinstance(doc, dict) and doc.get("scene_id") == scene_id:
                    return {"path": f, "data": doc}
    return {}


def write_scene_card(path: Path, data: dict) -> None:
    """写入 scene card frontmatter, 保留 body 部分."""
    import yaml
    raw = path.read_text() if path.exists() else ""
    if "---" in raw:
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            # 保留原 body
            body = parts[2]
            new_front = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
            path.write_text("---\n" + new_front + "---" + body)
            return
    # 无 frontmatter, 直接写
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False))


def parse_lifecycle(lc: str) -> int:
    try:
        return LIFECYCLE_ORDER.index(lc)
    except ValueError:
        return -1


def can_upgrade(current: str, proposed: str) -> bool:
    """仅允许正向升级 (shadow → assisted, assisted → routine).)."""
    ci = parse_lifecycle(current)
    pi = parse_lifecycle(proposed)
    return ci >= 0 and pi > ci


def apply_lifecycle_change(proposal: dict, force: bool = False) -> dict:
    """应用 lifecycle 提案到 scene card."""
    target = proposal.get("target")
    ptype = proposal.get("type", "")
    proposed_state = proposal.get("proposed_state", {})
    risk = proposal.get("risk_level", "L1")
    if not target:
        return {"ok": False, "reason": "missing target"}
    # 风险门
    risk_level_num = int(risk[1:]) if len(risk) > 1 else 0
    if risk_level_num > int(AUTO_APPLY_MAX_RISK[1:]) and not force:
        return {"ok": False, "reason": f"risk {risk} > L1, requires --force"}
    card = read_scene_card(target)
    if not card:
        return {"ok": False, "reason": f"scene card not found: {target}"}
    applied_changes = []
    # scene_lifecycle 提案
    if ptype == "scene_lifecycle":
        new_lifecycle = proposed_state.get("lifecycle")
        if not new_lifecycle:
            return {"ok": False, "reason": "scene_lifecycle missing proposed_state.lifecycle"}
        current_lc = card["data"].get("lifecycle", "?")
        if not can_upgrade(current_lc, new_lifecycle):
            return {"ok": False, "reason": f"cannot downgrade {current_lc} → {new_lifecycle}"}
        card["data"]["lifecycle"] = new_lifecycle
        applied_changes.append(f"lifecycle: {current_lc} → {new_lifecycle}")
    # route_tune 提案: 更新 triggered / auto_score 标记
    elif ptype == "route_tune":
        for k, v in proposed_state.items():
            if k in ("triggered", "auto_score"):
                card["data"][f"evolution_{k}"] = v
                applied_changes.append(f"{k}={v}")
    # template_optimize 提案: 写入优化标记 + 模板引用
    elif ptype == "template_optimize":
        template_ref = proposed_state.get("template_ref", "intake-review-deliver")
        optimization = proposed_state.get("optimization", "default")
        card["data"]["optimized_template"] = template_ref
        card["data"]["template_optimization"] = optimization
        card["data"]["template_optimized_at"] = __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())
        applied_changes.append(f"template: {template_ref} ({optimization})")
    else:
        # new_scene 等: 写入 evolution_optimized 标记
        card["data"]["evolution_optimized"] = True
        applied_changes.append("evolution_optimized=True")
    # 公共元数据
    card["data"]["last_modified_by"] = "evolution_engine"
    card["data"]["last_modified_at"] = __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())
    if "lifecycle_gate" not in card["data"]:
        card["data"]["lifecycle_gate"] = {}
    card["data"]["lifecycle_gate"]["status"] = f"applied_by_evolution_engine"
    write_scene_card(card["path"], card["data"])
    # 审计 log
    entry = {
        "proposal_id": proposal.get("id"),
        "type": ptype,
        "target": target,
        "applied_changes": applied_changes,
        "applied_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
        "risk_level": risk,
    }
    log = []
    if APPLIED_LOG.exists():
        log = json.loads(APPLIED_LOG.read_text())
    log.append(entry)
    APPLIED_LOG.parent.mkdir(parents=True, exist_ok=True)
    APPLIED_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    return {"ok": True, "target": target, "applied_changes": applied_changes, "log_entry": entry}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal-id", required=True, help="proposal ID to apply")
    parser.add_argument("--force", action="store_true", help="apply even for L2+ risk")
    args = parser.parse_args()
    # 查找 proposal
    proposals_file = ROOT / ".omo" / "state" / "evolution-proposals.json"
    if not proposals_file.exists():
        print("no proposals file")
        return 1
    proposals = json.loads(proposals_file.read_text())
    proposal = next((p for p in proposals if p.get("id") == args.proposal_id), None)
    if not proposal:
        print(f"proposal {args.proposal_id} not found")
        return 1
    result = apply_lifecycle_change(proposal, force=args.force)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())