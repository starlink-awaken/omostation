"""causal_tracer.py — 决策因果链追溯引擎 (BET-Y1Q4-T6-26).

基于 SemanticaKernel 的决策因果链追溯器，
支持 CAUSED/INFLUENCED 关系建模与循环检测。

关系类型:
    CAUSED — 直接因果关系（强）
    INFLUENCED — 间接影响关系（弱）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from kairon.graph.semantica_kernel import SemanticaKernel

# ── RDF 命名空间 ──────────────────────────────────────
_DECISION_NS = "urn:kairon:decision:"
_CAUSAL_NS = "urn:kairon:causal:"

_RELATION_CAUSED = f"{_CAUSAL_NS}CAUSED"
_RELATION_INFLUENCED = f"{_CAUSAL_NS}INFLUENCED"
_RELATION_DECISION = f"{_DECISION_NS}Decision"
_RELATION_TIMESTAMP = f"{_DECISION_NS}timestamp"
_RELATION_AGENT = f"{_DECISION_NS}agent"
_RELATION_ACTION = f"{_DECISION_NS}action"
_RELATION_CONFIDENCE = f"{_DECISION_NS}confidence"
_RELATION_OUTCOME = f"{_DECISION_NS}outcome"
_RELATION_INPUT = f"{_DECISION_NS}input"


@dataclass
class DecisionRecord:
    """决策记录数据类.

    Attributes:
        decision_id: 唯一决策标识符 (自动生成)
        timestamp: 决策时间戳 (UTC)
        agent: 决策者标识 (agent/role name)
        action: 执行的动作描述
        confidence: 决策置信度 0.0~1.0
        inputs: 输入事实/证据列表
        outcome: 决策结果 (可选，事后记录)
        metadata: 附加元数据
    """

    agent: str
    action: str
    confidence: float = 0.5
    inputs: list[str] = field(default_factory=list)
    outcome: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    decision_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = str(uuid.uuid4())
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")

    @property
    def uri(self) -> str:
        """RDF URI for this decision."""
        return f"{_DECISION_NS}{self.decision_id}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON/BOS transport."""
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent,
            "action": self.action,
            "confidence": self.confidence,
            "inputs": self.inputs,
            "outcome": self.outcome,
            "metadata": self.metadata,
        }


