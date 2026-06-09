"""
model_driven.lifecycle.pipeline — 三阶段宏观流水线

在 7 阶段之上增加更高层次的抽象：
- Phase 1: ColdStart (规划 + 设计) — 系统冷启动与骨干建网
- Phase 2: Evolution (开发 + 部署) — 长周期运行与 ADR 自演进
- Phase 3: Hardening (运行 + 运维 + 运营) — 架构硬化与持续优化

7 阶段与 3 Phase 的映射:
  Planning ─┐
            ├── Phase 1: ColdStart
  Design   ─┘

  Development ─┐
               ├── Phase 2: Evolution
  Deployment  ─┘

  Runtime      ─┐
  Operations   ─├── Phase 3: Hardening
  BusinessOps ─┘
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from model_driven.mof.m3_extended import LifecycleStage
from model_driven.lifecycle.stages import LifecycleTracker, StageStatus
from model_driven.lifecycle.gates import GateEngine, GateResult


class PipelinePhase(Enum):
    """三阶段宏观流水线"""

    COLD_START = "cold_start"  # 冷启动: 规划+设计
    EVOLUTION = "evolution"  # 演进: 开发+部署
    HARDENING = "hardening"  # 硬化: 运行+运维+运营

    @classmethod
    def from_stage(cls, stage: LifecycleStage) -> "PipelinePhase":
        """从 7 阶段映射到 3 Phase"""
        mapping = {
            LifecycleStage.PLANNING: cls.COLD_START,
            LifecycleStage.DESIGN: cls.COLD_START,
            LifecycleStage.DEVELOPMENT: cls.EVOLUTION,
            LifecycleStage.DEPLOYMENT: cls.EVOLUTION,
            LifecycleStage.RUNTIME: cls.HARDENING,
            LifecycleStage.OPERATIONS: cls.HARDENING,
            LifecycleStage.BUSINESS_OPS: cls.HARDENING,
        }
        return mapping.get(stage, cls.EVOLUTION)

    @classmethod
    def get_stages(cls, phase: "PipelinePhase") -> list[LifecycleStage]:
        """获取 Phase 包含的 7 阶段列表"""
        mapping = {
            cls.COLD_START: [LifecycleStage.PLANNING, LifecycleStage.DESIGN],
            cls.EVOLUTION: [LifecycleStage.DEVELOPMENT, LifecycleStage.DEPLOYMENT],
            cls.HARDENING: [LifecycleStage.RUNTIME, LifecycleStage.OPERATIONS, LifecycleStage.BUSINESS_OPS],
        }
        return mapping.get(phase, [])


class PhaseStatus(Enum):
    """Phase 运行状态"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class PhaseInstance:
    """Phase 实例"""

    phase: PipelinePhase
    status: PhaseStatus = PhaseStatus.NOT_STARTED
    started_at: str = ""
    completed_at: str = ""
    deliverables: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def start(self) -> None:
        self.status = PhaseStatus.IN_PROGRESS
        self.started_at = datetime.now(timezone.utc).isoformat()

    def complete(self) -> None:
        self.status = PhaseStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def block(self, reason: str) -> None:
        self.status = PhaseStatus.BLOCKED
        self.issues.append(reason)


@dataclass
class PhaseGate:
    """Phase 间门禁"""

    id: str
    name: str
    from_phase: PipelinePhase
    to_phase: PipelinePhase
    conditions: list[str] = field(default_factory=list)
    auto_pass: bool = False


# ── 标准 Phase 门禁 ──────────────────────────────────

STANDARD_PHASE_GATES = [
    PhaseGate(
        id="PHASE-GATE-COLDSTART-TO-EVOLUTION",
        name="冷启动→演进 门禁",
        from_phase=PipelinePhase.COLD_START,
        to_phase=PipelinePhase.EVOLUTION,
        conditions=[
            "OKR 已审批",
            "Spec 已批准",
            "关键 ADR 已记录",
            "接口契约已定义",
            "设计评审通过",
        ],
    ),
    PhaseGate(
        id="PHASE-GATE-EVOLUTION-TO-HARDENING",
        name="演进→硬化 门禁",
        from_phase=PipelinePhase.EVOLUTION,
        to_phase=PipelinePhase.HARDENING,
        conditions=[
            "测试通过率 >= 95%",
            "CI 绿灯",
            "部署成功",
            "冒烟测试通过",
            "监控已配置",
        ],
    ),
]


