"""Workflow Registry — Pre-built GraphWorkflow templates for common agent tasks.

Maps domain-specific workflows to GraphWorkflow definitions, so the CLI
and Hatcher can create standardized workflows without inline node definitions.

Usage::

    from swarm_engine.workflow_registry import WorkflowRegistry

    wf = WorkflowRegistry.create("default")
    state = wf.run({"goal": "检查邮件并分类"})
"""

from __future__ import annotations

from typing import Any

from .graph_workflow import GraphWorkflow
from .intelligent_agent import IntelligentAgent


class WorkflowRegistry:
    """Registry of pre-built GraphWorkflow templates."""

    @classmethod
    def create(cls, template_id: str = "default") -> GraphWorkflow:
        """Create a GraphWorkflow from a registered template.

        Templates:
            - "default": Plan → Execute (general purpose)
            - "mail": Read → Classify → Extract → Brief
            - "admin": Plan → Forward → Collect → Compile → Review → Submit
        """
        builders = {
            "default": cls._build_default,
            "mail": cls._build_mail_pipeline,
            "admin": cls._build_admin_pipeline,
        }
        builder = builders.get(template_id, cls._build_default)
        return builder()

    # ── Template: default (plan → execute) ──────────────────────────────

    @staticmethod
    def _build_default() -> GraphWorkflow:
        """General-purpose plan → execute workflow."""
        wf = GraphWorkflow()

        @wf.node("任务规划", description="分析并分解任务目标")
        def plan_task(state: dict[str, Any]) -> dict[str, Any]:
            goal = state.get("goal", "")
            agent = IntelligentAgent("planner", state.get("domain", "work"))
            result = agent.decide(
                question=f"将以下任务目标拆解为3步，仅输出简短文本：{goal}",
                context={"goal": goal},
                action={"type": "classify", "target": "self"},
            )
            return {"plan": result.get("response") or f"分析目标: {goal}"}

        @wf.node("任务执行", description="执行具体计划")
        def execute_task(state: dict[str, Any]) -> dict[str, Any]:
            plan = state.get("plan", "")
            agent = IntelligentAgent("executor", state.get("domain", "work"))
            result = agent.decide(
                question=f"根据计划执行任务，简洁回答：{plan[:200]}",
                context={"plan": plan[:500]},
                action={"type": "generate", "target": "self"},
            )
            return {"output": result.get("response") or f"成功执行:\n{plan}"}

        wf.add_edge("任务规划", "任务执行")
        wf.set_entry("任务规划")
        return wf

    # ── Template: mail pipeline ─────────────────────────────────────────

    @staticmethod
    def _build_mail_pipeline() -> GraphWorkflow:
        """Mail processing: read → classify → extract → brief."""
        wf = GraphWorkflow()

        @wf.node("读取邮件", description="从邮箱读取最新邮件")
        def read_mail(state: dict[str, Any]) -> dict[str, Any]:
            agent = IntelligentAgent("mail-agent", "work")
            result = agent.decide(
                question="读取最近的工作邮件，返回主题列表",
                context={"action": "read_mail"},
                action={"type": "read", "target": "self"},
            )
            return {"mails_raw": result.get("response", "")}

        @wf.node("分类邮件", description="LLM 分类邮件")
        def classify_mail(state: dict[str, Any]) -> dict[str, Any]:
            raw = state.get("mails_raw", "")
            agent = IntelligentAgent("mail-agent", "work")
            result = agent.decide(
                question=f"对以下邮件进行分类(通知/任务/参考/垃圾/个人)：\n{raw[:500]}",
                context={"mails": raw[:500]},
                action={"type": "classify", "target": "self"},
            )
            return {"classified": result.get("response", "")}

        @wf.node("生成日报", description="生成 Markdown 日报")
        def generate_brief(state: dict[str, Any]) -> dict[str, Any]:
            classified = state.get("classified", "")
            agent = IntelligentAgent("mail-agent", "work")
            result = agent.decide(
                question=f"根据分类结果生成简洁的 Markdown 日报：\n{classified[:500]}",
                context={"classified": classified[:500]},
                action={"type": "generate", "target": "self"},
            )
            return {"briefing": result.get("response", "")}

        wf.add_edge("读取邮件", "分类邮件")
        wf.add_edge("分类邮件", "生成日报")
        wf.set_entry("读取邮件")
        return wf

    # ── Template: admin pipeline ────────────────────────────────────────

    @staticmethod
    def _build_admin_pipeline() -> GraphWorkflow:
        """Admin workflow: plan → forward → compile → review."""
        wf = GraphWorkflow()

        @wf.node("任务分析", description="分析行政任务要求")
        def analyze(state: dict[str, Any]) -> dict[str, Any]:
            goal = state.get("goal", "")
            agent = IntelligentAgent("admin-workflow", "work")
            result = agent.decide(
                question=f"分析行政任务，输出JSON(task_type, deadline, target)：{goal}",
                context={"goal": goal},
                action={"type": "classify", "target": "self"},
            )
            return {"analysis": result.get("response", "")}

        @wf.node("生成草稿", description="生成转发通知和数据收集表草稿")
        def generate_drafts(state: dict[str, Any]) -> dict[str, Any]:
            analysis = state.get("analysis", "")
            agent = IntelligentAgent("doc-generator", "work")
            result = agent.decide(
                question=f"根据分析结果生成通知草稿：{analysis[:300]}",
                context={"analysis": analysis[:300]},
                action={"type": "generate", "target": "subordinate"},
            )
            return {"drafts": result.get("response", "")}

        @wf.node("汇总报告", description="汇总并生成报告")
        def compile_report(state: dict[str, Any]) -> dict[str, Any]:
            drafts = state.get("drafts", "")
            agent = IntelligentAgent("admin-workflow", "work")
            result = agent.decide(
                question=f"汇总以下内容生成报告：{drafts[:300]}",
                context={"drafts": drafts[:300]},
                action={"type": "generate", "target": "self"},
            )
            return {"report": result.get("response", "")}

        @wf.node("审阅提交", description="生成提交邮件草稿")
        def review_submit(state: dict[str, Any]) -> dict[str, Any]:
            report = state.get("report", "")
            agent = IntelligentAgent("admin-workflow", "work")
            result = agent.decide(
                question=f"审阅报告并生成提交摘要：{report[:300]}",
                context={"report": report[:300]},
                action={"type": "submit", "target": "superior", "domain": "work"},
            )
            return {"submission": result.get("response", "")}

        wf.add_edge("任务分析", "生成草稿")
        wf.add_edge("生成草稿", "汇总报告")
        wf.add_edge("汇总报告", "审阅提交")
        wf.set_entry("任务分析")
        return wf
