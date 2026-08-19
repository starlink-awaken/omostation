#!/usr/bin/env python3
"""l3_smart_router.py — L3 智能路由 (替代 regex).

修复 #2: signal_router 用 regex, LLM 接入前先用多维评分.
多维评分:
  - 类型 (公文/会议/调研/代码/默认)
  - 紧急度 (含 due/expedite/紧急/ASAP/今天/now)
  - 质量 (内容长度 + 关键词密度)
  - 上下文 (文件名 + 时间戳)

与 knowledge_quality 同框架: 0~1 评分, 最高分场景.

设计:
  - 4 个评分维度 → 路由决策
  - 解释路径 (为什么选这个场景)
  - 与 signal_router 兼容 (v1=regex, v2=L3 评分)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "projects/omo/src"))


@dataclass
class RouteScore:
    scene: str
    type_match: float  # 0~1
    urgency: float     # 0~1
    quality: float     # 0~1
    total: float       # 加权总分

    def to_dict(self) -> dict:
        return {"scene": self.scene, "type": round(self.type_match, 2),
                "urgency": round(self.urgency, 2), "quality": round(self.quality, 2),
                "total": round(self.total, 2)}


# 场景 → 关键词映射 (type_match 评分)
SCENE_KEYWORDS = {
    "document-review": {"review", "公文", "审查", "格式", "敏感", "依据", "report", "draft"},
    "meeting-supervision": {"meeting", "会议", "决议", "纪要", "action-item", "follow-up"},
    "research-pipeline": {"research", "调研", "query", "研究", "paper", "文献", "hypothesis"},
    "engineering-delivery": {".py", ".ts", ".go", "pr_", "merge", "code", "refactor"},
    "knowledge-ingest": {"insight", "note", "experience", "lesson", "knowledge", "tip"},
}

URGENCY_KEYWORDS = {"紧急", "asap", "urgent", "今天", "now", "deadline", "截止",
                    "due", "expedite", "blocker"}

SCENES = ["document-review", "meeting-supervision", "research-pipeline",
          "engineering-delivery", "knowledge-ingest"]

# 权重
W_TYPE = 0.5
W_URGENCY = 0.2
W_QUALITY = 0.3


def score_type(name: str, content: str) -> dict[str, float]:
    """每个场景的类型匹配分."""
    text = f"{name} {content[:1000]}".lower()
    scores = {}
    for scene, kws in SCENE_KEYWORDS.items():
        hits = sum(1 for kw in kws if kw.lower() in text)
        scores[scene] = min(1.0, hits / 2)  # 2+ 命中 = 满分
    return scores


def score_urgency(content: str) -> float:
    """紧急度评分 (0~1)."""
    text = content.lower()
    hits = sum(1 for kw in URGENCY_KEYWORDS if kw in text)
    return min(1.0, hits / 2)


def score_quality(content: str) -> float:
    """内容质量评分 (长度 + 关键词密度)."""
    if not content.strip():
        return 0.0
    length_score = min(1.0, len(content) / 1000)  # 1000字 = 满分
    # 因果关键词 (与方法/原因/结果/注意 匹配加分)
    causal = sum(1 for kw in ["因为", "方法", "结果", "注意", "因为", "due to", "method", "result"]
                 if kw in content.lower())
    causal_score = min(1.0, causal / 2)
    return (length_score + causal_score) / 2


def route(file_path: Path, content: str) -> tuple[str, list[RouteScore], dict]:
    """L3 智能路由 — 返回 (最佳场景, 所有分数, 解释)."""
    name = file_path.name
    type_scores = score_type(name, content)
    urgency = score_urgency(content)
    quality = score_quality(content)
    # 加权总分
    scores: list[RouteScore] = []
    for scene in SCENES:
        s = type_scores.get(scene, 0.0)
        total = W_TYPE * s + W_URGENCY * urgency + W_QUALITY * quality
        scores.append(RouteScore(scene=scene, type_match=s, urgency=urgency, quality=quality, total=total))
    # 选最高分 (tie-break 按 SCENES 顺序)
    scores.sort(key=lambda x: (-x.total, SCENES.index(x.scene)))
    best = scores[0]
    explanation = {
        "scoring_model": "l3_smart_router_v1",
        "weights": {"type": W_TYPE, "urgency": W_URGENCY, "quality": W_QUALITY},
        "urgency": round(urgency, 2),
        "quality": round(quality, 2),
        "type_scores": {k: round(v, 2) for k, v in type_scores.items()},
        "all_scores": [s.to_dict() for s in scores],
    }
    return best.scene, scores, explanation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="信号文件路径")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    f = Path(args.file)
    if not f.exists():
        print(f"file not found: {f}")
        return 1
    content = f.read_text(encoding="utf-8", errors="ignore")
    best, scores, explanation = route(f, content)
    if args.json:
        print(json.dumps({"best_scene": best, "explanation": explanation}, indent=2, ensure_ascii=False))
    else:
        print(f"最佳路由: {best}")
        for s in scores:
            print(f"  {s.scene:25s} 总分 {s.total:.2f} (type={s.type_match:.2f}, urgency={s.urgency:.2f}, quality={s.quality:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())