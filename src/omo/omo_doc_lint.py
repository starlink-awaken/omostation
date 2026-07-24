from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .omo_io import write_text_atomic
from .omo_shared import load_yaml_docs
from .opc_phase_paths import resolve_opc_phase_task_path


def doc_lint_index_path(workspace_root: Path) -> Path:
    return workspace_root / ".omo" / "_delivery" / "doc-lint" / "index.json"


def load_doc_lint_index(workspace_root: Path) -> dict[str, Any]:
    path = doc_lint_index_path(workspace_root)
    if not path.exists():
        return {"runs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"runs": []}


def update_doc_lint_index(
    workspace_root: Path, findings: dict[str, Any]
) -> dict[str, Any]:
    index = load_doc_lint_index(workspace_root)
    runs = [
        run
        for run in index.get("runs", [])
        if run.get("generated_at") != findings["generated_at"]
    ]
    runs.append(
        {
            "generated_at": findings["generated_at"],
            "drift_total": findings["drift_total"],
            "dead_links": len(findings["dead_links"]),
            "term_issues": len(findings["term_consistency_issues"]),
        }
    )
    runs.sort(key=lambda item: item["generated_at"])
    index["runs"] = runs[-30:]
    index["summary"] = {
        "run_count": len(index["runs"]),
        "latest_drift_total": index["runs"][-1]["drift_total"]
        if index["runs"]
        else None,
    }
    write_text_atomic(
        doc_lint_index_path(workspace_root),
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
    )
    return index


def write_doc_lint_outputs(
    workspace_root: Path, findings: dict[str, Any], today: str
) -> tuple[Path, Path]:
    out_dir = workspace_root / ".omo" / "_delivery" / "doc-lint"
    json_path = out_dir / f"{today}.json"
    write_text_atomic(
        json_path,
        json.dumps(findings, ensure_ascii=False, indent=2) + "\n",
    )
    md_path = out_dir / f"{today}.md"
    lines = [
        f"# OPC Doc Lint — {today}",
        "",
        f"Drift total: **{findings['drift_total']}**",
        "",
    ]
    lines.append("## Key docs presence")
    lines.append(f"- expected: {findings['key_docs']['expected']}")
    lines.append(f"- present: {len(findings['key_docs']['present'])}")
    if findings["key_docs"]["missing"]:
        lines.append(f"- missing: {findings['key_docs']['missing']}")
    lines.append("")
    lines.append("## Phase doc consistency")
    for item in findings["phase_doc_consistency"]:
        marker = "DRIFT" if item.get("drift") else "ok"
        lines.append(f"- {item.get('phase', '?')}: {marker}")
    lines.append("")
    lines.append("## Dead links")
    if findings["dead_links"]:
        for dead in findings["dead_links"]:
            lines.append(f"- {dead['doc']} → {dead['link_target']}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Term consistency")
    if findings["term_consistency_issues"]:
        for issue in findings["term_consistency_issues"]:
            lines.append(f"- {issue['phase']}: {issue['issue']}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## History")
    lines.append(f"- run_count: {findings['history']['summary']['run_count']}")
    lines.append(
        f"- latest_drift_total: {findings['history']['summary']['latest_drift_total']}"
    )
    write_text_atomic(md_path, "\n".join(lines) + "\n")
    return json_path, md_path


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def resolve_doc_path(workspace_root: Path, rel: str) -> Path:
    direct = workspace_root / rel
    if direct.exists():
        return direct
    if rel.startswith("docs/"):
        alt = workspace_root / "docs" / "opc" / Path(rel).name
        if alt.exists():
            return alt
    return direct


def read_text(workspace_root: Path, rel: str) -> str:
    return resolve_doc_path(workspace_root, rel).read_text(encoding="utf-8")


def read_yaml(workspace_root: Path, rel: str) -> dict[str, Any]:
    return load_yaml_docs(read_text(workspace_root, rel))


def check_key_docs_exist(workspace_root: Path, key_docs: list[str]) -> dict[str, Any]:
    missing: list[str] = []
    present: list[str] = []
    for rel in key_docs:
        if resolve_doc_path(workspace_root, rel).exists():
            present.append(rel)
        else:
            missing.append(rel)
    return {
        "kind": "key_docs_present",
        "expected": len(key_docs),
        "present": present,
        "missing": missing,
        "drift": len(missing) > 0,
    }


def check_phase_doc_consistency(
    workspace_root: Path,
    phase_plan_docs: list[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for phase, task_id, doc_rel in phase_plan_docs:
        try:
            plan_rel = str(
                resolve_opc_phase_task_path(workspace_root, task_id).relative_to(
                    workspace_root
                )
            )
            plan = read_yaml(workspace_root, plan_rel)
            doc = read_text(workspace_root, doc_rel)
        except FileNotFoundError:
            findings.append({"phase": phase, "status": "missing-file", "drift": True})
            continue
        plan_status = plan.get("gate_status", "unknown")
        if plan_status == "passed":
            if (
                "passed" not in doc.lower()
                and f"Gate {plan['gate'][-1]} passed" not in doc
            ):
                findings.append(
                    {
                        "phase": phase,
                        "plan_status": plan_status,
                        "doc": doc_rel,
                        "issue": "plan says passed but doc lacks 'passed'",
                        "drift": True,
                    }
                )
            else:
                findings.append(
                    {
                        "phase": phase,
                        "plan_status": plan_status,
                        "doc": doc_rel,
                        "drift": False,
                    }
                )
        else:
            findings.append(
                {
                    "phase": phase,
                    "plan_status": plan_status,
                    "doc": doc_rel,
                    "drift": False,
                }
            )
    return findings


def check_dead_links(workspace_root: Path, key_docs: list[str]) -> list[dict[str, Any]]:
    link_re = re.compile(r"\[([^\]]+)\]\((?!https?://|#)([^)]+)\)")
    dead: list[dict[str, Any]] = []
    for rel in key_docs:
        try:
            text = read_text(workspace_root, rel)
        except FileNotFoundError:
            continue
        for match in link_re.finditer(text):
            link_text, link_target = match.group(1), match.group(2)
            if link_target.startswith(("/", "http")):
                continue
            target = (workspace_root / rel).parent / link_target
            if not target.exists():
                dead.append(
                    {"doc": rel, "link_text": link_text, "link_target": link_target}
                )
    return dead


def check_term_consistency(
    workspace_root: Path,
    phase_plan_docs: list[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for phase, task_id, doc_rel in phase_plan_docs:
        try:
            plan_rel = str(
                resolve_opc_phase_task_path(workspace_root, task_id).relative_to(
                    workspace_root
                )
            )
            plan = read_yaml(workspace_root, plan_rel)
            doc = read_text(workspace_root, doc_rel)
        except FileNotFoundError:
            continue
        plan_status = plan.get("gate_status", "unknown")
        gate = plan.get("gate", "")
        if plan_status != "passed":
            continue
        head_text = "\n".join(doc.splitlines()[:30]).lower()
        has_current_pass_signal = "closed" in head_text or "passed" in head_text
        if (
            "not_yet_passed" in head_text
            and gate.lower() in head_text
            and not has_current_pass_signal
        ):
            issues.append(
                {
                    "phase": phase,
                    "doc": doc_rel,
                    "issue": f"doc head still has 'not_yet_passed' for {gate}",
                }
            )
    return issues


def run_doc_lint(
    workspace_root: Path,
    *,
    key_docs: list[str],
    phase_plan_docs: list[tuple[str, str, str]],
    generated_at: str | None = None,
    today: str | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    findings: dict[str, Any] = {
        "generated_at": generated_at or utc_now_iso(),
        "key_docs": check_key_docs_exist(workspace_root, key_docs),
        "phase_doc_consistency": check_phase_doc_consistency(
            workspace_root, phase_plan_docs
        ),
        "dead_links": check_dead_links(workspace_root, key_docs),
        "term_consistency_issues": check_term_consistency(
            workspace_root, phase_plan_docs
        ),
    }
    total_drift = (
        (1 if findings["key_docs"]["drift"] else 0)
        + sum(1 for item in findings["phase_doc_consistency"] if item.get("drift"))
        + (1 if findings["dead_links"] else 0)
        + (1 if findings["term_consistency_issues"] else 0)
    )
    findings["drift_total"] = total_drift
    findings["history"] = update_doc_lint_index(workspace_root, findings)
    json_path, md_path = write_doc_lint_outputs(
        workspace_root, findings, today or utc_today()
    )
    return findings, json_path, md_path
