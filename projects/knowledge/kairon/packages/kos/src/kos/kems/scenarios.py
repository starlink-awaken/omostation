"""Deterministic analyzers for the three P2 KEMS operating scenarios."""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ScenarioEvidence:
    line: int
    excerpt: str
    kind: str


@dataclass(frozen=True)
class ScenarioAnalysis:
    schema_version: str
    scenario_id: str
    metrics: dict[str, Any]
    insights: tuple[str, ...]
    recommendations: tuple[str, ...]
    evidence: tuple[ScenarioEvidence, ...]
    review_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["insights"] = list(self.insights)
        result["recommendations"] = list(self.recommendations)
        result["evidence"] = [asdict(item) for item in self.evidence]
        result["review_flags"] = list(self.review_flags)
        return result


def _rows(content: str) -> list[tuple[int, dict[str, str]]]:
    lines = [line for line in content.splitlines() if line.strip()]
    if not lines:
        raise ValueError("scenario data must not be empty")
    sample = "\n".join(lines[:4])
    dialect = csv.Sniffer().sniff(sample, delimiters=",\t|;")
    reader = csv.DictReader(io.StringIO("\n".join(lines)), dialect=dialect)
    return [
        (index + 2, {str(k).strip(): (v or "").strip() for k, v in row.items()}) for index, row in enumerate(reader)
    ]


def _value(row: dict[str, str], *names: str) -> str:
    for name in names:
        if name in row and row[name]:
            return row[name]
    return ""


def analyze_reconsideration(content: str) -> ScenarioAnalysis:
    """Aggregate synthetic or exported reconsideration-case tabular data."""
    rows = _rows(content)
    statuses = Counter(_value(row, "状态", "status", "案件状态") or "未知" for _, row in rows)
    regions = Counter(_value(row, "地区", "region", "地市") or "未知" for _, row in rows)
    high_risk = [
        (line, row)
        for line, row in rows
        if any(word in _value(row, "风险", "risk", "问题").lower() for word in ("高", "high", "重大"))
    ]
    evidence = tuple(
        ScenarioEvidence(line, " | ".join(f"{k}={v}" for k, v in row.items() if v)[:240], "high_risk")
        for line, row in high_risk[:10]
    )
    insights = (
        f"共 {len(rows)} 件，状态分布为 {dict(statuses)}。",
        f"地区覆盖 {len(regions)} 个，最多为 {regions.most_common(1)[0][0]}。",
    )
    recommendations = (
        ("优先复核标记为高风险的案件，并补齐缺失地区或状态。",)
        if high_risk
        else ("建立风险字段人工复核集，再进行趋势判断。",)
    )
    flags = ("risk_field_not_detected",) if not high_risk else ()
    return ScenarioAnalysis(
        "kems.reconsideration-analysis.v1",
        "administrative-reconsideration",
        {"total": len(rows), "statuses": dict(statuses), "regions": dict(regions), "high_risk_count": len(high_risk)},
        insights,
        recommendations,
        evidence,
        flags,
    )


def analyze_ai_survey(content: str) -> ScenarioAnalysis:
    """Aggregate AI-application survey responses without inferring missing answers."""
    rows = _rows(content)
    statuses = Counter(_value(row, "进度", "状态", "status") or "未填" for _, row in rows)
    departments = Counter(_value(row, "单位", "部门", "department") or "未填" for _, row in rows)
    missing = [line for line, row in rows if any(not value for value in row.values())]
    evidence = tuple(ScenarioEvidence(line, f"survey row {line}", "missing_field") for line in missing[:10])
    insights = (f"收到 {len(rows)} 份反馈，进度分布为 {dict(statuses)}。", f"涉及 {len(departments)} 个单位。")
    recommendations = ("向缺失字段的单位发出补报提醒。",) if missing else ("按进度分层生成汇总报告，并进入人工确认。",)
    flags = ("incomplete_responses",) if missing else ()
    return ScenarioAnalysis(
        "kems.ai-survey-analysis.v1",
        "ai-application-survey",
        {
            "response_count": len(rows),
            "statuses": dict(statuses),
            "departments": dict(departments),
            "missing_row_count": len(missing),
        },
        insights,
        recommendations,
        evidence,
        flags,
    )


_TASK = re.compile(r"(?:任务|事项)\s*[:：]\s*(?P<task>[^；;\n]+)")
_OWNER = re.compile(r"(?:责任人|负责人|牵头人)\s*[:：]\s*(?P<owner>[^；;\n]+)")
_DUE = re.compile(r"(?:截止|完成时间|时限)\s*[:：]\s*(?P<due>[^；;\n]+)")


def analyze_tri_medical_minutes(content: str) -> ScenarioAnalysis:
    """Extract accountable actions from 三医 meeting minutes with evidence."""
    tasks: list[dict[str, str]] = []
    evidence: list[ScenarioEvidence] = []
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        task = _TASK.search(line)
        if not task and not any(word in line for word in ("负责", "牵头", "完成")):
            continue
        item = {
            "task": task.group("task").strip() if task else line[:160],
            "owner": (_OWNER.search(line).group("owner").strip() if _OWNER.search(line) else ""),  # type: ignore[reportOptionalMemberAccess]
            "due": (_DUE.search(line).group("due").strip() if _DUE.search(line) else ""),  # type: ignore[reportOptionalMemberAccess]
        }
        tasks.append(item)
        evidence.append(ScenarioEvidence(line_number, line[:240], "task"))
    missing_owner = sum(not task["owner"] for task in tasks)
    missing_due = sum(not task["due"] for task in tasks)
    flags = tuple(
        flag for flag, count in (("missing_owner", missing_owner), ("missing_due_date", missing_due)) if count
    )
    recommendations = (
        ("补齐责任人和截止时间后再进入协同派发。",) if flags else ("将已抽取事项生成待办并关联原会议纪要。",)
    )
    return ScenarioAnalysis(
        "kems.tri-medical-task-analysis.v1",
        "tri-medical-informatization",
        {
            "task_count": len(tasks),
            "tasks": tasks,
            "missing_owner_count": missing_owner,
            "missing_due_count": missing_due,
        },
        (f"识别到 {len(tasks)} 项会议任务。",),
        recommendations,
        tuple(evidence[:20]),
        flags,
    )
