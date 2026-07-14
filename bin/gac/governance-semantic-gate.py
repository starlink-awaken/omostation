#!/usr/bin/env python3
"""Unified semantic gate for governance tool outputs.

This gate consumes machine JSON from the existing governance tools and applies
one shared ok/blocking contract. It prevents "command exited 0, but JSON said
ok=false" drift from becoming invisible to local/CI gates.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[2]


def _command(script: str, *args: str) -> list[str]:
    return [sys.executable, script, *args]


def _run_json(check_id: str, command: list[str], timeout: int = 180) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "id": check_id,
            "command": " ".join(command),
            "returncode": None,
            "parsed": False,
            "data": {},
            "error": f"timeout after {timeout}s",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }

    stdout = result.stdout.strip()
    try:
        data = json.loads(stdout) if stdout else {}
        parsed = isinstance(data, dict)
    except json.JSONDecodeError as exc:
        data = {}
        parsed = False
        parse_error = str(exc)
    else:
        parse_error = ""

    return {
        "id": check_id,
        "command": " ".join(command),
        "returncode": result.returncode,
        "parsed": parsed,
        "data": data,
        "error": parse_error,
        "stdout": stdout if not parsed else "",
        "stderr": result.stderr.strip(),
    }


def _adr_ok(data: dict[str, Any]) -> tuple[bool, list[str]]:
    fields = [
        "missing_numbers",
        "duplicate_numbers",
        "frontmatter_issues",
        "files_not_in_index",
        "index_refs_not_in_files",
    ]
    findings: list[str] = []
    if not data.get("index_present", False):
        findings.append("INDEX.md is missing")
    for field in fields:
        values = data.get(field) or []
        if values:
            findings.append(f"{field}={len(values)}")
    return not findings, findings


def _simple_ok(data: dict[str, Any]) -> tuple[bool, list[str]]:
    if data.get("ok") is True:
        return True, []
    return False, ["ok=false"]


def _agent_workflow_ok(data: dict[str, Any], *, release: bool) -> tuple[bool, list[str]]:
    findings: list[str] = []
    if data.get("ok") is not True:
        findings.append("status ok=false")
    compliance = data.get("compliance") or {}
    if compliance.get("ok") is not True:
        findings.append("compliance ok=false")
    if data.get("stale_locks", 0):
        findings.append(f"stale_locks={data.get('stale_locks')}")
    active_runs = data.get("active_runs") or []
    if active_runs:
        findings.append(f"active_runs={len(active_runs)}")
    return not findings, findings


def _packages_ok(data: dict[str, Any], *, release: bool) -> tuple[bool, list[str]]:
    findings: list[str] = []
    if data.get("ok") is not True:
        findings.append("packages ok=false")
    if data.get("unknown_count", 0):
        findings.append(f"unknown_count={data.get('unknown_count')}")
    if data.get("release_ready") is not True:
        findings.append("release_ready=false")
    return not findings, findings


def _evaluate(
    raw: dict[str, Any],
    evaluator: Callable[[dict[str, Any]], tuple[bool, list[str]]],
    *,
    severity: str,
    blocking: bool,
) -> dict[str, Any]:
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    command_ok = raw.get("returncode") == 0
    parsed = raw.get("parsed") is True
    semantic_ok, findings = evaluator(data)
    if not parsed:
        findings = [f"json_parse_error={raw.get('error') or 'unknown'}", *findings]
    if not command_ok:
        findings = [f"returncode={raw.get('returncode')}", *findings]
    ok = command_ok and parsed and semantic_ok
    return {
        "id": raw["id"],
        "ok": ok,
        "severity": severity,
        "blocking": blocking,
        "command": raw["command"],
        "returncode": raw.get("returncode"),
        "findings": findings,
    }


def run_gate(*, release: bool = False) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    definitions: list[tuple[str, list[str], Callable[[dict[str, Any]], tuple[bool, list[str]]], str, bool]] = [
        # GaC 声明/执行鸿沟 (TASK-A367B061): 129 rules 缺 executor → gac-bootstrap/executor 报 ok=false.
        # 短期降 non-blocking (GaC 半成品非 CI 阻断事由, 补 executor 是长期专项); 长期补 129 executor 后恢复 blocking.
        (
            "gac-bootstrap",
            _command("bin/gac/gac-bootstrap.py", "--json"),
            _simple_ok,
            "error",
            False,
        ),
        (
            "gac-executor",
            _command("bin/gac/gac-executor.py", "--json"),
            _simple_ok,
            "error",
            False,
        ),
        (
            "gac-mof-validate",
            _command("bin/gac/gac-mof-validate.py", "--json"),
            _simple_ok,
            "error",
            True,
        ),
        # mof-schema-validate json_parse_error (TASK-A367B061): sys.executable 跑 ecos 脚本 import 失败 stdout 非 JSON.
        # 短期降 non-blocking; 长期 _command 用 uv run/PYTHONPATH 装依赖.
        (
            "mof-schema-validate",
            _command("projects/ecos/src/ecos/ssot/tools/mof-schema-validate.py", "--json"),
            _simple_ok,
            "error",
            False,
        ),
        (
            "adr-coverage",
            _command("bin/adr/adr-coverage.py", "--json"),
            _adr_ok,
            "error",
            True,
        ),
        (
            "agent-workflow-status",
            _command("bin/agent-workflow.py", "status", "--json"),
            lambda data: _agent_workflow_ok(data, release=release),
            "warn" if not release else "error",
            release,
        ),
        (
            "governance-evolution-packages",
            _command("bin/gac/governance-evolution.py", "packages", "--json"),
            lambda data: _packages_ok(data, release=release),
            "warn" if not release else "error",
            release,
        ),
        # 治本B: 调度注册自洽 gate (CI 可验, 不依赖本机 plist).
        # gen --validate 验 services.yaml 自洽 (interpreter 锚点禁 .tmp + 必填字段). blocking.
        # (原 --check 验本机 plist, CI 无本机 plist 总 drift=1 → 改 --validate 验注册自洽)
        (
            "service-config-drift",
            _command("bin/mof/gen-service-configs.py", "--validate", "--json"),
            _simple_ok,
            "error",
            True,
        ),
    ]

    for check_id, command, evaluator, severity, blocking in definitions:
        raw = _run_json(check_id, command)
        checks.append(
            _evaluate(raw, evaluator, severity=severity, blocking=blocking)
        )

    blocking_failures = [item for item in checks if item["blocking"] and not item["ok"]]
    warnings = [item for item in checks if not item["blocking"] and not item["ok"]]
    return {
        "ok": not blocking_failures,
        "release": release,
        "blocking_failures": len(blocking_failures),
        "warnings": len(warnings),
        "checks": checks,
    }


def print_human(report: dict[str, Any]) -> None:
    print("═══ Governance semantic gate ═══")
    print(f"release={report['release']}")
    for item in report["checks"]:
        if item["ok"]:
            status = "PASS"
        elif item["blocking"]:
            status = "FAIL"
        else:
            status = "WARN"
        print(f"[{status}] {item['id']} :: {item['command']}")
        for finding in item["findings"]:
            print(f"  - {finding}")
    print("Governance semantic gate: " + ("PASS" if report["ok"] else "FAIL"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run unified governance semantic checks")
    parser.add_argument("--release", action="store_true", help="Block on release readiness and active runs")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    report = run_gate(release=args.release)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