class PipelineTracker:
    """三阶段宏观流水线追踪器"""

    def __init__(self, entity_id: str, entity_type: str = ""):
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.phases: dict[PipelinePhase, PhaseInstance] = {
            phase: PhaseInstance(phase=phase)
            for phase in PipelinePhase
        }
        self.current_phase: PipelinePhase | None = None
        self.lifecycle_tracker: LifecycleTracker = LifecycleTracker(entity_id=entity_id, entity_type=entity_type)
        self._phase_gates = STANDARD_PHASE_GATES
        self._history: list[dict[str, Any]] = []

    def start_phase(self, phase: PipelinePhase) -> bool:
        """开始一个 Phase"""
        # 检查前置 Phase
        if phase == PipelinePhase.EVOLUTION:
            if self.phases[PipelinePhase.COLD_START].status != PhaseStatus.COMPLETED:
                return False
        elif phase == PipelinePhase.HARDENING:
            if self.phases[PipelinePhase.EVOLUTION].status != PhaseStatus.COMPLETED:
                return False

        self.current_phase = phase
        self.phases[phase].start()

        # 自动启动 Phase 内的第一个 7 阶段
        stages = PipelinePhase.get_stages(phase)
        if stages:
            self.lifecycle_tracker.advance_to(stages[0])

        self._history.append({
            "action": "start_phase",
            "phase": phase.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return True

    def complete_phase(self, phase: PipelinePhase) -> bool:
        """完成一个 Phase"""
        if self.phases[phase].status != PhaseStatus.IN_PROGRESS:
            return False

        # 检查 Phase 内所有 7 阶段是否完成
        stages = PipelinePhase.get_stages(phase)
        for stage in stages:
            instance = self.lifecycle_tracker.stages[stage]
            if instance.status not in (StageStatus.COMPLETED, StageStatus.SKIPPED):
                return False

        self.phases[phase].complete()
        self._history.append({
            "action": "complete_phase",
            "phase": phase.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return True

    def check_phase_gate(self, from_phase: PipelinePhase, to_phase: PipelinePhase, context: dict[str, Any] | None = None) -> tuple[bool, str]:
        """检查 Phase 间门禁"""
        for gate in self._phase_gates:
            if gate.from_phase == from_phase and gate.to_phase == to_phase:
                if gate.auto_pass:
                    return True, "自动通过"

                # 检查条件
                context = context or {}
                failed = []
                for condition in gate.conditions:
                    if condition not in context or not context[condition]:
                        failed.append(condition)

                if failed:
                    return False, f"未满足条件: {', '.join(failed)}"
                return True, "门禁通过"

        return True, "无门禁"

    def get_current_stage_in_phase(self) -> LifecycleStage | None:
        """获取当前 Phase 内所处的 7 阶段"""
        return self.lifecycle_tracker.current_stage

    def advance_stage_in_phase(self) -> bool:
        """在当前 Phase 内推进到下一个 7 阶段"""
        if not self.current_phase:
            return False

        current = self.lifecycle_tracker.current_stage
        if not current:
            return False

        stages = PipelinePhase.get_stages(self.current_phase)
        try:
            idx = stages.index(current)
            if idx + 1 < len(stages):
                return self.lifecycle_tracker.advance_to(stages[idx + 1])
        except ValueError:
            pass

        return False

    def get_progress(self) -> dict[str, Any]:
        """获取三阶段宏观进度"""
        phase_progress = {}
        for phase in PipelinePhase:
            stages = PipelinePhase.get_stages(phase)
            completed = sum(
                1 for s in stages
                if self.lifecycle_tracker.stages[s].status == StageStatus.COMPLETED
            )
            phase_progress[phase.value] = {
                "status": self.phases[phase].status.value,
                "stages_completed": completed,
                "stages_total": len(stages),
                "progress_pct": round(completed / len(stages) * 100, 1) if stages else 0,
            }

        lifecycle_progress = self.lifecycle_tracker.get_progress()

        return {
            "entity_id": self.entity_id,
            "current_phase": self.current_phase.value if self.current_phase else "not_started",
            "phases": phase_progress,
            "lifecycle": lifecycle_progress,
            "overall_progress": lifecycle_progress["progress_pct"],
        }

    # ── 状态持久化 ──────────────────────────────────

    def save(self, state_dir: str | None = None) -> bool:
        """将 PipelineTracker 状态持久化到文件

        Args:
            state_dir: 状态目录，默认 ~/Workspace/.omo/state/model-driven/
        """
        from pathlib import Path

        if state_dir is None:
            state_dir = str(Path.home() / "Workspace" / ".omo" / "state" / "model-driven")

        state_path = Path(state_dir)
        state_path.mkdir(parents=True, exist_ok=True)

        file_path = state_path / f"{self.entity_id}-pipeline.yaml"
        try:
            import yaml
            data = {
                "entity_id": self.entity_id,
                "entity_type": self.entity_type,
                "current_phase": self.current_phase.value if self.current_phase else None,
                "phases": {
                    p.value: {
                        "status": self.phases[p].status.value,
                        "started_at": self.phases[p].started_at,
                        "completed_at": self.phases[p].completed_at,
                        "issues": self.phases[p].issues,
                    }
                    for p in PipelinePhase
                },
                "lifecycle_stages": {
                    s.value: {
                        "status": self.lifecycle_tracker.stages[s].status.value,
                        "started_at": self.lifecycle_tracker.stages[s].started_at,
                        "completed_at": self.lifecycle_tracker.stages[s].completed_at,
                    }
                    for s in LifecycleStage
                },
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(file_path, "w") as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            return True
        except Exception:
            return False

    @classmethod
    def load(cls, entity_id: str, state_dir: str | None = None) -> "PipelineTracker | None":
        """从文件加载 PipelineTracker 状态

        Args:
            entity_id: 实体 ID
            state_dir: 状态目录，默认 ~/Workspace/.omo/state/model-driven/
        """
        from pathlib import Path

        if state_dir is None:
            state_dir = str(Path.home() / "Workspace" / ".omo" / "state" / "model-driven")

        file_path = Path(state_dir) / f"{entity_id}-pipeline.yaml"
        if not file_path.exists():
            return None

        try:
            import yaml
            with open(file_path) as f:
                data = yaml.safe_load(f)

            tracker = cls(entity_id=data.get("entity_id", entity_id),
                          entity_type=data.get("entity_type", ""))

            # 恢复 Phase 状态
            for phase in PipelinePhase:
                phase_data = data.get("phases", {}).get(phase.value, {})
                if phase_data.get("status") == "in_progress":
                    tracker.phases[phase].status = PhaseStatus.IN_PROGRESS
                    tracker.phases[phase].started_at = phase_data.get("started_at", "")
                    tracker.current_phase = phase
                elif phase_data.get("status") == "completed":
                    tracker.phases[phase].status = PhaseStatus.COMPLETED
                    tracker.phases[phase].started_at = phase_data.get("started_at", "")
                    tracker.phases[phase].completed_at = phase_data.get("completed_at", "")
                if phase_data.get("issues"):
                    tracker.phases[phase].issues = phase_data["issues"]

            # 恢复 Lifecycle 阶段状态
            for stage in LifecycleStage:
                stage_data = data.get("lifecycle_stages", {}).get(stage.value, {})
                if stage_data.get("status") == "completed":
                    tracker.lifecycle_tracker.stages[stage].status = StageStatus.COMPLETED
                    tracker.lifecycle_tracker.stages[stage].completed_at = stage_data.get("completed_at", "")
                    tracker.lifecycle_tracker.stages[stage].started_at = stage_data.get("started_at", "")
                elif stage_data.get("status") == "in_progress":
                    tracker.lifecycle_tracker.stages[stage].status = StageStatus.IN_PROGRESS
                    tracker.lifecycle_tracker.stages[stage].started_at = stage_data.get("started_at", "")

            return tracker
        except Exception as e:
            import sys
            print(f"[model-driven] PipelineTracker.load({entity_id}) 失败: {e}", file=sys.stderr)
            return None
