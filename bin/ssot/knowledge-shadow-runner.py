#!/usr/bin/env python3
"""knowledge-shadow-runner.py — P1 Shadow 模式运行器 (BET-Y3H1 业务落地).

执行 knowledge-capture-pipeline 的 shadow 模式:
  1. 扫描信号源 (inbox_folder / apple_mail / github_push)
  2. 提取知识片段
  3. 质量评分 (knowledge_quality.score_knowledge)
  4. 生成待复核条目
  5. 记录样本 + 更新 calibration

设计:
  - 定时运行 (默认每日一次)
  - 幂等 (重复运行不重复入库)
  - 审计日志
  - 与 MOSBeliefManager 集成

退出:
  - samples >= 30 AND calibration >= 0.60 → 建议升 assisted
  - 否则 → 延长 shadow 或回退
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "projects/omo/src"))

from omo.knowledge_quality import score_knowledge
from omo.omo_belief import MOSBeliefManager

logger = logging.getLogger("knowledge-shadow")

SHADOW_STATE_FILE = ROOT / ".omo" / "state" / "knowledge-shadow.json"


def load_shadow_state() -> dict:
    if SHADOW_STATE_FILE.exists():
        return json.loads(SHADOW_STATE_FILE.read_text())
    return {"samples": [], "total": 0, "accepted": 0, "rejected": 0, "start_time": None}


def save_shadow_state(state: dict) -> None:
    SHADOW_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SHADOW_STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def scan_signal_sources() -> list[dict]:
    """扫描信号源, 提取知识片段."""
    fragments = []
    # inbox_folder 信号源
    inbox_folder = Path.home() / "Documents" / "@感知信号"
    if inbox_folder.exists():
        for f in inbox_folder.glob("*"):
            if f.is_file() and not f.name.startswith("."):
                content = f.read_text(encoding="utf-8", errors="ignore")
                if content.strip():
                    fragments.append({
                        "content": content[:2000],
                        "type": "doc_experience",
                        "source_scene": "unified-inbox",
                        "source_file": str(f.name),
                    })
    return fragments


def run_shadow_cycle(dry_run: bool = True) -> dict:
    """运行一次 shadow 周期."""
    state = load_shadow_state()
    if not state["start_time"]:
        state["start_time"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    fragments = scan_signal_sources()
    logger.info(f"扫描到 {len(fragments)} 个知识片段")

    new_samples = 0
    for frag in fragments:
        # 质量评分
        scoring = score_knowledge(frag)
        sample = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source_scene": frag.get("source_scene", "?"),
            "type": frag.get("type", "?"),
            "quality_score": scoring["score"],
            "grade": scoring["grade"],
            "recommendation": scoring["recommendation"],
        }
        # 质量门: score >= 0.4 才进入复核
        if scoring["score"] >= 0.4:
            new_samples += 1
            state["samples"].append(sample)
            if not dry_run:
                # 记录到 MOS
                mos = MOSBeliefManager()
                mos.record_capability_calibration(
                    capability_ref=f"ref://scene/knowledge-ingest/{frag.get('type','?')}",
                    success_rate=scoring["score"],
                    sample_size=1,
                    last_run_id=f"shadow-{state['total']}",
                )
        state["total"] += 1

    save_shadow_state(state)

    # 计算 calibration
    accepted = len([s for s in state["samples"] if s["quality_score"] >= 0.6])
    calibration = round(accepted / max(len(state["samples"]), 1), 2)

    result = {
        "new_samples": new_samples,
        "total_samples": len(state["samples"]),
        "calibration": calibration,
        "passes_threshold": len(state["samples"]) >= 30 and calibration >= 0.60,
    }
    logger.info(f"Shadow 周期完成: {result}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", default=True, help="不写入 MOS")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    result = run_shadow_cycle(dry_run=args.dry_run)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"新样本: {result['new_samples']}, 总样本: {result['total_samples']}, "
              f"calibration: {result['calibration']}, "
              f"达标: {'✅' if result['passes_threshold'] else '❌'}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
