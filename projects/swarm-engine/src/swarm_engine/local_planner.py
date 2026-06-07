from __future__ import annotations

from ._compat import ExecutionPlan, PlannedStep, Priority, TaskType, _log

# ---
# domain: D-Execution
# layer: organ
# status: active
# version: 1.0.0
# ---
"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Constraint: "[!!] LOCAL_PLANNER_FALLBACK"
Summary: 'LocalPlanner: 本地 fallback 规划器 — 当 LLM 不可用时提供本地任务规划能力。'
Tags:
  - planner
  - fallback
  - local
  - task
  - orchestration
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Local Planner ≡ Module
# 内涵 ≝ {Local, Planner}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, LocalPlanner)}
# 功能 ⊢ {Local_Planner, Init_Local, Validate_Planner}
# =============================================================================


from typing import Any

_TASK_PATTERNS: list[tuple[TaskType, list[str], float]] = [
    (
        TaskType.CODE_GENERATION,
        ["write", "create", "implement", "add", "generate", "build", "新建", "编写", "创建"],
        0.9,
    ),
    (
        TaskType.CODE_REFACTOR,
        ["refactor", "restructure", "reorganize", "improve", "optimize", "重构", "优化", "重写"],
        0.85,
    ),
    (
        TaskType.CODE_REVIEW,
        ["review", "check", "audit", "validate", "verify", "inspect", "审查", "检查", "审计"],
        0.8,
    ),
    (
        TaskType.SECURITY_AUDIT,
        [
            "security",
            "vulnerability",
            "exploit",
            "threat",
            "attack",
            "permission",
            "安全",
            "漏洞",
            "威胁",
        ],
        0.95,
    ),
    (
        TaskType.TEST_GENERATION,
        ["test", "spec", "mock", "fixture", "coverage", "测试", "单元测试", "集成测试"],
        0.85,
    ),
    (
        TaskType.DOCUMENTATION,
        ["document", "readme", "guide", "spec", "api", "docs", "文档", "说明", "注释"],
        0.75,
    ),
    (
        TaskType.DATA_ANALYSIS,
        ["analyze", "analysis", "report", "metrics", "statistics", "分析", "统计", "报告"],
        0.8,
    ),
    (
        TaskType.INFRASTRUCTURE,
        [
            "deploy",
            "setup",
            "configure",
            "install",
            "docker",
            "kubernetes",
            "部署",
            "配置",
            "安装",
            "环境",
        ],
        0.9,
    ),
    (
        TaskType.RESEARCH,
        ["research", "investigate", "explore", "compare", "benchmark", "研究", "调研", "比较"],
        0.85,
    ),
    (
        TaskType.DEPLOYMENT,
        ["deploy", "release", "publish", "ship", "push", "发布", "上线", "部署"],
        0.9,
    ),
]

_CAPABILITY_MAP: dict[TaskType, list[str]] = {
    TaskType.CODE_GENERATION: ["code.generation", "code.refinement"],
    TaskType.CODE_REFACTOR: ["code.refinement", "code.analysis"],
    TaskType.CODE_REVIEW: ["code.review", "code.analysis"],
    TaskType.SECURITY_AUDIT: ["security.scan", "security.audit"],
    TaskType.TEST_GENERATION: ["code.test", "code.generation"],
    TaskType.DOCUMENTATION: ["docs.write", "code.analysis"],
    TaskType.DATA_ANALYSIS: ["data.analysis", "research"],
    TaskType.INFRASTRUCTURE: ["infra.deploy", "infra.configure"],
    TaskType.RESEARCH: ["research", "analysis"],
    TaskType.DEPLOYMENT: ["infra.deploy", "ci.cd"],
}

