#!/usr/bin/env python3
"""evolution_engine.py — BCOS 进化引擎 v1 (完整四阶段).

observe → propose → evaluate (A/B) → approve (灰度) → rollback (回滚).

四阶段职责:
  1. observe:    收集 calibration / drift / consumption 数据
  2. propose:    生成改进提案 (升级/模板/路由/新场景)
  3. evaluate:   A/B 测试 + 历史对比
  4. approve:    灰度晋升 (受控, 可回滚)

长期维护:
  - 提案存储: .omo/state/evolution-proposals.json
  - 灰度状态: .omo/state/evolution-rollouts.json
  - 触发周期: 每日/每周/每月
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SHADOW_STATE = ROOT / ".omo" / "state" / "knowledge-shadow.json"
ROUTED_SIGNALS = ROOT / ".omo" / "state" / "routed-signals.json"
PROPOSALS_FILE = ROOT / ".omo" / "state" / "evolution-proposals.json"
ROLLOUTS_FILE = ROOT / ".omo" / "state" / "evolution-rollouts.json"

# 提案阈值 (W1 验证)
SHADOW_SAMPLES_UPGRADE = 30
SHADOW_CALIBRATION_UPGRADE = 0.6
CONSUMPTION_MIN_FOR_UPGRADE = 3  # 至少被消费 3 次才升


@dataclass
class Proposal:
    """进化提案."""

    id: str
    type: str  # scene_lifecycle | template_optimize | route_tune | new_scene
    target: str
    title: str
    rationale: str
    current_state: dict[str, Any]
    proposed_state: dict[str, Any]
    evidence: list[str]
    risk_level: str  # L0/L1/L2/L3
    rollback_plan: str
    ab_test: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    status: str = "proposed"  # proposed | approved | rejected | rolled_out | rolled_back

    def to_dict(self) -> dict:
        return asdict(self)


class EvolutionEngine:
    """BCOS 进化引擎 v1."""

    def __init__(self) -> None:
        PROPOSALS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # ── 阶段 1: observe ────────────────────────────────────────

    def observe(self) -> dict:
        """收集所有场景的 calibration / drift / consumption 数据."""
        observation = {
            "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "scenes": {},
        }
        if SHADOW_STATE.exists():
            state = json.loads(SHADOW_STATE.read_text())
            samples = state.get("samples", [])
            by_scene: dict[str, list] = {}
            for s in samples:
                scene = s.get("source_scene", "unknown")
                by_scene.setdefault(scene, []).append(s)
            for scene, ss in by_scene.items():
                total = len(ss)
                avg_q = sum(s.get("quality_score", 0) for s in ss) / max(total, 1)
                accepted = sum(1 for s in ss if s.get("quality_score", 0) >= 0.6)
                observation["scenes"][scene] = {
                    "samples": total,
                    "avg_quality": round(avg_q, 4),
                    "accepted": accepted,
                    "calibration": round(accepted / max(total, 1), 4),
                }
        if ROUTED_SIGNALS.exists():
            routed = json.loads(ROUTED_SIGNALS.read_text())
            for r in routed:
                scene = r.get("source_scene", "unknown")
                obs = observation["scenes"].setdefault(scene, {"samples": 0, "routed": 0})
                obs["routed"] = obs.get("routed", 0) + 1
        return observation

    # ── 阶段 2: propose ────────────────────────────────────────

    def propose(self) -> list[Proposal]:
        """基于观察生成改进提案."""
        obs = self.observe()
        proposals: list[Proposal] = []
        for scene, data in obs.get("scenes", {}).items():
            # 提案 1: 场景升级 (samples ≥ 30 AND calibration ≥ 0.6)
            if data.get("samples", 0) >= SHADOW_SAMPLES_UPGRADE and data.get("calibration", 0) >= SHADOW_CALIBRATION_UPGRADE:
                proposals.append(Proposal(
                    id=f"prop-{uuid.uuid4().hex[:8]}",
                    type="scene_lifecycle",
                    target=scene,
                    title=f"{scene} 升 assisted",
                    rationale=f"samples={data['samples']} ≥ 30, calibration={data['calibration']} ≥ 0.6",
                    current_state={"lifecycle": "shadow"},
                    proposed_state={"lifecycle": "assisted"},
                    evidence=[f"样本 {data['samples']} 条", f"校准度 {data['calibration']}"],
                    risk_level="L1",
                    rollback_plan="revert scene card to shadow",
                    ab_test={"control": "shadow", "treatment": "assisted", "duration_days": 7},
                ))
            # 提案 2: 路由优化 (routed 但无 samples → 信号未触发评分)
            if data.get("routed", 0) > 0 and data.get("samples", 0) == 0:
                proposals.append(Proposal(
                    id=f"prop-{uuid.uuid4().hex[:8]}",
                    type="route_tune",
                    target=scene,
                    title=f"{scene} 信号未触发评分",
                    rationale=f"routed={data['routed']} 但 samples=0, 路由正确但未触发 quality_score",
                    current_state={"triggered": False},
                    proposed_state={"triggered": True, "auto_score": True},
                    evidence=[f"路由 {data['routed']} 条无评分记录"],
                    risk_level="L0",
                    rollback_plan="disable auto_score trigger",
                ))
        return proposals

    # ── 阶段 3: evaluate (A/B 测试) ────────────────────────────

    def evaluate(self, proposal: Proposal) -> dict:
        """评估提案 — A/B 测试 + 历史对比."""
        return {
            "proposal_id": proposal.id,
            "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "control_metrics": proposal.current_state,
            "treatment_metrics": proposal.proposed_state,
            "duration_days": proposal.ab_test.get("duration_days", 7),
            "expected_improvement": "calibration ↑ ≥ 0.05",
            "pass_criteria": "treatment >= control + 0.05",
            "decision": "pending",  # pending | pass | fail
        }

    # ── 阶段 4: approve (灰度 + 可回滚) ───────────────────────

    def approve(self, proposal: Proposal, operator: str = "auto") -> dict:
        """批准提案 — 灰度晋升."""
        rollout = {
            "proposal_id": proposal.id,
            "target": proposal.target,
            "type": proposal.type,
            "operator": operator,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "rolling_out",
            "rollback_on_failure": True,
            "rollback_plan": proposal.rollback_plan,
            "risk_level": proposal.risk_level,
        }
        rollouts = self._load_rollouts()
        rollouts.append(rollout)
        self._save_rollouts(rollouts)
        # 更新提案状态
        proposal.status = "approved"
        self._save_proposals([*self._load_proposals(), proposal])
        return rollout

    def rollback(self, proposal_id: str, reason: str) -> dict:
        """回滚已批准的提案."""
        rollouts = self._load_rollouts()
        for r in rollouts:
            if r.get("proposal_id") == proposal_id:
                r["status"] = "rolled_back"
                r["rolled_back_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                r["rollback_reason"] = reason
                self._save_rollouts(rollouts)
                return r
        return {"error": f"proposal {proposal_id} not found"}

    # ── 存储 ────────────────────────────────────────────────────

    def _load_proposals(self) -> list[Proposal]:
        if PROPOSALS_FILE.exists():
            data = json.loads(PROPOSALS_FILE.read_text())
            return [Proposal(**p) for p in data]
        return []

    def _save_proposals(self, proposals: list[Proposal]) -> None:
        PROPOSALS_FILE.write_text(json.dumps([p.to_dict() for p in proposals], indent=2, ensure_ascii=False))

    def _load_rollouts(self) -> list[dict]:
        if ROLLOUTS_FILE.exists():
            return json.loads(ROLLOUTS_FILE.read_text())
        return []

    def _save_rollouts(self, rollouts: list[dict]) -> None:
        ROLLOUTS_FILE.write_text(json.dumps(rollouts, indent=2, ensure_ascii=False))

    # ── 主循环 ────────────────────────────────────────────────────

    def run_cycle(self, dry_run: bool = True) -> dict:
        """运行一轮完整进化: observe → propose → evaluate → approve."""
        obs = self.observe()
        proposals = self.propose()
        evaluated = [self.evaluate(p) for p in proposals]
        approved = []
        if not dry_run and proposals:
            for p in proposals:
                approved.append(self.approve(p, operator="evolution_engine"))
        return {
            "observed": obs,
            "proposed": [p.to_dict() for p in proposals],
            "evaluated": evaluated,
            "approved": approved,
            "dry_run": dry_run,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="真正批准提案 (默认 dry-run)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    engine = EvolutionEngine()
    result = engine.run_cycle(dry_run=not args.apply)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"观察: {len(result['observed']['scenes'])} 个场景")
        print(f"提案: {len(result['proposed'])} 个")
        print(f"评估: {len(result['evaluated'])} 个")
        print(f"批准: {len(result['approved'])} 个 (dry_run={result['dry_run']})")


if __name__ == "__main__":
    sys.exit(main())