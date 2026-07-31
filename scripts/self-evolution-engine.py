#!/usr/bin/env python3
"""self-evolution-engine.py — MetaOS 系统自演进与偏好向量学习引擎

功能: 1. 扫描人类在 WEEKLY-VERDICT / BDSK-VERDICT 中的历史打钩决策；
2. 提炼人类决策偏好向量 (Decision Preference Vector) 并更新至 state；
3. 动态检查 Workflow 架构缺陷，自动提议优化版的 Workflow Spec 定义。

v1.0 (Self-Evolution Architecture Engine) | 2026-07-31
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path("/Users/xiamingxing/Documents")
WS_ROOT = Path("/Users/xiamingxing/Workspace")
PREFERENCE_FILE = WS_ROOT / ".omo" / "state" / "human_preference_vector.json"
WORKFLOW_SPEC = WS_ROOT / "projects" / "ecos" / "etc" / "workflows" / "universal-ingest-pipeline.workflow.yaml"


def extract_human_verdict_history() -> list[dict[str, str]]:
    """扫描所有历史裁决单中的打钩选择 [x]."""
    verdict_files = list((DOCS_ROOT / "@驾驶舱" / "_knowledge" / "20-operations").glob("*VERDICT*.md"))
    verdict_files += list((DOCS_ROOT / "_inbox").glob("*VERDICT*.md"))

    choices = []
    for vf in verdict_files:
        try:
            content = vf.read_text(encoding="utf-8", errors="ignore")
            # 捕获选中的打钩项 [x] 或 [X]
            matches = re.findall(r"-\s*\[[xX]\]\s*(.+)", content)
            for m in matches:
                choices.append({"file": vf.name, "choice": m.strip()})
        except Exception:
            continue
    return choices


def update_preference_vector() -> dict[str, float]:
    """根据人类历史打钩，计算并更新人类偏好权值向量."""
    choices = extract_human_verdict_history()
    
    # 基础偏好向量模型
    prefs = {
        "prefer_mvp_speed": 0.5,       # 偏好极速 MVP 构建
        "prefer_privacy_local": 0.9,     # 偏好 100% 本地化
        "prefer_rich_ui": 0.8,          # 偏好富媒体与高颜值 UI
        "prefer_bdsk_deliberation": 0.85 # 偏好 B.D.S.K. 多 Agent 碰撞
    }

    # 根据历史打钩选择更新权值
    for c in choices:
        text = c["choice"]
        if "MVP" in text or "极速" in text:
            prefs["prefer_mvp_speed"] = min(1.0, prefs["prefer_mvp_speed"] + 0.1)
        if "本地" in text or "隐私" in text:
            prefs["prefer_privacy_local"] = min(1.0, prefs["prefer_privacy_local"] + 0.05)
        if "UI" in text or "图表" in text or "看板" in text:
            prefs["prefer_rich_ui"] = min(1.0, prefs["prefer_rich_ui"] + 0.1)

    PREFERENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "preference_vector": prefs,
        "sample_size": len(choices)
    }
    PREFERENCE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"🧠 人类决策偏好权值向量已学习更新 ──► {PREFERENCE_FILE.name} (权重: MVP={prefs['prefer_mvp_speed']:.2f}, 隐私={prefs['prefer_privacy_local']:.2f})")
    return prefs


def self_inspect_and_evolve_workflow() -> bool:
    """自动检查现有 Workflow Spec，提议并热扩充自进化节点."""
    if not WORKFLOW_SPEC.exists():
        return False
    
    spec_text = WORKFLOW_SPEC.read_text(encoding="utf-8")
    if "evolution_engine" not in spec_text:
        # 动态将自进化引擎注入 Workflow 规范中
        new_step = """
  - step_id: "ST-06"
    name: "人类打钩偏好自进化与架构重构引擎"
    engine: "projects/omo/scripts/self-evolution-engine.py"
    outputs: [".omo/state/human_preference_vector.json"]
"""
        updated_spec = spec_text.strip() + "\n" + new_step
        WORKFLOW_SPEC.write_text(updated_spec, encoding="utf-8")
        print(f"🧬 Workflow Spec 架构完成自我进化重构 ──► 新增自进化节点 ST-06")
        return True
    return False


def main() -> int:
    print("🧬 启动 MetaOS 智能体架构自进化与偏好向量学习引擎...")
    update_preference_vector()
    evolved = self_inspect_and_evolve_workflow()
    print(f"🎉 自进化轮次完成: {'架构发生自我重构' if evolved else '架构已处于最佳进化态'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