_STEP_TEMPLATES: dict[TaskType, list[dict[str, Any]]] = {
    TaskType.CODE_GENERATION: [
        {"desc": "Analyze requirements and design solution", "eu": 0.5},
        {"desc": "Generate code implementation", "eu": 2.0},
        {"desc": "Add unit tests", "eu": 1.0},
        {"desc": "Review generated code", "eu": 0.5},
    ],
    TaskType.CODE_REFACTOR: [
        {"desc": "Analyze current code structure", "eu": 0.5},
        {"desc": "Identify refactoring opportunities", "eu": 0.5},
        {"desc": "Implement refactoring changes", "eu": 1.5},
        {"desc": "Verify tests still pass", "eu": 0.5},
    ],
    TaskType.SECURITY_AUDIT: [
        {"desc": "Scan for common vulnerabilities", "eu": 1.0},
        {"desc": "Check authentication and authorization", "eu": 0.8},
        {"desc": "Analyze data validation", "eu": 0.6},
        {"desc": "Generate security report", "eu": 0.4},
    ],
    TaskType.TEST_GENERATION: [
        {"desc": "Identify untested code paths", "eu": 0.5},
        {"desc": "Generate unit tests", "eu": 1.5},
        {"desc": "Generate integration tests", "eu": 1.0},
        {"desc": "Verify test coverage", "eu": 0.5},
    ],
}


# ---------------------------------------------------------------------------
# LocalPlanner
# ---------------------------------------------------------------------------


