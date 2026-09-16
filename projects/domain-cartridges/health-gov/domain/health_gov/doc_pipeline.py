"""卫健公文全周期管线: 来文登记 → 拟办 → 批阅(署名) → 办结 → 红头导出 → 会议督办.

Deterministic local computation only (stdlib + reportlab for PDF export).
熔断语义: 涉密输入拒绝入库；发文字号格式不符拒绝登记；无署名批阅/办结拒绝落盘；
红头必备要素缺失阻止导出并返回错误条款清单；缺 reportlab 时显式抛错，不伪造 PDF.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

KINDS = ("notice", "letter", "minutes-task")
# Spec alias: xh-letter → letter (T7-06 design used xh-letter; keep both).
KIND_ALIASES = {"xh-letter": "letter"}
URGENCIES = ("normal", "urgent", "immediate")
CLASSIFICATIONS = ("public", "internal", "secret", "topsecret")
DECISIONS = ("同意", "退回", "转办")
STATUSES = ("registered", "drafted", "approved", "returned", "dispatched")

SECRET_LEVELS = {"secret", "topsecret"}

# 发文字号: 机关代字〔YYYY〕N号, 如 ×卫发〔2026〕12号
DOC_NO_RE = re.compile(r"^\S+〔\d{4}〕\d+号$")
# 成文日期全字: 2026年9月15日
FULL_DATE_RE = re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日$")

DEADLINE_DAYS = {"immediate": 1, "urgent": 3, "normal": 15}

# 拟办模板: (kind, urgency) → (拟办意见模板, 分办去向模板)
_OPINION_TEMPLATES = {
    "notice": "请{route}认真贯彻落实，并将落实情况按期反馈。",
    "letter": "请{route}研提回复意见，报审后按时复函。",
    "minutes-task": "请{route}按期办结并反馈办理结果，逾期纳入督办。",
}
_URGENCY_PREFIX = {"immediate": "【特急】", "urgent": "【加急】", "normal": ""}
_KIND_ROUTE = {"notice": "各相关科室", "letter": "业务对口科室", "minutes-task": "责任科室"}


def _parse_day(s: str) -> date:
    s = (s or "").strip()
    m = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return date.fromisoformat(s)


@dataclass
class IncomingDoc:
    doc_id: str
    title: str  # 标题须含事由+文种三要素(由 validate_redhead 校验)
    doc_no: str  # 发文字号
    kind: str  # notice | letter | minutes-task
    urgency: str = "normal"
    classification: str = "internal"
    source: str = ""
    received_date: str = ""
    agency: str = ""  # 发文机关标志(红头)
    recipients: str = ""  # 主送机关
    text: str = ""  # 正文
    printer: str = ""  # 印发机关(版记)
    printed_date: str = ""  # 印发日期(版记)
    status: str = "registered"
    deadline: str = ""  # 拟办后填写 YYYY-MM-DD
    last_decision: str = ""  # 最近一次批阅意见: 同意|退回|转办


@dataclass
class DraftOpinion:
    doc_id: str
    drafter: str
    opinion: str
    route: str
    deadline_days: int
    deadline: str


@dataclass
class Approval:
    doc_id: str
    approver: str
    decision: str  # 同意 | 退回 | 转办
    comment: str
    decided_at: str  # YYYY-MM-DD


@dataclass
class ActionItem:
    item: str
    owner: str
    due: str  # YYYY-MM-DD
    status: str = "open"  # open | done
    closed_by: str = ""


@dataclass
class MeetingMinutes:
    meeting_id: str
    topic: str
    held_date: str  # YYYY-MM-DD
    attendees: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    actions: list[ActionItem] = field(default_factory=list)


def register_incoming(**kwargs) -> IncomingDoc:
    """来文登记. 涉密/文号格式错/ kind 非法 → ValueError(拒绝入库)."""
    doc = IncomingDoc(**kwargs)
    if doc.classification in SECRET_LEVELS:
        raise ValueError(f"涉密公文拒绝入库: classification={doc.classification}(涉密不上网)")
    doc.kind = KIND_ALIASES.get(doc.kind, doc.kind)
    if doc.kind not in KINDS:
        raise ValueError(f"非法文种: {doc.kind}")
    if doc.urgency not in URGENCIES:
        raise ValueError(f"非法缓急: {doc.urgency}")
    if not DOC_NO_RE.match(doc.doc_no or ""):
        raise ValueError(f"发文字号格式不符(机关代字〔YYYY〕N号): {doc.doc_no!r}")
    doc.status = "registered"
    doc.last_decision = ""
    return doc


def draft_opinion(doc: IncomingDoc, drafter: str, route: str = "") -> DraftOpinion:
    """拟办. registered/returned 可拟办；返回拟办单并回填 doc.deadline."""
    if doc.status not in ("registered", "returned"):
        raise ValueError(f"非法跃迁: {doc.status} → drafted(仅 registered/returned 可拟办)")
    if not drafter:
        raise ValueError("拟办人不能为空")
    route = route or _KIND_ROUTE[doc.kind]
    prefix = _URGENCY_PREFIX[doc.urgency]
    opinion = prefix + _OPINION_TEMPLATES[doc.kind].format(route=route)
    days = DEADLINE_DAYS[doc.urgency]
    base = _parse_day(doc.received_date) if doc.received_date else date.today()
    deadline = (base + timedelta(days=days)).isoformat()
    doc.deadline = deadline
    doc.status = "drafted"
    return DraftOpinion(doc_id=doc.doc_id, drafter=drafter, opinion=opinion,
                        route=route, deadline_days=days, deadline=deadline)


def approve(doc: IncomingDoc, approver: str, decision: str,
            comment: str = "", decided_at: str = "") -> Approval:
    """批阅. 仅 drafted 可批阅；无署名/非法decision/退回无意见 → 拒绝.

    决策分流: 同意→approved；退回→returned；转办→registered（重新拟办）.
    """
    if doc.status != "drafted":
        raise ValueError(f"非法跃迁: {doc.status} → approve(仅 drafted 可批阅)")
    if not approver:
        raise ValueError("无署名批阅无效: approver 为空")
    if decision not in DECISIONS:
        raise ValueError(f"非法批阅意见: {decision}")
    if decision == "退回" and not comment:
        raise ValueError("退回必须附意见: comment 为空")
    doc.last_decision = decision
    if decision == "同意":
        doc.status = "approved"
    elif decision == "退回":
        doc.status = "returned"
    else:  # 转办
        doc.status = "registered"
    return Approval(doc_id=doc.doc_id, approver=approver, decision=decision,
                    comment=comment, decided_at=decided_at or date.today().isoformat())


def dispatch(doc: IncomingDoc) -> IncomingDoc:
    """办结/发出. 仅 approved 且 last_decision=同意 可办结."""
    if doc.status != "approved" or doc.last_decision != "同意":
        raise ValueError(
            f"非法跃迁: status={doc.status} decision={doc.last_decision!r} "
            "→ dispatched(仅 approved+同意 可办结)"
        )
    doc.status = "dispatched"
    return doc


def is_overdue(doc: IncomingDoc, today: str = "") -> bool:
    if doc.status == "dispatched" or not doc.deadline:
        return False
    return (today or date.today().isoformat()) > doc.deadline


def validate_redhead(doc: IncomingDoc) -> list[str]:
    """GB/T 9704-2012 版式必备要素校验(下行/平行文子集). 返回错误条款清单, 空=通过."""
    errors: list[str] = []
    if not doc.agency:
        errors.append("缺发文机关标志(红头)")
    if not DOC_NO_RE.match(doc.doc_no or ""):
        errors.append(f"发文字号不合规: {doc.doc_no!r}")
    if not doc.title or len(doc.title) < 6:
        errors.append("标题缺失或过短")
    if not doc.recipients:
        errors.append("缺主送机关")
    if not doc.text:
        errors.append("缺正文")
    if not FULL_DATE_RE.match(doc.received_date or "") and not FULL_DATE_RE.match(doc.printed_date or ""):
        errors.append("缺全字成文日期(YYYY年M月D日)")
    if not doc.printer or not doc.printed_date:
        errors.append("缺版记(印发机关+印发日期)")
    return errors


def render_redhead_text(doc: IncomingDoc, approval: Approval | None = None) -> str:
    lines = [
        "★" * 31,
        doc.agency.center(30),
        "★" * 31,
        doc.doc_no.center(30),
        "─" * 31,
        f"标  题：{doc.title}",
        f"主送机关：{doc.recipients}",
        "",
        doc.text,
        "",
    ]
    if approval is not None:
        lines.append(f"批阅：{approval.decision}  签发人：{approval.approver}  {approval.decided_at}")
        if approval.comment:
            lines.append(f"批阅意见：{approval.comment}")
    lines += [
        "",
        f"成文日期：{doc.printed_date or doc.received_date}".rjust(30),
        "",
        f"（印章：{doc.agency}）".rjust(30),
        "",
        "─" * 31,
        f"抄送：{doc.source}" if doc.source else "抄送：—",
        f"印发机关：{doc.printer}  印发日期：{doc.printed_date}",
    ]
    return "\n".join(lines) + "\n"


def export_package(doc: IncomingDoc, out_dir: str | Path,
                   approval: Approval | None = None) -> dict[str, str]:
    """红头导出二件套: redhead.txt(版式文本) + redhead.pdf(真实PDF).

    要素校验不通过 → ValueError(阻止导出, 错误条款随异常带出).
    缺 reportlab → RuntimeError(显式抛错，不伪造空 PDF).
    """
    errors = validate_redhead(doc)
    if errors:
        raise ValueError("版式要素缺失，阻止导出: " + "；".join(errors))
    if approval is not None and approval.decision != "同意":
        raise ValueError(f"非同意批阅不可导出红头: decision={approval.decision!r}")
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except ImportError as e:
        raise RuntimeError("PDF 导出需 reportlab(uv pip install reportlab)，不伪造空 PDF") from e

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    txt_path = out / f"{doc.doc_id}-redhead.txt"
    txt_path.write_text(render_redhead_text(doc, approval), encoding="utf-8")

    font_candidates = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ]
    font_file = next((f for f in font_candidates if Path(f).exists()), None)
    if font_file is None:
        raise RuntimeError("未找到系统 CJK 字体，PDF 无法渲染中文，不伪造输出")
    try:
        pdfmetrics.registerFont(TTFont("GovCJK", font_file, subfontIndex=0))
        font_name = "GovCJK"
    except Exception:
        pdfmetrics.registerFont(TTFont("GovCJK", font_file))
        font_name = "GovCJK"

    pdf_path = out / f"{doc.doc_id}-redhead.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4

    def wrap(text: str, max_w: float, fsize: int) -> list[str]:
        out_lines, cur = [], ""
        for ch in text:
            if pdfmetrics.stringWidth(cur + ch, font_name, fsize) <= max_w:
                cur += ch
            else:
                out_lines.append(cur)
                cur = ch
        if cur:
            out_lines.append(cur)
        return out_lines or [""]

    y = height - 72
    c.setFillColorRGB(0.8, 0, 0)
    c.setFont(font_name, 22)
    c.drawCentredString(width / 2, y, doc.agency)
    y -= 12
    c.setStrokeColorRGB(0.8, 0, 0)
    c.setLineWidth(2)
    c.line(72, y, width - 72, y)
    y -= 26
    c.setFillColorRGB(0, 0, 0)
    c.setFont(font_name, 12)
    c.drawCentredString(width / 2, y, doc.doc_no)
    y -= 30
    c.setFont(font_name, 16)
    for ln in wrap(doc.title, width - 144, 16):
        c.drawCentredString(width / 2, y, ln)
        y -= 24
    y -= 6
    c.setFont(font_name, 12)
    c.drawString(72, y, f"主送机关：{doc.recipients}")
    y -= 22
    for para in doc.text.split("\n"):
        for ln in wrap("　　" + para if para else "", width - 144, 12):
            if y < 120:
                c.showPage()
                c.setFont(font_name, 12)
                y = height - 72
            c.drawString(72, y, ln)
            y -= 18
    y -= 10
    if approval is not None:
        c.drawString(72, y, f"批阅：{approval.decision}  签发人：{approval.approver}  {approval.decided_at}")
        y -= 20
    c.drawRightString(width - 72, y, f"成文日期：{doc.printed_date or doc.received_date}")
    y -= 20
    c.drawRightString(width - 72, y, f"（印章：{doc.agency}）")
    y -= 30
    c.setFont(font_name, 10)
    c.drawString(72, y, f"印发机关：{doc.printer}  印发日期：{doc.printed_date}")
    c.showPage()
    c.save()
    return {"txt": str(txt_path), "pdf": str(pdf_path)}


def record_minutes(meeting_id: str, topic: str, held_date: str,
                   attendees: list[str], decisions: list[str],
                   actions: list[dict]) -> MeetingMinutes:
    if not meeting_id or not topic:
        raise ValueError("会议编号与议题不能为空")
    items = [ActionItem(**a) for a in actions]
    for a in items:
        if not a.owner or not a.due:
            raise ValueError(f"议定事项须明确责任人与时限: {a.item}")
    return MeetingMinutes(meeting_id=meeting_id, topic=topic, held_date=held_date,
                          attendees=list(attendees), decisions=list(decisions), actions=items)


def supervise(minutes: MeetingMinutes, today: str = "") -> dict:
    """督办检查 → 督办单(overdue 置顶 + 逾期天数)与汇总计数."""
    today_d = _parse_day(today) if today else date.today()
    督办, done_n, open_n, overdue_n = [], 0, 0, 0
    for a in minutes.actions:
        if a.status == "done":
            done_n += 1
            continue
        overdue_days = (today_d - _parse_day(a.due)).days
        if overdue_days > 0:
            overdue_n += 1
            督办.append({"item": a.item, "owner": a.owner, "state": "overdue",
                        "overdue_days": overdue_days})
        else:
            open_n += 1
            督办.append({"item": a.item, "owner": a.owner, "state": "open",
                        "overdue_days": 0})
    督办.sort(key=lambda r: (r["state"] != "overdue", -r["overdue_days"]))
    return {"meeting_id": minutes.meeting_id, "total": len(minutes.actions),
            "done": done_n, "open": open_n, "overdue": overdue_n, "督办": 督办}


def close_action(minutes: MeetingMinutes, item: str, closed_by: str) -> ActionItem:
    """办结议定事项. 无署名办结无效."""
    if not closed_by:
        raise ValueError("无署名办结无效: closed_by 为空")
    for a in minutes.actions:
        if a.item == item:
            a.status = "done"
            a.closed_by = closed_by
            return a
    raise ValueError(f"未找到议定事项: {item}")
