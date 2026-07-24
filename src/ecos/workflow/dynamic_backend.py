"""Dynamic Workflow Backend — LLM 驱动的动态工作流

当 execution.mode = dynamic 时，工作流引擎放弃预定义步骤列表，
改为由 LLM 根据当前上下文动态决策下一步执行什么动作。

架构:
  DynamicExecutor (backend_registry 入口)
    └→ DynamicPlanner (LLM 决策层)
         ├→ llm_client (可选依赖: OpenAI API 兼容端点)
         ├→ tool_registry (可用的 workflow actions + sub-workflows)
         └→ fallback (LLM 不可用时→线性执行并告警)

使用:
  execution:
    mode: dynamic
    dynamic:
      objective: "完成系统健康巡检并生成报告"
      llm_model: gpt-4o-mini
      max_steps: 10
      available_actions:
        - health_check
        - domain_validate_all
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("ecos.workflow.dynamic_backend")


# ── 动态执行器（暴露给 backend_registry 的入口函数）──


def execute(m1_node: dict, params: dict | None = None) -> dict:
    """动态工作流执行器

    Args:
        m1_node: M1 工作流定义
        params: 执行参数

    Returns:
        执行结果 dict, 格式与 _default_executor 兼容
    """
    results: dict[str, Any] = {"steps": [], "passed": 0, "failed": 0}
    params = params or {}

    # 从工作流定义中提取 dynamic 配置
    execution = m1_node.get("execution", {})
    dynamic_cfg = execution.get("dynamic", {})
    objective = dynamic_cfg.get("objective", m1_node.get("description", "执行工作流"))
    max_steps = dynamic_cfg.get("max_steps", 10)
    available_actions = dynamic_cfg.get("available_actions", [])
    llm_model = dynamic_cfg.get("llm_model", os.environ.get("DYNAMIC_WF_MODEL", ""))

    logger.info(
        "Dynamic workflow: %s (max_steps=%d, llm=%s)",
        objective,
        max_steps,
        llm_model or "(fallback)",
    )

    # 初始化 Planner
    planner = DynamicPlanner(
        objective=objective,
        available_actions=available_actions or _detect_actions(m1_node),
        llm_model=llm_model,
    )

    # 执行循环
    context: dict[str, Any] = {"workflow_name": m1_node.get("name", ""), "results": []}
    step_count = 0

    while step_count < max_steps:
        step_count += 1

        # LLM 决策下一步
        decision = planner.decide(context)

        if decision.get("action") == "__done__":
            logger.info("Dynamic workflow completed at step %d", step_count)
            break

        action_name = decision.get("action", "")
        step_name = decision.get("name", f"dynamic-step-{step_count}")
        reason = decision.get("reason", "")

        try:
            # 执行 action (通过 actions.py)
            from ecos.workflow.actions import resolve_action

            handler = resolve_action(action_name)
            if handler is None:
                logger.warning(
                    "Unknown action '%s' at step %d", action_name, step_count
                )
                results["steps"].append(
                    {
                        "name": step_name,
                        "status": "failed",
                        "action": action_name,
                        "error": f"未知动作: {action_name}",
                    }
                )
                results["failed"] += 1
                context["results"].append({"step": step_name, "ok": False})
                continue

            logger.info(
                "Dynamic step %d: %s → %s (%s)",
                step_count,
                step_name,
                action_name,
                reason,
            )
            step_result = handler(decision.get("params", {}) or {})
            ok = step_result.get("passed", False)

            results["steps"].append(
                {
                    "name": step_name,
                    "status": "ok" if ok else "failed",
                    "action": action_name,
                    "reason": reason,
                    "result": step_result,
                }
            )
            if ok:
                results["passed"] += 1
            else:
                results["failed"] += 1

            context["results"].append(
                {"step": step_name, "ok": ok, "summary": step_result.get("summary", "")}
            )

        except Exception as e:  # defensive fallback
            logger.error("Dynamic step %d failed: %s", step_count, e)
            results["steps"].append(
                {
                    "name": step_name,
                    "status": "error",
                    "action": action_name,
                    "error": str(e),
                }
            )
            results["failed"] += 1
            context["results"].append({"step": step_name, "ok": False, "error": str(e)})

    if step_count >= max_steps and not results["steps"][-1].get("action") == "__done__":
        logger.warning(
            "Dynamic workflow reached max_steps=%d without explicit completion",
            max_steps,
        )

    return results


def _detect_actions(m1_node: dict) -> list[str]:
    """从 workflow 现有步骤中提取可用动作列表"""
    actions: set[str] = set()
    for step in m1_node.get("steps", []):
        act = step.get("action")
        if act:
            actions.add(act)
    return sorted(actions)


# ── 动态规划器 ──


class DynamicPlanner:
    """LLM 驱动的动态工作流规划器

    在每一步基于当前上下文和目标，决定下一步执行什么动作。
    LLM 不可用时回退到简单线性执行。
    """

    def __init__(
        self,
        objective: str,
        available_actions: list[str],
        llm_model: str = "",
    ):
        self.objective = objective
        self.available_actions = available_actions
        self.llm_model = llm_model
        self._llm_client = self._init_llm()

    def _init_llm(self) -> Any | None:
        """初始化 LLM 客户端（可选依赖）"""
        if not self.llm_model:
            return None
        try:
            from openai import OpenAI

            return OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY", "sk-placeholder"),
                base_url=os.environ.get(
                    "OPENAI_BASE_URL",
                    os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1"),
                ),
            )
        except ImportError:
            logger.warning(
                "openai not installed, dynamic mode falls back to linear execution"
            )
            return None

    def decide(self, context: dict[str, Any]) -> dict[str, Any]:
        """决定下一步执行什么动作

        如果 LLM 可用，调用 LLM 决策；
        否则回退到线性执行（按 available_actions 顺序执行）。
        """
        if self._llm_client and self.llm_model:
            return self._decide_with_llm(context)
        return self._decide_fallback(context)

    def _decide_fallback(self, context: dict[str, Any]) -> dict[str, Any]:
        """LLM 不可用时的回退策略：按顺序执行可用动作

        第一轮执行全部 available_actions，
        第二轮告警并返回 __done__。
        """
        done_count = sum(1 for r in context.get("results", []) if r.get("ok"))
        if done_count >= len(self.available_actions):
            return {
                "action": "__done__",
                "name": "完成",
                "reason": "所有可用动作已执行完成",
            }

        # 找到第一个未执行的动作
        for action in self.available_actions:
            if not any(
                r.get("summary", "").startswith(action)
                or r.get("step", "").startswith(action[:5])
                for r in context.get("results", [])
            ):
                return {
                    "action": action,
                    "name": f"执行 {action}",
                    "reason": "线性回退: 顺序执行可用动作",
                    "params": {},
                }

        # 所有动作都试过了
        return {
            "action": "__done__",
            "name": "完成",
            "reason": "所有可用动作已尝试执行",
        }

    def _decide_with_llm(self, context: dict[str, Any]) -> dict[str, Any]:
        """调用 LLM 决策下一步"""
        try:
            return self._call_llm(context)
        except Exception as e:  # defensive fallback
            logger.warning("LLM decision failed, fallback: %s", e)
            return self._decide_fallback(context)

    def _call_llm(self, context: dict[str, Any]) -> dict[str, Any]:
        """调用 LLM API 获取下一步决策"""
        if not self._llm_client:
            return self._decide_fallback(context)

        prompt = self._build_prompt(context)
        response = self._llm_client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个工作流编排助手。根据目标和当前上下文，"
                        "从可用动作中选择下一步要执行的动作。"
                        '返回 JSON: {"action": "<动作名>", "name": "<步骤名>", '
                        '"reason": "<选择理由>", "params": {}}'
                        '当所有必要动作已完成时，返回 {"action": "__done__", "name": "完成"}'
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.3,
            max_tokens=300,
            response_format={"type": "json_object"},
        )

        text = response.choices[0].message.content or ""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            logger.warning("LLM returned invalid JSON, falling back: %s", text[:200])
            return self._decide_fallback(context)

    def _build_prompt(self, context: dict[str, Any]) -> str:
        """构建 LLM prompt"""
        step_history = json.dumps(
            context.get("results", []), ensure_ascii=False, indent=2
        )
        return (
            f"目标: {self.objective}\n\n"
            f"可用动作: {', '.join(self.available_actions)}\n\n"
            f"已执行步骤:\n{step_history}\n\n"
            "请决定下一步要执行什么动作。"
        )