class LocalPlanner:
    """
    Local fallback task planner for when LLM is unavailable.

    Uses rule-based pattern matching and templates to generate execution plans.
    Provides:
    - Intent classification
    - Task decomposition into steps
    - Dependency analysis
    - EU budget estimation
    - Parallelization hints
    """

    MAX_STEPS = 20

    def __init__(self) -> None:
        self.status = "active"  # was super().__init__(metadata_path=...)
        self._step_counter = 0
        self._plan_counter = 0

    # ── Public API ─────────────────────────────────────────────────────────────

    def plan(self, intent: str, context: dict[str, Any] | None = None) -> ExecutionPlan:
        """
        Generate an execution plan from intent text.

        Args:
            intent: Natural language intent description.
            context: Optional context dict with 'files', 'language', 'framework', etc.

        Returns:
            ExecutionPlan with decomposed steps and metadata.
        """
        context = context or {}
        _log.info("[LocalPlanner] Planning for intent: %s", intent[:100])

        # Step 1: Classify intent
        task_type, type_confidence = self._classify_intent(intent)

        # Step 2: Generate steps from template
        steps = self._decompose_steps(intent, task_type, context)

        # Step 3: Analyze dependencies
        parallel_groups = self._analyze_parallelization(steps)

        # Step 4: Estimate resources
        total_eu = sum(s.estimated_eu for s in steps)
        estimated_duration = self._estimate_duration(steps)

        # Step 5: Generate rollback plan
        for step in steps:
            step.rollback_plan = self._generate_rollback(step, context)

        plan = ExecutionPlan(
            plan_id=self._generate_plan_id(),
            original_intent=intent,
            steps=steps,
            estimated_total_eu=total_eu,
            estimated_duration=estimated_duration,
            can_parallelize=parallel_groups,
            confidence=type_confidence,
            fallback_used=False,
            reasoning=f"Local planner generated {len(steps)} steps for {task_type.value}",
        )

        _log.info(
            "[LocalPlanner] Plan generated: %d steps, %.1f EU, %.1fs estimated",
            len(steps),
            total_eu,
            estimated_duration,
        )
        return plan

    def can_handle(self, intent: str) -> tuple[bool, float]:
        """
        Check if this planner can handle the given intent.

        Returns:
            (can_handle, confidence) tuple.
        """
        task_type, confidence = self._classify_intent(intent)
        return task_type != TaskType.UNKNOWN or confidence > 0.3, confidence

    # ── Private Helpers ─────────────────────────────────────────────────────────

    def _classify_intent(self, intent: str) -> tuple[TaskType, float]:
        """Classify intent into task type using keyword matching."""
        normalized = intent.lower()
        scores: dict[TaskType, float] = {}

        for task_type, keywords, base_confidence in _TASK_PATTERNS:
            hits = 0
            for kw in keywords:
                if kw in normalized:
                    hits += 1
            if hits > 0:
                scores[task_type] = base_confidence * min(hits / len(keywords), 1.0)

        if not scores:
            return TaskType.UNKNOWN, 0.3

        best_type = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_type]

        _log.debug("[LocalPlanner] Classified as %s (confidence: %.2f)", best_type.value, best_score)
        return best_type, min(best_score, 1.0)

    def _decompose_steps(
        self,
        intent: str,
        task_type: TaskType,
        context: dict[str, Any],
    ) -> list[PlannedStep]:
        """Decompose intent into execution steps using templates."""
        steps: list[PlannedStep] = []

        # Check for template
        templates = _STEP_TEMPLATES.get(task_type, [])

        if templates:
            for i, tmpl in enumerate(templates):
                step = PlannedStep(
                    step_id=self._generate_step_id(),
                    description=tmpl["desc"],
                    task_type=task_type,
                    priority=self._infer_priority(intent, task_type),
                    dependencies=[steps[-1].step_id] if steps and i > 0 else [],
                    estimated_eu=tmpl["eu"],
                    suggested_capability=self._get_capability(task_type),
                )
                steps.append(step)
        else:
            # Generic decomposition for unknown types
            steps.append(
                PlannedStep(
                    step_id=self._generate_step_id(),
                    description=f"Analyze: {intent[:50]}",
                    task_type=task_type,
                    priority=self._infer_priority(intent, task_type),
                    estimated_eu=1.0,
                    suggested_capability="analysis",
                )
            )
            steps.append(
                PlannedStep(
                    step_id=self._generate_step_id(),
                    description=f"Execute: {intent[:50]}",
                    task_type=task_type,
                    priority=self._infer_priority(intent, task_type),
                    dependencies=[steps[0].step_id],
                    estimated_eu=2.0,
                    suggested_capability=self._get_capability(task_type),
                )
            )

        # Limit to MAX_STEPS
        return steps[: self.MAX_STEPS]

    def _analyze_parallelization(self, steps: list[PlannedStep]) -> list[str]:
        """Identify steps that can run in parallel (no dependencies)."""
        parallel: list[str] = []
        for step in steps:
            if not step.dependencies:
                parallel.append(step.step_id)
        return parallel

    def _estimate_duration(self, steps: list[PlannedStep]) -> float:
        """Estimate total execution duration in seconds."""
        # Assume ~10 seconds per EU average
        total_eu = sum(s.estimated_eu for s in steps)
        return total_eu * 10.0

    def _generate_rollback(self, step: PlannedStep, _context: dict[str, Any]) -> str:
        """Generate rollback instructions for a step."""
        file_hint = _context.get("target_file", "affected files")

        if step.task_type == TaskType.CODE_GENERATION:
            return f"Remove generated code from {file_hint}"
        elif step.task_type == TaskType.CODE_REFACTOR:
            return f"Restore original code in {file_hint} from git"
        elif step.task_type == TaskType.TEST_GENERATION:
            return f"Remove generated tests from {file_hint}"
        else:
            return f"Rollback changes to {file_hint}"

    def _infer_priority(self, intent: str, task_type: TaskType) -> Priority:
        """Infer priority from intent keywords."""
        normalized = intent.lower()

        if any(kw in normalized for kw in ["urgent", "critical", "asap", "immediately", "紧急", "立即"]):
            return Priority.CRITICAL
        if any(kw in normalized for kw in ["important", "priority", "soon", "重要", "优先"]):
            return Priority.HIGH
        if task_type == TaskType.SECURITY_AUDIT:
            return Priority.HIGH

        return Priority.MEDIUM

    def _get_capability(self, task_type: TaskType) -> str:
        """Map task type to required capability."""
        caps = _CAPABILITY_MAP.get(task_type, ["generic"])
        return caps[0] if caps else "generic"

    def _generate_plan_id(self) -> str:
        """Generate unique plan ID using UUID."""
        import uuid

        self._plan_counter += 1
        return f"PLAN-{uuid.uuid4().hex[:8].upper()}-{self._plan_counter:04d}"

    def _generate_step_id(self) -> str:
        """Generate unique step ID using UUID."""
        import uuid

        self._step_counter += 1
        return f"S{uuid.uuid4().hex[:8].upper()}"

    def validate_internal_state(self) -> bool:
        return True
