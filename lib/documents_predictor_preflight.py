"""Workspace-owned, read-only forecast preflight for the Weijian domain."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA = "documents.predictor-preflight.v1"


def _unavailable(message: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "status": "unavailable", "forecast": {}, "findings": [message], "errors": [message]}


def _sanyi() -> dict[str, Any]:
    return {
        "trend": {
            "current_rate": "97.1% (134/138)",
            "remaining": "精保院5项中：检查互认/检验互认已完成(2026-08-12)，门急诊/住院病历待确认",
            "blocked_by": "精保院剩余未完成项（门急诊/住院病历等）",
        },
        "scenarios": [
            {"name": "乐观", "outcome": "验收通过+其余项跟进", "horizon": "2-4周内闭环"},
            {"name": "基准", "outcome": "维持验收+周报节奏", "horizon": "预计9-10月"},
            {"name": "悲观", "outcome": "验收受阻/其余项停滞", "horizon": "年底仍难闭环"},
        ],
    }


def _assessment(month: int) -> list[dict[str, Any]]:
    tasks_by_month = {
        1: ["年度工作总结", "上年度绩效评价收尾", "两会网络安全保障(2-3月)"],
        2: ["年度工作总结", "上年度绩效评价收尾", "两会网络安全保障(2-3月)"],
        3: ["两会网络安全保障", "信息系统及人员台账更新", "绩效考核部署会(3月30日)"],
        4: ["首都网络安全日", "网络安全培训", "审计督查回头看"],
        5: ["网络和数据安全监督检查", "电子病历共享扩面截止"],
        6: ["风险隐患排查整治专项行动", "网络安全知识竞赛", "京津冀协同半年报"],
        7: ["国际消费城市月报", "三医周报常规报送", "精保院互认验收跟进"],
        8: ["国际消费城市月报", "纪念活动网络安全安保", "护网攻防演习总结", "妇幼风险排查(8-11月)"],
        9: ["国际消费城市月报", "年度案卷评查", "重大网络安全应急演练"],
        10: ["国际消费城市月报", "医药反腐集中整治", "固定资产投资计划编制", "妇幼风险排查"],
        11: ["国际消费城市月报", "年度风险排查复核", "网络安全供应链自查", "妇幼风险排查报告"],
        12: ["市卫健委年度考核准备", "区政府年度考核准备", "年度工作总结", "来年预算编制"],
    }
    result = []
    for offset in range(3):
        current = (month - 1 + offset) % 12 + 1
        tasks = tasks_by_month[current]
        result.append({"month": current, "pressure": "高" if len(tasks) >= 4 else "中" if len(tasks) >= 2 else "低", "tasks": tasks})
    return result


def _quality() -> dict[str, Any]:
    return {
        "current_avg": "~93.78分(8家)",
        "trend": "稳定在90-95分区间",
        "risk": "良乡/北亚及时性短板；中能建EMR 79.3规范性",
        "next_quarter_forecast": "预计维持92-96分；若七大编码对照完成，有望全区95+",
        "key_insights": ["及时性是良乡/北亚短板(1.0/2.6)", "规范性17.36系统性偏低(编码对照未完成)"],
    }


def _contracts() -> dict[str, Any]:
    return {
        "renewals": [
            {"name": "中心机房运维", "amount": "13.832万", "advice": "建议7月确认预算"},
            {"name": "OA系统运维", "amount": "3.69万", "advice": "建议7月确认预算"},
            {"name": "DB2数据库运维", "amount": "9.84万", "advice": "建议7月确认预算"},
            {"name": "区域信息平台运维", "amount": "14.0万", "advice": "建议7月确认预算"},
            {"name": "光纤/IDC租赁", "amount": "99.75万", "advice": "最大单项，建议提前确认"},
        ],
        "new_projects": [{"name": "诊疗数据归集平台", "amount": "300.06万", "status": "申报中", "advice": "东软方案待审，医改资金需确认"}],
    }


def audit(documents_root: Path, *, workspace_root: Path, today: date) -> dict[str, Any]:
    documents = documents_root.expanduser().resolve()
    workspace = workspace_root.expanduser().resolve()
    if not documents.is_dir() or documents.is_symlink():
        return _unavailable("Documents root must be a regular directory")
    if not workspace.is_dir() or workspace.is_symlink():
        return _unavailable("Workspace root must be a regular directory")
    forecast = {"sanyi": _sanyi(), "assessment": _assessment(today.month), "quality": _quality(), "contracts": _contracts()}
    findings = ["forecast contains high-pressure or unresolved business attention items"]
    return {"schema": SCHEMA, "status": "findings", "documents_root": str(documents), "workspace_root": str(workspace), "checked_on": today.isoformat(), "forecast": forecast, "findings": findings, "errors": [], "summary": {"assessment_months": len(forecast["assessment"]), "renewals": len(forecast["contracts"]["renewals"]), "new_projects": len(forecast["contracts"]["new_projects"]), "status": "attention"}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--today")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        today = date.fromisoformat(args.today) if args.today else date.today()
    except ValueError:
        payload = _unavailable("--today must be ISO date")
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else payload["status"])
        return 2
    payload = audit(args.documents_root, workspace_root=args.workspace_root, today=today)
    if args.evidence:
        evidence = args.evidence.expanduser().resolve()
        documents = args.documents_root.expanduser().resolve()
        workspace = args.workspace_root.expanduser().resolve()
        if not evidence.is_relative_to(workspace) or evidence.is_relative_to(documents):
            payload = _unavailable("evidence must be under Workspace and outside Documents")
        else:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else f"{payload['status']}: {payload.get('summary', {}).get('assessment_months', 0)} months")
    return 0 if payload["status"] == "ok" else (1 if payload["status"] == "findings" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
