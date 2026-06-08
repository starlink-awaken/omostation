#!/usr/bin/env python3
# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""任务拆解器 — 将复杂问题拆解为 P0/P1/P2 阶段的任务 DAG。

复用 VisionParser 的 few-shot 模式，但独立实现避免 CognitiveBus 依赖。
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field

# 尝试 LLM path
HAS_LLM = False
try:
    from organs.D_Execution.organs.llm.provider import LLMRequest  # type: ignore[import-not-found]
    from organs.D_Execution.organs.llm.provider_factory import LLMProviderFactory  # type: ignore[import-not-found]
    HAS_LLM = True
except ImportError:
    pass


@dataclass
class DecomposedTask:
    task_id: str
    description: str
    phase: str  # P0=规划, P1=执行, P2=验证
    dependencies: list[str] = field(default_factory=list)
    capability_hint: str = "general.task.*"


@dataclass
class DecompositionResult:
    original_question: str
    tasks: list[DecomposedTask]
    method: str = "deterministic"


FEW_SHOT_PROMPT = """You are a senior task-decomposition specialist.

Given a complex question, decompose it into atomic tasks organized in three phases:
- P0 (Planning/Design): Research, analysis, data gathering
- P1 (Execution): Implementation, processing, generation
- P2 (Verification): Validation, testing, review

Return ONLY a valid JSON array. Each element:
  "description": concise task description
  "capability_hint": one of "analysis.research.*", "knowledge.documentation.*",
                      "code.generation.*", "data.modeling.*", "general.task.*"
  "phase": "P0" | "P1" | "P2"
  "dependencies": list of zero-based indices this task depends on

Example: "How have my learning interests evolved this year?"
[
  {{"description": "查询FactGraph中今年的学习记录", "capability_hint": "analysis.research.*", "phase": "P0", "dependencies": []}},
  {{"description": "分析学习主题迁徙模式和频率变化", "capability_hint": "analysis.research.*", "phase": "P1", "dependencies": [0]}},
  {{"description": "生成结构化洞察报告", "capability_hint": "knowledge.documentation.*", "phase": "P2", "dependencies": [1]}}
]

Question: {question}
Return ONLY the JSON array."""


_KEYWORD_MAP: list[tuple[list[str], str]] = [
    (["分析", "趋势", "模式", "变迁", "比较", "对比"], "analysis.research.*"),
    (["查询", "检索", "查找", "搜索", "回忆"], "analysis.research.*"),
    (["总结", "报告", "文档", "记录", "笔记"], "knowledge.documentation.*"),
    (["生成", "创建", "编写", "构建", "实现"], "code.generation.*"),
    (["关系", "链接", "关联", "图谱", "连接"], "data.modeling.*"),
    (["验证", "检查", "确认", "测试"], "general.task.*"),
]


def _infer_capability(text: str) -> str:
    text_lower = text.lower()
    for keywords, cap in _KEYWORD_MAP:
        if any(kw in text_lower for kw in keywords):
            return cap
    return "general.task.*"


def _split_by_phase(question: str) -> list[str]:
    """基于规则的自然任务拆解 — 按 NLP 意图分割。"""
    patterns = [
        (r"分析(.+?)并(总结|生成|给出)", ["分析{0}", "总结{0}"]),
        (r"查询(.+?)然后(分析|比较)", ["查询{0}", "分析{0}"]),
        (r"比较(.+?)和(.+?)的(差异|关系|区别)", ["分析{0}", "分析{1}", "比较{0}和{1}"]),
    ]

    for pattern, template_parts in patterns:
        match = re.search(pattern, question)
        if match:
            tasks = []
            for part in template_parts:
                filled = part.format(*match.groups())
                if filled not in tasks:
                    tasks.append(filled)
            if tasks:
                return tasks

    # 默认拆解
    return [
        f"收集与「{question}」相关的现有知识",
        f"分析{question}的核心影响因素",
        "提取关键洞察并识别知识缺口",
        "生成结构化报告并更新知识图谱",
    ]


