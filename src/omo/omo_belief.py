#!/usr/bin/env python3
"""
projects/omo/src/omo/omo_belief.py — MOS Agent Belief 三表 Schema 与写入持久化工具 (BET-Y1Q1-T3-01)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .omo_io import write_yaml_atomic
from .omo_paths import WORKSPACE_ROOT
from .omo_shared import load_yaml_value


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class AgentBelief:
    id: str
    topic: str
    belief: str
    created_at: str = field(default_factory=_utc_now)
    confidence: float = 1.0
    source_run_id: str | None = None


@dataclass
class AgentLesson:
    id: str
    belief_id: str
    pitfall: str
    solution: str
    severity: str = "warning"
    created_at: str = field(default_factory=_utc_now)


@dataclass
class AgentContext:
    id: str
    belief_id: str
    scope_path: str
    applicable_tags: list[str] = field(default_factory=list)


@dataclass
class WorldSnapshot:
    """世界模型 — agent 对外部世界状态的观察快照"""

    id: str
    observed_at: str = field(default_factory=_utc_now)
    source: str = ""
    domain: str = ""
    observations: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    expires_at: str | None = None


@dataclass
class CapabilityCalibration:
    """自我模型 — agent 对自身能力的实测校准"""

    id: str
    capability_ref: str = ""
    measured_at: str = field(default_factory=_utc_now)
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    sample_size: int = 0
    last_run_id: str | None = None


@dataclass
class DecisionOutcome:
    """因果模型 — 决策→结果的因果追踪"""

    id: str
    decision_at: str = field(default_factory=_utc_now)
    decision_type: str = ""
    input_summary: str = ""
    expected_outcome: str = ""
    actual_outcome: str = ""
    delta: str = ""
    source_run_id: str | None = None


class MOSBeliefManager:
    """MOS agent_belief 三表持久化与查询管理器"""

    def __init__(self, root: Path | None = None):
        self.root = root or WORKSPACE_ROOT
        self.registry_file = (
            self.root / ".omo" / "_truth" / "registry" / "memory-os.yaml"
        )
        self.state_dir = self.root / ".omo" / "state" / "agent-beliefs"
        self.state_file = self.state_dir / "index.yaml"
        self.audit_log_file = self.state_dir / "audit.log"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _load_registry(self) -> dict[str, Any]:
        if not self.registry_file.exists():
            return {}
        return load_yaml_value(self.registry_file) or {}

    def _append_audit_log(self, action: str, details: str) -> None:
        """追加写入审计日志流"""
        log_line = f"[{_utc_now()}] ACTION={action} DETAILS={details}\n"
        with self.audit_log_file.open("a", encoding="utf-8") as f:
            f.write(log_line)

    def _load_state(self) -> dict[str, list[dict[str, Any]]]:
        if not self.state_file.exists():
            return {
                "beliefs": [],
                "lessons": [],
                "contexts": [],
                "world_snapshots": [],
                "capability_calibrations": [],
                "decision_outcomes": [],
                "agent_skills": [],
                "agent_experiences": [],
            }
        data = load_yaml_value(self.state_file) or {}
        return {
            "beliefs": data.get("beliefs", []),
            "lessons": data.get("lessons", []),
            "contexts": data.get("contexts", []),
            "world_snapshots": data.get("world_snapshots", []),
            "capability_calibrations": data.get("capability_calibrations", []),
            "decision_outcomes": data.get("decision_outcomes", []),
            "agent_skills": data.get("agent_skills", []),
            "agent_experiences": data.get("agent_experiences", []),
        }

    def record_belief(
        self,
        topic: str,
        belief_text: str,
        pitfall: str | None = None,
        solution: str | None = None,
        scope_path: str = "*",
        source_run_id: str | None = None,
    ) -> str:
        """记录新的 Agent Belief 及关联的 Lesson 与 Context"""
        state = self._load_state()
        b_id = f"belief-{len(state['beliefs']) + 1:04d}"

        belief_entry = AgentBelief(
            id=b_id,
            topic=topic,
            belief=belief_text,
            source_run_id=source_run_id,
        )
        state["beliefs"].append(asdict(belief_entry))

        if pitfall and solution:
            l_id = f"lesson-{len(state['lessons']) + 1:04d}"
            lesson_entry = AgentLesson(
                id=l_id,
                belief_id=b_id,
                pitfall=pitfall,
                solution=solution,
            )
            state["lessons"].append(asdict(lesson_entry))

        c_id = f"ctx-{len(state['contexts']) + 1:04d}"
        ctx_entry = AgentContext(
            id=c_id,
            belief_id=b_id,
            scope_path=scope_path,
            applicable_tags=[topic],
        )
        state["contexts"].append(asdict(ctx_entry))

        # 原子落盘写入
        write_yaml_atomic(self.state_file, state)
        self._update_registry_summary(len(state["beliefs"]), state)
        self._append_audit_log(
            "RECORD_BELIEF", f"id={b_id} topic={topic} run_id={source_run_id}"
        )
        self._try_auto_crystallize(topic, state)
        return b_id

    def _try_auto_crystallize(
        self, topic: str, state: dict[str, list[dict[str, Any]]]
    ) -> None:
        """Best-effort: 当 topic 信念数 >= 2 时自动结晶为 Skill (BET-Y1Q2-T6-06)."""
        try:
            from .omo_crystallizer import CRYSTALLIZATION_THRESHOLD, SkillCrystallizer

            topic_beliefs = [b for b in state["beliefs"] if b.get("topic") == topic]
            if len(topic_beliefs) < CRYSTALLIZATION_THRESHOLD:
                return
            crystallizer = SkillCrystallizer()
            crystallizer.check_and_crystallize(
                beliefs=state["beliefs"],
                lessons=state.get("lessons", []),
                contexts=state.get("contexts", []),
                topic=topic,
            )
            self._append_audit_log(
                "AUTO_CRYSTALLIZE",
                f"topic={topic} count={len(topic_beliefs)}",
            )
        except Exception:
            pass

    def _update_registry_summary(
        self, total_beliefs: int, state: dict | None = None
    ) -> None:
        """同步更新注册表元数据汇总"""
        registry_data = self._load_registry()
        registry_data["schema"] = "memory-os/v1"
        registry_data["as_of"] = _utc_now()
        registry_data["total_beliefs"] = total_beliefs
        registry_data["tables"] = [
            "agent_belief",
            "agent_lesson",
            "agent_context",
            "world_snapshot",
            "capability_calibration",
            "decision_outcome",
        ]
        if state:
            registry_data["total_world_snapshots"] = len(
                state.get("world_snapshots", [])
            )
            registry_data["total_capability_calibrations"] = len(
                state.get("capability_calibrations", [])
            )
            registry_data["total_decision_outcomes"] = len(
                state.get("decision_outcomes", [])
            )
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        write_yaml_atomic(self.registry_file, registry_data)

    def query_beliefs(self, keyword: str | None = None) -> list[dict[str, Any]]:
        """按关键词查询适合的 Agent 信念与教训"""
        state = self._load_state()
        if not keyword:
            return state["beliefs"]

        kw = keyword.lower()
        matched = []
        for b in state["beliefs"]:
            if kw in b["topic"].lower() or kw in b["belief"].lower():
                matched.append(b)
        return matched

    def record_world_snapshot(
        self,
        source: str,
        domain: str,
        observations: dict[str, Any],
        confidence: float = 1.0,
        expires_at: str | None = None,
    ) -> str:
        """记录世界模型快照 — agent 对外部状态的观察"""
        state = self._load_state()
        ws_id = f"ws-{len(state['world_snapshots']) + 1:04d}"
        entry = WorldSnapshot(
            id=ws_id,
            source=source,
            domain=domain,
            observations=observations,
            confidence=confidence,
            expires_at=expires_at,
        )
        state["world_snapshots"].append(asdict(entry))
        write_yaml_atomic(self.state_file, state)
        self._update_registry_summary(len(state["beliefs"]), state)
        self._append_audit_log(
            "RECORD_WORLD_SNAPSHOT", f"id={ws_id} domain={domain} source={source}"
        )
        return ws_id

    def record_capability_calibration(
        self,
        capability_ref: str,
        success_rate: float,
        avg_latency_ms: float = 0.0,
        sample_size: int = 1,
        last_run_id: str | None = None,
    ) -> str:
        """记录自我模型校准 — agent 对自身能力的实测"""
        state = self._load_state()
        cc_id = f"cc-{len(state['capability_calibrations']) + 1:04d}"
        entry = CapabilityCalibration(
            id=cc_id,
            capability_ref=capability_ref,
            success_rate=success_rate,
            avg_latency_ms=avg_latency_ms,
            sample_size=sample_size,
            last_run_id=last_run_id,
        )
        state["capability_calibrations"].append(asdict(entry))
        write_yaml_atomic(self.state_file, state)
        self._update_registry_summary(len(state["beliefs"]), state)
        self._append_audit_log(
            "RECORD_CAPABILITY_CALIBRATION",
            f"id={cc_id} ref={capability_ref} rate={success_rate}",
        )
        return cc_id

    def record_decision_outcome(
        self,
        decision_type: str,
        input_summary: str,
        expected_outcome: str,
        actual_outcome: str,
        delta: str = "",
        source_run_id: str | None = None,
    ) -> str:
        """记录因果模型 — 决策→结果的因果追踪"""
        state = self._load_state()
        do_id = f"do-{len(state['decision_outcomes']) + 1:04d}"
        entry = DecisionOutcome(
            id=do_id,
            decision_type=decision_type,
            input_summary=input_summary,
            expected_outcome=expected_outcome,
            actual_outcome=actual_outcome,
            delta=delta,
            source_run_id=source_run_id,
        )
        state["decision_outcomes"].append(asdict(entry))
        write_yaml_atomic(self.state_file, state)
        self._update_registry_summary(len(state["beliefs"]), state)
        self._append_audit_log(
            "RECORD_DECISION_OUTCOME",
            f"id={do_id} type={decision_type} run={source_run_id}",
        )
        return do_id

    def get_decision_outcome(self, do_id: str) -> dict[str, Any] | None:
        """按 ID 查找 decision_outcome 记录 (闭环: adjudication → belief)."""
        state = self._load_state()
        for do in state["decision_outcomes"]:
            if do["id"] == do_id:
                return do
        return None

    def update_belief_confidence(
        self,
        belief_id: str,
        delta: float,
        *,
        reason: str = "",
    ) -> float:
        """调整信念置信度 (闭环: 裁决反馈 → 信念修正).

        Args:
            belief_id: 目标信念 ID (belief-NNNN).
            delta: 置信度变化量 (正=增强, 负=削弱).
            reason: 调整原因 (审计用).

        Returns:
            调整后的置信度.
        """
        state = self._load_state()
        for b in state["beliefs"]:
            if b["id"] == belief_id:
                old = b.get("confidence", 1.0)
                new = max(0.0, min(1.0, old + delta))
                b["confidence"] = new
                write_yaml_atomic(self.state_file, state)
                self._append_audit_log(
                    "UPDATE_BELIEF_CONFIDENCE",
                    f"id={belief_id} {old:.2f}→{new:.2f} delta={delta:+.2f} reason={reason}",
                )
                return new
        raise KeyError(f"belief not found: {belief_id}")

    def find_belief_by_topic(self, topic: str) -> dict[str, Any] | None:
        """按 topic 查找信念 (闭环: decision_type → belief topic 映射)."""
        state = self._load_state()
        topic_lower = topic.lower()
        for b in state["beliefs"]:
            if topic_lower in b["topic"].lower():
                return b
        return None

    # ── P2: 记忆扩展 (技能库+经验库+遗忘+Mem0模式) ──────────────

    def record_skill(self, agent_id: str, skill_name: str, code_or_pattern: str, learned_from: str, *, reusable: bool = True) -> str:
        """P2-T1: 记录agent积累的可复用技能."""
        state = self._load_state()
        sk_id = f"skill-{len(state['agent_skills']) + 1:04d}"
        state["agent_skills"].append({"id": sk_id, "agent_id": agent_id, "skill_name": skill_name, "code_or_pattern": code_or_pattern[:500], "learned_from": learned_from, "reusable": reusable, "recorded_at": _utc_now()})
        write_yaml_atomic(self.state_file, state)
        self._append_audit_log("RECORD_SKILL", f"id={sk_id} agent={agent_id} skill={skill_name}")
        return sk_id

    def record_experience(self, agent_id: str, experience: str, outcome: str, *, context: str = "") -> str:
        """P2-T2: 记录agent的正/反面经验教训."""
        state = self._load_state()
        ex_id = f"exp-{len(state['agent_experiences']) + 1:04d}"
        state["agent_experiences"].append({"id": ex_id, "agent_id": agent_id, "experience": experience[:500], "outcome": outcome, "context": context[:200], "recorded_at": _utc_now()})
        write_yaml_atomic(self.state_file, state)
        self._append_audit_log("RECORD_EXPERIENCE", f"id={ex_id} agent={agent_id} outcome={outcome}")
        return ex_id

    def forget_expired(self, *, max_age_days: int = 90) -> dict[str, int]:
        """P2-T3: TTL-based遗忘 — 标记超过max_age天的记忆为archived (参考SAGE Ebbinghaus)."""
        from datetime import datetime, timedelta, timezone
        state = self._load_state()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        archived = {"world_snapshots": 0, "experiences": 0}
        for ws in state["world_snapshots"]:
            ts = str(ws.get("expires_at", ws.get("ts", "")))
            if ts and ts < cutoff and ws.get("status") != "archived":
                ws["status"] = "archived"; archived["world_snapshots"] += 1
        for exp in state["agent_experiences"]:
            ts = str(exp.get("recorded_at", ""))
            if ts and ts < cutoff and exp.get("status") != "archived":
                exp["status"] = "archived"; archived["experiences"] += 1
        write_yaml_atomic(self.state_file, state)
        self._append_audit_log("FORGET_EXPIRED", f"max_age={max_age_days}d archived={archived}")
        return archived

    def update_memory(self, table: str, key: str, operation: str, value: Any = None) -> bool:
        """P2-T4: Mem0模式记忆操作 — ADD/MERGE/UPDATE/DELETE."""
        state = self._load_state()
        if table not in state:
            return False
        items = state[table]
        found_idx = None
        for i, item in enumerate(items):
            if item.get("id") == key or key in str(item.get("topic", "")):
                found_idx = i; break
        if operation == "ADD" and found_idx is None and isinstance(value, dict):
            items.append(value); write_yaml_atomic(self.state_file, state); return True
        elif operation == "DELETE" and found_idx is not None:
            items.pop(found_idx); write_yaml_atomic(self.state_file, state); return True
        elif operation == "UPDATE" and found_idx is not None and isinstance(value, dict):
            items[found_idx].update(value); write_yaml_atomic(self.state_file, state); return True
        elif operation == "MERGE" and found_idx is not None and isinstance(value, dict):
            for k, v in value.items():
                if k not in items[found_idx]:
                    items[found_idx][k] = v
            write_yaml_atomic(self.state_file, state); return True
        return False
