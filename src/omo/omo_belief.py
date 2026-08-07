#!/usr/bin/env python3
"""
projects/omo/src/omo/omo_belief.py — MOS Agent Belief 三表 Schema 与写入持久化工具 (BET-Y1Q1-T3-01)
"""

from __future__ import annotations

import json
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

    def _append_audit_log(self, action: str, details: str) -> None:
        """追加写入审计日志流"""
        log_line = f"[{_utc_now()}] ACTION={action} DETAILS={details}\n"
        with self.audit_log_file.open("a", encoding="utf-8") as f:
            f.write(log_line)

    def _load_state(self) -> dict[str, list[dict[str, Any]]]:
        if not self.state_file.exists():
            return {"beliefs": [], "lessons": [], "contexts": []}
        data = load_yaml_value(self.state_file) or {}
        return {
            "beliefs": data.get("beliefs", []),
            "lessons": data.get("lessons", []),
            "contexts": data.get("contexts", []),
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
        self._update_registry_summary(len(state["beliefs"]))
        self._append_audit_log("RECORD_BELIEF", f"id={b_id} topic={topic} run_id={source_run_id}")
        return b_id

    def _update_registry_summary(self, total_beliefs: int) -> None:
        """同步更新注册表元数据汇总"""
        registry_data = (
            load_yaml_value(self.registry_file) or {}
            if self.registry_file.exists()
            else {}
        )
        registry_data["schema"] = "memory-os/v1"
        registry_data["as_of"] = _utc_now()
        registry_data["total_beliefs"] = total_beliefs
        registry_data["tables"] = ["agent_belief", "agent_lesson", "agent_context"]
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
