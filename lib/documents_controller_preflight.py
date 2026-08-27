"""Workspace-owned, read-only parity preflight for the Weijian controller."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "documents.controller-preflight.v1"
RULE_IDS = ("CR01", "CR02", "CR03", "CR05", "CR08", "CR23", "CR24", "CR25", "CR26", "CR29", "CR30")
PLANES = ("_control", "_entities", "_meta", "_runtime", "_storage", "_knowledge")
STAGES = ("00-需求", "01-申报", "02-审批", "03-招采", "04-合同", "05-实施", "06-验收", "07-运维", "08-绩效审计", "99-归档")
MACHINE_TYPES = ("🔴", "⚠️")
_REVIEWED = re.compile(r"(?mi)^\s*last-reviewed[:：]\s*(\d{4}-\d{2}-\d{2})")
_SIGNAL = re.compile(r"(?m)^\s*(?:-\s*)?type:\s*(🔴|⚠️|✅)")


def _unavailable(message: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "status": "unavailable", "rules": {}, "findings": [message], "errors": [message]}


def _rule(status: str = "ok", *, findings: list[str] | None = None, **details: Any) -> dict[str, Any]:
    return {"status": status, "findings": findings or [], **details}


def _read(path: Path) -> str | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _signals(domain: Path) -> tuple[dict[str, Any], list[str]]:
    text = _read(domain / "_control" / "signals.md")
    if text is None:
        return _rule("unavailable", findings=["signals.md missing or unreadable"]), ["signals.md missing or unreadable"]
    counts = {"red": text.count("type: 🔴"), "warning": text.count("type: ⚠️"), "ok": text.count("type: ✅")}
    findings: list[str] = []
    if counts["red"]:
        findings.append(f"{counts['red']} red signal(s)")
    if counts["warning"] >= 3:
        findings.append(f"{counts['warning']} warning signals")
    return _rule("findings" if findings else "ok", findings=findings, counts=counts), findings


def _freshness(domain: Path, today: date) -> tuple[dict[str, Any], list[str], list[str]]:
    stale_30: list[str] = []
    stale_60: list[str] = []
    broken: list[str] = []
    scanned = 0
    for plane in PLANES:
        root = domain / plane
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if path.is_symlink():
                continue
            text = _read(path)
            if text is None:
                broken.append(str(path.relative_to(domain)))
                continue
            match = _REVIEWED.search(text[:4096])
            if not match:
                continue
            try:
                age = (today - date.fromisoformat(match.group(1))).days
            except ValueError:
                broken.append(str(path.relative_to(domain)))
                continue
            scanned += 1
            if age > 60:
                stale_60.append(str(path.relative_to(domain)))
            elif age > 30:
                stale_30.append(str(path.relative_to(domain)))
    findings = []
    if stale_30 or stale_60:
        findings.append(f"stale markdown: 30-60d={len(stale_30)}, 60d+={len(stale_60)}")
    if broken:
        findings.append(f"unreadable/invalid markdown: {len(broken)}")
    return _rule("findings" if findings else "ok", findings=findings, scanned=scanned, stale_30_60=stale_30, stale_60=stale_60, broken=broken), stale_30, stale_60


def _model_rule(domain: Path) -> dict[str, Any]:
    facts = _read(domain / "_entities" / "facts.md")
    facts_match = _REVIEWED.search(facts or "")
    models = sorted((domain / "_entities" / "models").glob("*.md")) if (domain / "_entities" / "models").is_dir() else []
    stale = []
    if facts_match:
        for model in models:
            match = _REVIEWED.search(_read(model) or "")
            if match and match.group(1) < facts_match.group(1):
                stale.append(model.name)
    findings = [f"{len(stale)} model(s) older than facts view"] if stale else []
    return _rule("findings" if findings else "ok", findings=findings, facts_last_reviewed=facts_match.group(1) if facts_match else None, model_count=len(models), stale_models=stale)


def _yaml_exists(path: Path) -> tuple[bool, str]:
    text = _read(path)
    if text is None:
        return False, "missing"
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError:
        return False, "invalid yaml"
    return True, "ok" if value is not None else "empty"


def _project_rules(domain: Path) -> dict[str, Any]:
    archive = domain / "_knowledge" / "业务资料" / "01-业务核心" / "信息化项目" / "01-项目全生命周期" / "00-项目主档案"
    if not archive.is_dir():
        return {"CR25": _rule("findings", findings=["project archive missing"]), "CR26": _rule("ok"), "CR29": _rule("findings", findings=["project archive missing"]), "CR30": _rule("findings", findings=["project archive missing"])}
    projects = sorted(path for path in archive.iterdir() if path.is_dir() and not path.name.startswith(".") and path.name not in {"99-已归档项目", "01-项目台账"})
    missing_stages = {path.name: [stage for stage in STAGES if not (path / stage).is_dir()] for path in projects}
    missing_stages = {name: missing for name, missing in missing_stages.items() if missing}
    missing_materials = 0
    keywords = ("建议书", "可行性研究", "申报表", "数据资源", "申报函", "库表目录", "数据目录", "资源目录", "预算", "初步设计", "绩效目标", "批示", "专家评审")
    for project in projects:
        files = [item.name for item in (project / "01-申报").rglob("*") if item.is_file()] if (project / "01-申报").is_dir() else []
        missing_materials += sum(not any(keyword in name for name in files) for keyword in keywords)
    project_checks = {"CR25": _rule("ok"), "CR26": _rule("ok"), "CR29": _rule("findings" if missing_stages else "ok", findings=[f"missing stages in {len(missing_stages)} project(s)"] if missing_stages else [], projects=len(projects), missing_stages=missing_stages), "CR30": _rule("findings" if missing_materials else "ok", findings=[f"missing material categories: {missing_materials}"] if missing_materials else [], projects=len(projects), missing_materials=missing_materials)}
    for filename, rule in (("key-milestones.yaml", "CR25"), ("gaps.yaml", "CR25")):
        exists, state = _yaml_exists(domain / "_control" / filename if filename == "key-milestones.yaml" else domain / "_entities" / "ontology" / filename)
        if not exists:
            project_checks[rule]["status"] = "findings"
            project_checks[rule]["findings"].append(f"{filename}: {state}")
    return project_checks


def audit(documents_root: Path, *, workspace_root: Path, domain_relative: str, today: date) -> dict[str, Any]:
    documents = documents_root.expanduser().resolve()
    workspace = workspace_root.expanduser().resolve()
    if not documents.is_dir() or documents.is_symlink():
        return _unavailable("Documents root must be a regular directory")
    if not workspace.is_dir() or workspace.is_symlink():
        return _unavailable("Workspace root must be a regular directory")
    relative = Path(domain_relative)
    if relative.is_absolute() or ".." in relative.parts:
        return _unavailable("domain-relative must be relative and non-traversing")
    domain = (documents / relative).resolve()
    try:
        domain.relative_to(documents)
    except ValueError:
        return _unavailable("domain-relative escapes Documents root")
    if not domain.is_dir() or domain.is_symlink():
        return _unavailable("Weijian domain must be a regular directory")
    signal_rule, signal_findings = _signals(domain)
    freshness_rule, stale_30, stale_60 = _freshness(domain, today)
    project_rules = _project_rules(domain)
    ocr_files = sorted((domain / "_storage" / "06-工具" / "批量提取" / "ocr_20260731" / "lists").glob("ocr_*.json"))
    rules: dict[str, dict[str, Any]] = {
        "CR01": _rule("findings" if signal_rule["counts"]["red"] else "ok", findings=[f"{signal_rule['counts']['red']} red signal(s)"] if signal_rule["counts"]["red"] else [], counts=signal_rule["counts"]),
        "CR02": _rule("findings" if signal_rule["counts"]["warning"] >= 3 else "ok", findings=[f"{signal_rule['counts']['warning']} warning signals"] if signal_rule["counts"]["warning"] >= 3 else [], counts=signal_rule["counts"]),
        "CR03": freshness_rule,
        "CR05": _rule("findings" if stale_60 else "ok", findings=[f"{len(stale_60)} files stale over 60 days"] if stale_60 else [], count=len(stale_60)),
        "CR08": _rule("findings" if freshness_rule["broken"] else "ok", findings=[f"{len(freshness_rule['broken'])} unreadable/invalid files"] if freshness_rule["broken"] else [], count=len(freshness_rule["broken"])),
        "CR23": _rule("findings" if ocr_files else "ok", findings=[f"{len(ocr_files)} OCR list(s) remain"] if ocr_files else [], count=len(ocr_files)),
        "CR24": _model_rule(domain),
        "CR26": _rule("ok", findings=[]),
        **project_rules,
    }
    findings = [f"{rule_id}: {item}" for rule_id, rule in rules.items() for item in rule.get("findings", [])]
    return {"schema": SCHEMA, "status": "findings" if findings else "ok", "documents_root": str(documents), "workspace_root": str(workspace), "domain_relative": domain_relative, "rules": {key: rules[key] for key in RULE_IDS}, "findings": findings, "errors": [], "summary": {"rules": len(rules), "rule_findings": sum(item["status"] == "findings" for item in rules.values()), "findings": len(findings)}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--domain-relative", default="@工作文档/卫健委")
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
    payload = audit(args.documents_root, workspace_root=args.workspace_root, domain_relative=args.domain_relative, today=today)
    if args.evidence:
        evidence = args.evidence.expanduser().resolve()
        documents = args.documents_root.expanduser().resolve()
        workspace = args.workspace_root.expanduser().resolve()
        if not evidence.is_relative_to(workspace) or evidence.is_relative_to(documents):
            payload = _unavailable("evidence must be under Workspace and outside Documents")
        else:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else f"{payload['status']}: {payload.get('summary', {}).get('findings', 0)} findings")
    return 0 if payload["status"] == "ok" else (1 if payload["status"] == "findings" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
