#!/usr/bin/env python3
"""Admin Workflow Scenes — 9步行政流程的 scene dispatch 实现.

每个函数对应 journey spec 中的一个 state, 被 journey-runner 调用.
通过 risk_engine 做安全检查, 通过 _llm_helper 接入 AetherForge 算力.

Scene IDs:
  admin-inbox      → 读邮件+分类
  admin-classify   → 任务分解+截止识别
  admin-forward    → 生成转发通知+表格+邮件草稿
  admin-collect    → 注册截止追踪+检查回复
  admin-compile    → 汇总回复+生成报告
  admin-review     → 生成发领导的邮件草稿
  admin-submit     → 生成提交邮件+归档
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from _shared import ROOT, utc_now


def dispatch_admin_inbox(input_data: dict, token: dict) -> dict[str, Any]:
    """State: received → 读邮件 + LLM分类."""
    from mail_reader import read_netease_mail
    from mail_agent import classify_mail

    # 读最近工作邮件
    mails = read_netease_mail("work", limit=5, unread_only=True)
    if not mails:
        mails = read_netease_mail("work", limit=3, unread_only=False)

    if not mails:
        return {"status": "succeeded", "mails": [], "has_task": False}

    # LLM 分类第一封
    classified = []
    for m in mails[:3]:
        cls = classify_mail(m)
        classified.append({"subject": m.subject, "sender": m.sender, "category": cls.get("category"), "priority": cls.get("priority"), "summary": cls.get("summary", "")})

    has_task = any(c["category"] == "任务" for c in classified)

    return {
        "status": "succeeded",
        "mails": classified,
        "has_task": has_task,
        "latest_subject": classified[0]["subject"] if classified else "",
    }


def dispatch_admin_classify(input_data: dict, token: dict) -> dict[str, Any]:
    """State: classified → 任务分解 + 截止/目标识别."""
    from _llm_helper import llm_ask

    subject = input_data.get("latest_subject", "")
    mails = input_data.get("mails", [])
    if not subject and mails:
        subject = mails[0].get("subject", "")

    if not subject:
        return {"status": "succeeded", "requires_forwarding": False, "task_type": "none"}

    # LLM 任务分解
    response = llm_ask(
        f"分析这个工作任务, 输出 JSON:\n标题: {subject}\n\n"
        f'{{"requires_forwarding": true/false, "task_type": "转发通知/收集数据/提交报告", '
        f'"deadline": "预估截止时间", "target": "转发对象", "required_docs": "需要什么文档"}}',
        timeout=30.0,
    )

    result = {"requires_forwarding": True, "task_type": "转发通知", "deadline": "", "target": ""}
    if response:
        import re
        m = re.search(r'\{.*\}', response, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group())
            except Exception:
                pass

    return {"status": "succeeded", **result}


def dispatch_admin_forward(input_data: dict, token: dict) -> dict[str, Any]:
    """State: forwarding → 生成转发通知 + 表格 + 邮件草稿."""
    from doc_generator import generate_doc, save_draft
    from mail_sender import create_draft

    subject = input_data.get("latest_subject", "工作任务")
    target = input_data.get("target", "各相关单位")
    deadline = input_data.get("deadline", "")

    # risk check
    try:
        from risk_engine import RiskEngine, Action
        engine = RiskEngine()
        decision = engine.evaluate(Action(type="forward", target="subordinate", domain="work"))
        if decision.is_forbidden():
            return {"status": "blocked", "reason": "risk_engine: L4 forbidden"}
    except Exception:
        pass

    # 生成转发通知草稿
    context = {"title": subject, "target": target, "deadline": deadline, "source_subject": subject}
    notice = generate_doc("forward_notice", context)
    notice_path = save_draft("forward_notice", notice)

    # 生成数据收集表草稿
    form = generate_doc("data_collection", context)
    form_path = save_draft("data_collection", form)

    return {
        "status": "succeeded",
        "email_drafts_created": True,
        "notice_draft": str(notice_path),
        "form_draft": str(form_path),
        "requires_human_confirm": True,  # 发邮件前需人确认
    }


def dispatch_admin_collect(input_data: dict, token: dict) -> dict[str, Any]:
    """State: collecting → 注册截止追踪 + 检查回复."""
    try:
        from deadline_tracker import register_task, load_tasks
        subject = input_data.get("latest_subject", "工作任务")
        deadline = input_data.get("deadline", "")
        target = input_data.get("target", "")

        register_task(subject, deadline, target, input_data.get("task_type", "收集数据"))

        return {
            "status": "succeeded",
            "deadline_registered": True,
            "task_subject": subject,
            "awaiting_replies": True,
        }
    except Exception as e:
        return {"status": "succeeded", "deadline_registered": False, "error": str(e)[:100], "awaiting_replies": True}


def dispatch_admin_compile(input_data: dict, token: dict) -> dict[str, Any]:
    """State: compiling → 汇总回复 + 生成报告."""
    from doc_generator import generate_doc, save_draft

    subject = input_data.get("latest_subject", "工作报告")
    context = {
        "title": f"关于{subject}的汇总报告",
        "source_subject": subject,
        "deadline": input_data.get("deadline", ""),
    }

    report = generate_doc("summary_report", context)
    report_path = save_draft("summary_report", report)

    return {
        "status": "succeeded",
        "report_compiled": True,
        "report_draft": str(report_path),
    }


def dispatch_admin_review(input_data: dict, token: dict) -> dict[str, Any]:
    """State: reviewing → 生成发领导的邮件草稿."""
    from mail_sender import create_draft

    subject = input_data.get("latest_subject", "工作报告")
    report_path = input_data.get("report_draft", "")

    attachments = [report_path] if report_path else []

    # risk check: 发给领导 = L3
    try:
        from risk_engine import RiskEngine, Action
        engine = RiskEngine()
        decision = engine.evaluate(Action(type="send_email", target="leader", domain="work"))
        if decision.is_forbidden():
            return {"status": "blocked", "reason": "risk_engine: L4 forbidden"}
    except Exception:
        pass

    draft_path = create_draft(
        to="leader@bjfsh.gov.cn",  # 占位, 人审阅时修改
        subject=f"关于{subject}的报告（请审阅）",
        body=f"领导您好：\n\n关于{subject}的工作已完成汇总，报告见附件。\n请审阅指示。\n\n此致\n敬礼",
        attachments=attachments,
    )

    return {
        "status": "succeeded",
        "leader_email_draft": str(draft_path),
        "requires_human_confirm": True,
    }


def dispatch_admin_submit(input_data: dict, token: dict) -> dict[str, Any]:
    """State: submitted → 生成提交邮件 + 归档."""
    from mail_sender import create_draft

    subject = input_data.get("latest_subject", "工作任务")

    # risk check: 提交上级 = L3
    try:
        from risk_engine import RiskEngine, Action
        engine = RiskEngine()
        decision = engine.evaluate(Action(type="submit", target="superior", domain="work"))
        if decision.is_forbidden():
            return {"status": "blocked", "reason": "risk_engine: L4 forbidden"}
    except Exception:
        pass

    draft_path = create_draft(
        to="superior@bjfsh.gov.cn",
        subject=f"关于{subject}的提交",
        body=f"根据通知要求，现将{subject}相关材料提交，请查收。",
    )

    # 记录 trust outcome
    try:
        from risk_engine import RiskEngine, Action
        engine = RiskEngine()
        engine.record_outcome(Action(type="submit", target="superior"), True)
    except Exception:
        pass

    return {
        "status": "succeeded",
        "submission_draft": str(draft_path),
        "task_completed": True,
    }


# ── 注册到 DISPATCHERS ─────────────────────────────────────

ADMIN_SCENES = {
    "admin-inbox": dispatch_admin_inbox,
    "admin-classify": dispatch_admin_classify,
    "admin-forward": dispatch_admin_forward,
    "admin-collect": dispatch_admin_collect,
    "admin-compile": dispatch_admin_compile,
    "admin-review": dispatch_admin_review,
    "admin-submit": dispatch_admin_submit,
}