def _deterministic_decompose(question: str) -> DecompositionResult:
    task_texts = _split_by_phase(question)
    total = len(task_texts)
    tasks = []  # type: ignore[var-annotated]

    for i, text in enumerate(task_texts):
        fraction = i / max(total - 1, 1)
        if fraction < 0.25:
            phase = "P0"
        elif fraction > 0.75:
            phase = "P2"
        else:
            phase = "P1"

        dep_ids: list[str] = []
        if i > 0:
            dep_ids.append(tasks[i - 1].task_id)

        tasks.append(DecomposedTask(
            task_id=f"T-{uuid.uuid4().hex[:8].upper()}",
            description=text,
            phase=phase,
            dependencies=dep_ids,
            capability_hint=_infer_capability(text),
        ))

    return DecompositionResult(
        original_question=question, tasks=tasks, method="deterministic",
    )


def _llm_decompose(question: str) -> DecompositionResult | None:
    if not HAS_LLM:
        return None
    try:
        prompt = FEW_SHOT_PROMPT.format(question=question)
        factory = LLMProviderFactory()
        request = LLMRequest(prompt=prompt, temperature=0.3)
        response = factory.generate_resilient(request)

        json_match = re.search(r"\[.*?\]", response.content, re.DOTALL)
        if json_match:
            raw_tasks = json.loads(json_match.group())
            tasks = []
            id_map: dict[int, str] = {}
            for i, rt in enumerate(raw_tasks):
                tid = f"T-{uuid.uuid4().hex[:8].upper()}"
                id_map[i] = tid
                dep_ids = [id_map[d] for d in rt.get("dependencies", []) if d in id_map]
                tasks.append(DecomposedTask(
                    task_id=tid,
                    description=str(rt.get("description", "")),
                    phase=str(rt.get("phase", "P1")),
                    dependencies=dep_ids,
                    capability_hint=str(rt.get("capability_hint", "general.task.*")),
                ))
            if tasks:
                return DecompositionResult(
                    original_question=question, tasks=tasks, method="llm",
                )
    except (AttributeError, ImportError, json.JSONDecodeError, RuntimeError, TypeError, ValueError):
        pass
    return None


def decompose(question: str) -> DecompositionResult:
    result = _llm_decompose(question)
    if result:
        return result
    return _deterministic_decompose(question)


def format_decomposition(result: DecompositionResult) -> str:
    lines = [
        "# 任务拆解结果",
        "",
        f"**问题:** {result.original_question}",
        f"**方法:** {result.method}",
        f"**任务数:** {len(result.tasks)}",
        "",
        "## 任务 DAG",
        "",
        "| 任务 | 阶段 | 描述 | 依赖 | 能力 |",
        "|------|------|------|------|------|",
    ]
    for t in result.tasks:
        deps = ", ".join(t.dependencies) if t.dependencies else "—"
        lines.append(f"| {t.task_id} | {t.phase} | {t.description} | {deps} | {t.capability_hint} |")

    return "\n".join(lines)


def main() -> None:
    import sys
    question = sys.argv[1] if len(sys.argv) > 1 else "分析我对编程语言的学习模式"
    result = decompose(question)
    print(format_decomposition(result))