class CausalTracer:
    """决策因果链追溯器 — CAUSED/INFLUENCED 关系.

    使用 SemanticaKernel 作为底层图存储，提供：
    - 决策记录到因果图
    - 追溯因果祖先链 (trace_causes)
    - 追溯下游影响面 (trace_effects)
    - 建立因果关系 (link_cause)
    - 循环检测
    """

    def __init__(self, kernel: SemanticaKernel | None = None) -> None:
        """Initialize CausalTracer.

        Args:
            kernel: SemanticaKernel instance. Created with auto backend if None.
        """
        self._kernel = kernel or SemanticaKernel(backend="auto")

    # ── 记录决策 ────────────────────────────────────

    def record_decision(self, record: DecisionRecord) -> str:
        """Record a decision to the causal graph.

        Args:
            record: DecisionRecord to persist.

        Returns:
            The decision_id.
        """
        uri = record.uri

        # Decision entity
        self._kernel.add_triple(uri, _RELATION_DECISION, "true")

        # Timestamp
        self._kernel.add_triple(uri, _RELATION_TIMESTAMP, record.timestamp.isoformat())

        # Agent
        self._kernel.add_triple(uri, _RELATION_AGENT, record.agent)

        # Action
        self._kernel.add_triple(uri, _RELATION_ACTION, record.action)

        # Confidence
        self._kernel.add_triple(uri, _RELATION_CONFIDENCE, str(record.confidence))

        # Outcome (if set)
        if record.outcome:
            self._kernel.add_triple(uri, _RELATION_OUTCOME, record.outcome)

        # Inputs
        for inp in record.inputs:
            inp_uri = f"{_DECISION_NS}input:{uuid.uuid5(uuid.NAMESPACE_DNS, inp)}"
            self._kernel.add_triple(inp_uri, _RELATION_DECISION, "input")
            self._kernel.add_triple(uri, _RELATION_INPUT, inp)

        return record.decision_id

    # ── 追溯因果链 ──────────────────────────────────

    def trace_causes(self, decision_id: str, max_depth: int = 10) -> list[dict[str, Any]]:
        """Trace the full causal ancestor chain for a decision.

        Follows CAUSED (strong) and INFLUENCED (weak) edges backwards.

        Args:
            decision_id: The decision ID to trace from.
            max_depth: Maximum traversal depth (default 10, prevents infinite loops).

        Returns:
            List of ancestor nodes with relation type and depth info.
        """
        target_uri = f"{_DECISION_NS}{decision_id}"
        visited: set[str] = set()
        results: list[dict[str, Any]] = []

        self._traverse(target_uri, _RELATION_CAUSED, visited, results, depth=0, max_depth=max_depth, direction="causes")
        self._traverse(target_uri, _RELATION_INFLUENCED, visited, results, depth=0, max_depth=max_depth, direction="causes")

        return results

    def trace_effects(self, decision_id: str, max_depth: int = 10) -> list[dict[str, Any]]:
        """Trace downstream effects of a decision.

        Follows CAUSED and INFLUENCED edges forward (effects).

        Args:
            decision_id: The decision ID to trace from.
            max_depth: Maximum traversal depth.

        Returns:
            List of descendant nodes with relation type and depth info.
        """
        source_uri = f"{_DECISION_NS}{decision_id}"
        visited: set[str] = set()
        results: list[dict[str, Any]] = []

        self._traverse(source_uri, _RELATION_CAUSED, visited, results, depth=0, max_depth=max_depth, direction="effects")
        self._traverse(source_uri, _RELATION_INFLUENCED, visited, results, depth=0, max_depth=max_depth, direction="effects")

        return results

    def _traverse(
        self,
        start_uri: str,
        relation: str,
        visited: set[str],
        results: list[dict[str, Any]],
        depth: int,
        max_depth: int,
        direction: str,
    ) -> None:
        """DFS traversal for causal chain following."""
        if depth > max_depth or start_uri in visited:
            return
        visited.add(start_uri)

        # Query the graph for edges with this relation
        pattern = f"{{ ?s {relation} ?o }}"
        try:
            matches = self._kernel.query(pattern)
        except Exception:
            # Fallback: use direct triple inspection
            matches = self._kernel.query(relation)

        if not matches:
            return

        for match in matches:
            if direction == "effects":
                # Forward: start_uri → ?o
                subject = match.get("s", match.get("subject", ""))
                obj = match.get("o", match.get("object", ""))
                if subject == start_uri:
                    self._add_result(results, obj, relation, depth + 1)
                    self._traverse(obj, relation, visited, results, depth + 1, max_depth, direction)
            else:
                # Backward: ?s → start_uri (causes)
                subject = match.get("s", match.get("subject", ""))
                obj = match.get("o", match.get("object", ""))
                if obj == start_uri:
                    self._add_result(results, subject, relation, depth + 1)
                    self._traverse(subject, relation, visited, results, depth + 1, max_depth, direction)

    def _add_result(
        self, results: list[dict[str, Any]], uri: str, relation: str, depth: int
    ) -> None:
        """Add a traversal result, extracting decision_id from URI."""
        # Extract decision_id from URI
        decision_id = uri.replace(_DECISION_NS, "")
        if not decision_id or decision_id == uri:
            # Not a decision URI, use as-is
            decision_id = uri

        results.append(
            {
                "decision_id": decision_id,
                "relation": self._relation_name(relation),
                "depth": depth,
            }
        )

    @staticmethod
    def _relation_name(relation: str) -> str:
        """Convert relation URI to human-readable name."""
        if relation == _RELATION_CAUSED:
            return "CAUSED"
        if relation == _RELATION_INFLUENCED:
            return "INFLUENCED"
        return relation

    # ── 建立因果关系 ────────────────────────────────

    def link_cause(self, cause_id: str, effect_id: str, relation: str = "CAUSED") -> str:
        """Establish a causal link between two decisions.

        Args:
            cause_id: The cause decision ID.
            effect_id: The effect decision ID.
            relation: "CAUSED" (strong) or "INFLUENCED" (weak).

        Returns:
            The relation URI that was created.

        Raises:
            ValueError: If relation is not CAUSED or INFLUENCED.
        """
        rel_map = {"CAUSED": _RELATION_CAUSED, "INFLUENCED": _RELATION_INFLUENCED}
        if relation not in rel_map:
            raise ValueError(
                f"Invalid relation '{relation}'. Must be 'CAUSED' or 'INFLUENCED'."
            )
        relation_uri = rel_map[relation]

        cause_uri = f"{_DECISION_NS}{cause_id}"
        effect_uri = f"{_DECISION_NS}{effect_id}"

        self._kernel.add_triple(cause_uri, relation_uri, effect_uri)
        return relation_uri

    # ── 循环检测 ────────────────────────────────────

    def has_cycle(self) -> bool:
        """Check if the causal graph contains any cycles.

        Uses DFS-based cycle detection on CAUSED edges (strong causality).

        Returns:
            True if a cycle exists, False otherwise.
        """
        # Build adjacency list from graph
        adj: dict[str, set[str]] = {}

        # Query for CAUSED edges
        for relation_uri, rel_name in [
            (_RELATION_CAUSED, "CAUSED"),
            (_RELATION_INFLUENCED, "INFLUENCED"),
        ]:
            try:
                matches = self._kernel.query(relation_uri)
                if not matches:
                    matches = self._kernel.query(f"{{ ?s {relation_uri} ?o }}")
                for match in matches:
                    s = match.get("s", match.get("subject", ""))
                    o = match.get("o", match.get("object", ""))
                    if s and o:
                        adj.setdefault(s, set()).add(o)
            except Exception:
                continue

        # DFS cycle detection
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {node: WHITE for node in adj}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for neighbor in adj.get(node, set()):
                if color.get(neighbor, WHITE) == GRAY:
                    return True
                if color.get(neighbor, WHITE) == WHITE:
                    if dfs(neighbor):
                        return True
            color[node] = BLACK
            return False

        for node in list(adj.keys()):
            if color.get(node, WHITE) == WHITE:
                if dfs(node):
                    return True
        return False

    # ── 统计 ────────────────────────────────────────

    def decision_count(self) -> int:
        """Return the number of recorded decisions (excluding input nodes)."""
        try:
            matches = self._kernel.query(f"{{ ?s {_RELATION_DECISION} ?o }}")
            if not matches:
                matches = self._kernel.query(_RELATION_DECISION)
            # Only count decision entities (object="true"), not input nodes
            count = 0
            for m in matches:
                obj = m.get("o", m.get("object", ""))
                if obj == "true":
                    count += 1
            return count
        except Exception:
            return 0

    def get_record(self, decision_id: str) -> dict[str, str] | None:
        """Retrieve a decision record's metadata from the graph.

        Returns:
            Dict with agent, action, confidence, outcome fields, or None.
        """
        uri = f"{_DECISION_NS}{decision_id}"
        result: dict[str, str] = {"decision_id": decision_id}

        for relation, field_name in [
            (_RELATION_AGENT, "agent"),
            (_RELATION_ACTION, "action"),
            (_RELATION_CONFIDENCE, "confidence"),
            (_RELATION_OUTCOME, "outcome"),
            (_RELATION_TIMESTAMP, "timestamp"),
        ]:
            try:
                matches = self._kernel.query(f"{{ {uri} {relation} ?o }}")
                if not matches:
                    matches = self._kernel.query(f"{{ {uri} {relation} ?object }}")
                if matches:
                    val = matches[0].get("o", matches[0].get("object", ""))
                    if val:
                        result[field_name] = val
            except Exception:
                continue

        return result

    @property
    def kernel(self) -> SemanticaKernel:
        """Access the underlying SemanticaKernel."""
        return self._kernel