class DependencyGraph:
    """基于阶段推断的依赖图 — 使用 dict 邻接表。

    P0 无依赖, P1 依赖所有 P0, P2 依赖所有 P1。
    """

    def __init__(self, tasks: list[DecomposedTask]) -> None:
        self.graph: dict[str, list[str]] = {}
        self._build(tasks)

    def _build(self, tasks: list[DecomposedTask]) -> None:
        self.graph = {}
        task_ids = {t.task_id for t in tasks}
        for task in tasks:
            unknown = [dep for dep in task.dependencies if dep not in task_ids]
            if unknown:
                raise ValueError(f"Unknown dependency for {task.task_id}: {', '.join(unknown)}")

        p0 = [t.task_id for t in tasks if t.phase == "P0"]
        p1 = [t.task_id for t in tasks if t.phase == "P1"]
        p2 = [t.task_id for t in tasks if t.phase == "P2"]

        for tid in p0:
            self.graph[tid] = []
        for tid in p1:
            self.graph[tid] = list(p0)
        for tid in p2:
            self.graph[tid] = list(p1)

        # 兜底：未按阶段分组的任务保留其显式依赖
        for t in tasks:
            if t.task_id not in self.graph:
                self.graph[t.task_id] = list(t.dependencies)

    def topological_sort(self) -> list[str]:
        """Kahn 算法拓扑排序。"""
        in_degree: dict[str, int] = {n: len(deps) for n, deps in self.graph.items()}
        queue = [n for n, d in in_degree.items() if d == 0]
        result: list[str] = []

        # 构建正向邻接表: node -> [nodes that depend on it]
        fwd: dict[str, list[str]] = {n: [] for n in self.graph}
        for node, deps in self.graph.items():
            for dep in deps:
                if dep in fwd:
                    fwd[dep].append(node)

        while queue:
            n = queue.pop(0)
            result.append(n)
            for child in fwd.get(n, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        return result

    def critical_path(self) -> list[str]:
        """最长路径 — 从任意根节点到任意叶子节点。"""
        roots = [n for n, deps in self.graph.items() if not deps]
        longest: list[str] = []

        def dfs(node: str, path: list[str]) -> None:
            cur = path + [node]
            children = [n for n, deps in self.graph.items() if node in deps]
            if not children:
                if len(cur) > len(longest):
                    longest[:] = cur
            else:
                for c in children:
                    dfs(c, cur)

        for r in roots:
            dfs(r, [])
        return longest

    def parallel_groups(self) -> list[list[str]]:
        """BFS 分层 → 相同深度的任务为一个并行组。"""
        roots = [n for n, deps in self.graph.items() if not deps]
        groups: list[list[str]] = []
        current = list(roots)
        visited: set[str] = set()

        while current:
            groups.append(list(current))
            visited.update(current)
            nxt: list[str] = []
            for node in current:
                children = [n for n, deps in self.graph.items()
                            if node in deps and n not in visited and n not in nxt]
                nxt.extend(children)
            current = nxt

        return groups

    def to_mermaid(self) -> str:
        """渲染为 Mermaid 流程图。"""
        lines = ["graph TD"]
        for node, deps in self.graph.items():
            if deps:
                for d in deps:
                    lines.append(f"    {d}[{d}] --> {node}[{node}]")
            else:
                lines.append(f"    {node}[{node}]")
        return "\n".join(lines)

    def to_ascii(self) -> str:
        """渲染为缩进树。"""
        roots = [n for n, deps in self.graph.items() if not deps]
        result: list[str] = []

        def _render(n: str, depth: int = 0) -> None:
            result.append("  " * depth + f"- {n}")
            for child, deps in self.graph.items():
                if n in deps:
                    _render(child, depth + 1)

        for r in roots:
            _render(r)
        return "\n".join(result)


class TimelineEstimator:
    """根据任务描述关键词估算耗时。"""

    _COMPLEXITY_MAP: dict[str, float] = {
        "analysis": 0.5,
        "planning": 1.0,
        "execution": 2.0,
        "knowledge": 0.8,
        "data": 1.5,
        "general": 1.0,
    }

    @classmethod
    def estimate(cls, task: DecomposedTask) -> float:
        desc = task.description.lower()
        for kw, val in cls._COMPLEXITY_MAP.items():
            if kw in desc:
                return val
        hint = task.capability_hint.lower()
        for kw, val in cls._COMPLEXITY_MAP.items():
            if kw in hint:
                return val
        return 1.0

    @classmethod
    def total_estimate(cls, tasks: list[DecomposedTask]) -> float:
        return sum(cls.estimate(t) for t in tasks)


def enhance_decomposition(result: DecompositionResult) -> dict:
    """增强拆解结果 — 生成依赖图、时间线、可视化。"""
    graph = DependencyGraph(result.tasks)
    timeline = {t.task_id: TimelineEstimator.estimate(t) for t in result.tasks}
    total = TimelineEstimator.total_estimate(result.tasks)
    return {
        "original": result,
        "graph": graph,
        "timeline": timeline,
        "total_estimate": total,
        "visualization": graph.to_ascii(),
    }


def _wire_local_planner(goal: str) -> dict | None:
    """尝试对接 LocalPlanner — 导入失败返回 None。"""
    try:
        from organs.D_Execution.organs.local_planner import (  # type: ignore[import-not-found, import-untyped]
            LocalPlanner,
        )
        planner = LocalPlanner()
        can_handle, confidence = planner.can_handle(goal)
        if can_handle and confidence > 0.5:
            plan = planner.plan(goal)
            return {
                "plan_id": plan.plan_id,
                "steps": [vars(s) for s in plan.steps],
                "total_eu": plan.total_eu,
                "duration_s": plan.duration_s,
                "confidence": confidence,
                "parallel_groups": list(plan.parallel_groups),
            }
    except (ImportError, RuntimeError, OSError):
        pass
    return None


if __name__ == "__main__":
    main()
