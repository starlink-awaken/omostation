#!/usr/bin/env python3
"""OMO governance audit — debt action audit trail + workspace compliance checks.

This module serves two roles:

  1. **Debt action audit trail** (X1-AUDIT-001) — `record() / query() / summary()`
     append structured records to a JSONL audit file. Linked to debt items via
     `debt_id` field.

  2. **Workspace compliance checks** (P30-W1 GOV-MERGE, migrated from
     kairon_governance.audit) — `run_governance_audit()` and helpers run 6
     checks (lint, tests, debt, ADR, tasks, agora-health) and produce a
     Markdown + dataclass report.

The two roles share this module because both produce audit-style output
(JSONL / Markdown) and both underpin governance visibility. The debt
audit trail functions remain at the top of the file for backward
compatibility; the compliance checks follow under a clear section header.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Literal

from omo.omo_paths import (
    DECISIONS_DIR,
    DEBT_ITEMS_DIR,
    KAIRON_PACKAGES,
    TASKS_PLANNED_DIR,
    WORKSPACE_ROOT,
)
# 复用 omo_io.AppendOnlyLog (P49+ AppendOnlyLog 抽象: JSONL 物理读写唯一入口)
from omo.omo_io import AppendOnlyLog

# =============================================================================
# Section 1 — Debt action audit trail (X1-AUDIT-001, pre-existing)
# =============================================================================


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _default_audit_file() -> Path:
    return Path.home() / "runtime" / "audit" / "governance-audit.jsonl"


# 注: per-call log 创建 (与 omo_bos_metrics 一致), 便于 monkeypatch DEFAULT_METRICS_PATH.
# AppendOnlyLog 构造轻量 (Path + Lock), per-call 创建开销可忽略.


def record(
    action: str,
    debt_id: str = "",
    actor: str = "",
    details: str = "",
    audit_file: str | Path | None = None,
) -> dict:
    """Record a governance action to the audit trail.

    Returns the record dict for reference.
    """
    entry = {
        "ts": _utc_now(),
        "action": action,
        "debt_id": debt_id,
        "actor": actor,
        "details": details,
    }
    log = AppendOnlyLog(Path(audit_file) if audit_file else _default_audit_file())
    log.append(entry)
    return entry


def query(limit: int = 50, audit_file: str | Path | None = None) -> list[dict]:
    """Read the most recent audit records."""
    log = AppendOnlyLog(Path(audit_file) if audit_file else _default_audit_file())
    return log.read_all()[-limit:]


def summary(audit_file: str | Path | None = None) -> dict:
    """Return audit summary."""
    log = AppendOnlyLog(Path(audit_file) if audit_file else _default_audit_file())
    records = log.read_all()
    if not records:
        return {"total": 0, "actions": {}, "with_debt": 0}
    actions: dict[str, int] = {}
    debt_ids: set[str] = set()
    for r in records:
        a = r.get("action", "unknown")
        actions[a] = actions.get(a, 0) + 1
        if r.get("debt_id"):
            debt_ids.add(r["debt_id"])
    return {
        "total": len(records),
        "actions": actions,
        "unique_debt_ids": len(debt_ids),
        "latest": records[-1] if records else None,
    }


# =============================================================================
# Section 2 — Workspace governance compliance checks (P30-W1 GOV-MERGE)
# =============================================================================

# 模块级路径(允许测试覆盖)
_KAIRON_DIR: Path = Path(__file__).resolve().parents[4] / "projects" / "kairon"
_OMO_ROOT: Path = WORKSPACE_ROOT / ".omo"
_WORKSPACE_ROOT: Path = WORKSPACE_ROOT

# 环境变量开关: daemon 跑 audit 时跳过 agora 探活(避免每 tick 11 HTTP 请求)
ENV_SKIP_AGORA = "OMO_AUDIT_SKIP_AGORA"

Severity = Literal["ok", "warn", "fail"]


@dataclass
class CheckResult:
    """单次检查结果."""

    name: str
    category: str
    severity: Severity
    score: float  # 0-100
    message: str
    details: list[str] = field(default_factory=list)


@dataclass
class GovernanceReport:
    """巡检报告聚合."""

    date: str
    total_score: float
    grade: str
    checks: list[CheckResult]
    watchlist: list[str]
    recommendations: list[str]

    def to_markdown(self) -> str:
        """渲染为 Markdown 报告."""
        sev_emoji = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}
        lines: list[str] = [
            f"# omo 治理巡检报告 — {self.date}",
            "",
            f"**总分: {self.total_score} ({self.grade})**",
            "",
            "> 巡检器只读:本报告未修改 .omo/state/、.omo/goals/、.omo/INDEX.md。",
            "> 任务: P30-W1 GOV-MERGE (omo 治理巡检, 迁移自 kairon-governance.audit)",
            "",
            "## 1. 检查结果",
            "",
            "| 检查 | 类别 | 严重度 | 分数 | 说明 |",
            "|---|---|---|---|---|",
        ]
        for c in self.checks:
            sev = sev_emoji.get(c.severity, c.severity)
            lines.append(f"| {c.name} | {c.category} | {sev} | {c.score:.0f} | {c.message} |")

        lines += ["", "## 2. 检查细节", ""]
        for c in self.checks:
            if c.details:
                lines.append(f"### {c.name}")
                lines.append("")
                for d in c.details:
                    lines.append(f"- {d}")
                lines.append("")

        if self.watchlist:
            lines += ["## 3. 新发现潜在债务(debt watchlist)", ""]
            for w in self.watchlist:
                lines.append(f"- {w}")
            lines.append("")
        else:
            lines += ["## 3. 新发现潜在债务(debt watchlist)", "", "_(无)_", ""]

        if self.recommendations:
            lines += ["## 4. 修复建议", ""]
            for r in self.recommendations:
                lines.append(f"- {r}")
            lines.append("")
        else:
            lines += ["## 4. 修复建议", "", "_(无)_", ""]

        lines += [
            "## 5. 评分方法",
            "",
            "- 总分 = 6 项检查分数的算术平均(等权)",
            "- 等级阈值: 98+=A+ | 90-97=A | 80-89=B | 70-79=C | 60-69=D | <60=F",
            "- 扣分规则:",
            "  - **lint**: 每个 ruff error 扣 5 分",
            "  - **tests**: 每个无测试的包扣 10 分",
            "  - **debt**: 每条 resolved 缺证据扣 5 分",
            "  - **knowledge**: 每条断链扣 20 分",
            "  - **tasks**: 每条不一致扣 10 分",
            "  - **agora**: 健康度 < 80% 触发 warn, < 50% 触发 fail",
            "  - (设 `OMO_AUDIT_SKIP_AGORA=1` 可跳过 agora 探活, 默认 ok=100)",
            "",
        ]
        return "\n".join(lines)


# ── YAML 工具 ──────────────────────────────────────────────


def _load_yaml_safely(path: Path) -> dict | None:
    """安全加载 YAML,失败返回 None."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_load(text) or {}
    except ImportError:
        pass
    except Exception:
        return None
    return _mini_yaml_parse(text)


def _mini_yaml_parse(text: str) -> dict:
    """极简 YAML 解析器, 仅支持 'key: value' 形式的顶层字段."""
    out: dict = {}
    for line in text.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#") or line.startswith(" ") or line.startswith("\t"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        out[key] = value
    return out


# ── 6 项检查 ─────────────────────────────────────────────


def governance_check_lint() -> CheckResult:
    """跑 ruff check kairon packages/, 统计 error 数."""
    try:
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "packages/", "--statistics"],
            cwd=str(_KAIRON_DIR),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
        m = re.search(r"Found\s+(\d+)\s+errors?", output, re.IGNORECASE)
        errors = int(m.group(1)) if m else 0
        if errors == 0:
            return CheckResult(
                name="ruff lint",
                category="lint",
                severity="ok",
                score=100.0,
                message="0 errors",
            )
        sample: list[str] = []
        for line in output.splitlines():
            if re.match(r"^[^\s].+\.py:\d+:\d+:", line):
                sample.append(line.strip())
                if len(sample) >= 10:
                    break
        return CheckResult(
            name="ruff lint",
            category="lint",
            severity="warn",
            score=max(0.0, 100.0 - errors * 5),
            message=f"{errors} errors",
            details=sample,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name="ruff lint",
            category="lint",
            severity="fail",
            score=0.0,
            message="ruff check timeout (180s)",
        )
    except FileNotFoundError as exc:
        return CheckResult(
            name="ruff lint",
            category="lint",
            severity="fail",
            score=0.0,
            message=f"ruff 未找到: {exc}",
        )


def governance_check_test_coverage() -> CheckResult:
    """每个非归档包至少 1 个 test_*.py."""
    packages_dir = KAIRON_PACKAGES
    if not packages_dir.exists():
        return CheckResult(
            name="test coverage",
            category="tests",
            severity="fail",
            score=0.0,
            message="packages/ 目录不存在",
        )
    missing: list[str] = []
    for pkg_dir in sorted(packages_dir.iterdir()):
        if not pkg_dir.is_dir():
            continue
        if pkg_dir.name.startswith(".") or pkg_dir.name.startswith("_"):
            continue
        tests_dir = pkg_dir / "tests"
        if not tests_dir.exists():
            missing.append(f"{pkg_dir.name}: 无 tests/ 目录")
            continue
        if not any(tests_dir.rglob("test_*.py")):
            missing.append(f"{pkg_dir.name}: tests/ 下无 test_*.py")
    if not missing:
        return CheckResult(
            name="test coverage",
            category="tests",
            severity="ok",
            score=100.0,
            message="all packages have tests",
        )
    return CheckResult(
        name="test coverage",
        category="tests",
        severity="warn",
        score=max(0.0, 100.0 - len(missing) * 10),
        message=f"{len(missing)} packages without tests",
        details=missing,
    )


def governance_check_debt_integrity() -> CheckResult:
    """检查 .omo/debt/items/ 中 lifecycle_state=resolved 的项是否有 resolution_evidence."""
    debt_items_dir = DEBT_ITEMS_DIR
    if not debt_items_dir.exists():
        return CheckResult(
            name="debt integrity",
            category="debt",
            severity="ok",
            score=100.0,
            message="no debt items dir",
        )
    suspicious: list[str] = []
    for yaml_file in sorted(debt_items_dir.glob("*.yaml")):
        data = _load_yaml_safely(yaml_file)
        if not data:
            continue
        lifecycle = str(data.get("lifecycle_state", "")).strip()
        if lifecycle not in ("resolved", "closed"):
            continue
        evidence = str(data.get("resolution_evidence", "")).strip()
        if not evidence:
            history = data.get("history")
            if isinstance(history, list) and history:
                last = history[-1]
                if isinstance(last, dict):
                    note = str(last.get("note", "")).strip()
                    if note and len(note) >= 20:
                        evidence = note
        if not evidence or len(evidence) < 20:
            suspicious.append(
                f"{yaml_file.stem}: lifecycle={lifecycle} 但无 resolution_evidence"
            )
    if not suspicious:
        return CheckResult(
            name="debt integrity",
            category="debt",
            severity="ok",
            score=100.0,
            message="all resolved/closed debts have evidence",
        )
    return CheckResult(
        name="debt integrity",
        category="debt",
        severity="warn",
        score=max(0.0, 100.0 - len(suspicious) * 5),
        message=f"{len(suspicious)} resolved/closed debts lack evidence",
        details=suspicious,
    )


def governance_check_adr_links() -> CheckResult:
    """检查 ADR INDEX.md 引用的所有 ADR 都存在."""
    decisions_dir = DECISIONS_DIR
    if not decisions_dir.exists():
        return CheckResult(
            name="adr links",
            category="knowledge",
            severity="warn",
            score=50.0,
            message="decisions/ 目录不存在",
        )
    index_file = decisions_dir / "INDEX.md"
    if not index_file.exists():
        return CheckResult(
            name="adr links",
            category="knowledge",
            severity="warn",
            score=60.0,
            message="INDEX.md 不存在",
        )
    content = index_file.read_text(encoding="utf-8")
    referenced: set[str] = set()
    for m in re.finditer(r"\b(\d{4})-([a-z0-9-]+)\.md\b", content):
        referenced.add(f"{m.group(1)}-{m.group(2)}.md")
    existing: set[str] = {p.name for p in decisions_dir.glob("[0-9][0-9][0-9][0-9]-*.md")}
    broken = sorted(referenced - existing)
    orphan = sorted(existing - referenced)
    if not broken and not orphan:
        return CheckResult(
            name="adr links",
            category="knowledge",
            severity="ok",
            score=100.0,
            message=f"all {len(referenced)} ADR links valid",
        )
    details: list[str] = []
    for b in broken:
        details.append(f"REFERENCED-BUT-MISSING: {b}")
    for o in orphan:
        details.append(f"EXISTS-BUT-UNLISTED: {o}")
    severity: Severity = "fail" if broken else "warn"
    score = max(0.0, 100.0 - len(broken) * 20 - len(orphan) * 5)
    return CheckResult(
        name="adr links",
        category="knowledge",
        severity=severity,
        score=score,
        message=f"{len(broken)} broken, {len(orphan)} unlisted ADR links",
        details=details,
    )


def governance_check_task_consistency() -> CheckResult:
    """status=completed 的任务, deliverables 列出的路径必须存在."""
    planned_dir = TASKS_PLANNED_DIR
    if not planned_dir.exists():
        return CheckResult(
            name="task consistency",
            category="tasks",
            severity="ok",
            score=100.0,
            message="no planned tasks dir",
        )
    inconsistent: list[str] = []
    checked = 0
    for yaml_file in sorted(planned_dir.glob("*.yaml")):
        data = _load_yaml_safely(yaml_file)
        if not data:
            continue
        if str(data.get("status", "")).strip() != "completed":
            continue
        checked += 1
        deliverables = data.get("deliverables", [])
        if isinstance(deliverables, str):
            continue
        if not isinstance(deliverables, list):
            continue
        for d in deliverables:
            if not isinstance(d, str):
                continue
            p = _WORKSPACE_ROOT / d
            if p.exists():
                continue
            # Glob 展开 (P36 W0 规则宽容: 含 * 的路径按 glob 展开, 全部命中才算 OK)
            if any(ch in d for ch in ("*", "?", "[")):
                matches = list((_WORKSPACE_ROOT).glob(d))
                if matches:
                    continue
                inconsistent.append(
                    f"{yaml_file.stem} → {d} (glob 展开无匹配)"
                )
                continue
            inconsistent.append(f"{yaml_file.stem} → {d} (status=completed 但文件不存在)")
    if checked == 0:
        return CheckResult(
            name="task consistency",
            category="tasks",
            severity="ok",
            score=100.0,
            message="no completed tasks to verify",
        )
    if not inconsistent:
        return CheckResult(
            name="task consistency",
            category="tasks",
            severity="ok",
            score=100.0,
            message=f"all {checked} completed tasks have deliverables",
        )
    return CheckResult(
        name="task consistency",
        category="tasks",
        severity="warn",
        score=max(0.0, 100.0 - len(inconsistent) * 10),
        message=f"{len(inconsistent)} missing deliverables",
        details=inconsistent,
    )


def governance_check_agora_health() -> CheckResult:
    """第 6 项: agora 路由 -> 服务真实可达率(>=80% = 满分).

    单次 audit 默认会跑(HTTP 探活),
    daemon 跑时设 OMO_AUDIT_SKIP_AGORA=1 跳过.
    """
    if os.environ.get(ENV_SKIP_AGORA) == "1":
        return CheckResult(
            name="agora health",
            category="agora",
            severity="ok",
            score=100.0,
            message="skipped (OMO_AUDIT_SKIP_AGORA=1)",
        )

    try:
        from omo.omo_health import (
            check_all_health,
            derive_endpoints,
            load_agora_routes,
        )
    except ImportError as exc:
        return CheckResult(
            name="agora health",
            category="agora",
            severity="fail",
            score=0.0,
            message=f"omo_health import failed: {exc}"[:120],
        )

    try:
        routes = load_agora_routes()
        endpoints = derive_endpoints(routes)
        if not endpoints:
            return CheckResult(
                name="agora health",
                category="agora",
                severity="warn",
                score=50.0,
                message="no endpoints discoverable",
            )
        results = asyncio.run(check_all_health(endpoints))
        if not results:
            return CheckResult(
                name="agora health",
                category="agora",
                severity="warn",
                score=50.0,
                message="0 endpoints probed",
            )
        healthy_n = sum(1 for r in results if r.is_healthy)
        rate = healthy_n / len(results)
        score = round(rate * 100, 0)
        if score >= 80:
            severity: Severity = "ok"
        elif score >= 50:
            severity = "warn"
        else:
            severity = "fail"
        unhealthy = [r.service for r in results if not r.is_healthy][:5]
        return CheckResult(
            name="agora health",
            category="agora",
            severity=severity,
            score=score,
            message=f"{healthy_n}/{len(results)} services healthy",
            details=unhealthy,
        )
    except Exception as exc:
        return CheckResult(
            name="agora health",
            category="agora",
            severity="fail",
            score=0.0,
            message=f"probe failed: {str(exc)[:100]}",
        )


def compute_grade(score: float) -> str:
    """等权平均分 → 等级."""
    if score >= 98:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def build_watchlist(checks: list[CheckResult]) -> list[str]:
    """从 warn/fail 检查里提炼新债务候选(每个检查最多 5 条)."""
    watchlist: list[str] = []
    for c in checks:
        if c.severity == "ok":
            continue
        for d in c.details[:5]:
            watchlist.append(f"[{c.category}] {d}")
    return watchlist


def build_recommendations(checks: list[CheckResult]) -> list[str]:
    """基于检查类别给出修复建议."""
    recs: list[str] = []
    for c in checks:
        if c.severity == "ok":
            continue
        if c.category == "lint":
            recs.append("修复 ruff 错误, 参考 `cd projects/kairon && uv run ruff check packages/ --fix`")
        elif c.category == "tests":
            sample = ", ".join(d.split(":")[0] for d in c.details[:3])
            recs.append(f"为 {sample} 等包至少添加 1 个 smoke test")
        elif c.category == "debt":
            recs.append("给 resolved/closed 债务补上 `resolution_evidence` 字段(>= 20 字符)")
        elif c.category == "knowledge":
            recs.append("清理 ADR INDEX.md 中的死链 / 补齐未列出的 ADR / 创建缺失的 ADR")
        elif c.category == "tasks":
            recs.append("补齐任务 YAML 中声明的 deliverables, 或将 status 回退到 in_progress")
        elif c.category == "agora":
            unhealthy = ", ".join(d for d in c.details[:5])
            recs.append(
                f"修复 agora 服务可达性 ({unhealthy}); "
                "检查 service 端口与 health_endpoint 字段"
            )
    return recs


def run_governance_audit(workspace: Path | None = None) -> GovernanceReport:
    """跑 6 项检查并聚合报告.

    workspace 参数允许测试时传入 tmp_path, 默认读 WORKSPACE_ROOT.
    """
    global _OMO_ROOT, _KAIRON_DIR, _WORKSPACE_ROOT
    if workspace is not None:
        _OMO_ROOT = workspace / ".omo"
        _KAIRON_DIR = workspace / "projects" / "kairon"
        _WORKSPACE_ROOT = workspace

    checks = [
        governance_check_lint(),
        governance_check_test_coverage(),
        governance_check_debt_integrity(),
        governance_check_adr_links(),
        governance_check_task_consistency(),
        governance_check_agora_health(),
    ]
    total = sum(c.score for c in checks) / len(checks)
    return GovernanceReport(
        date=datetime.now(UTC).strftime("%Y-%m-%d"),
        total_score=round(total, 1),
        grade=compute_grade(total),
        checks=checks,
        watchlist=build_watchlist(checks),
        recommendations=build_recommendations(checks),
    )


def render_markdown(report: GovernanceReport) -> str:
    """便捷封装: report.to_markdown()."""
    return report.to_markdown()


# =============================================================================
# Section 3 — CLI (governance subcommand)
# =============================================================================


def governance_main(argv: list[str] | None = None) -> int:
    """CLI: omo governance audit [--output PATH] [--json] [--no-history]."""
    parser = argparse.ArgumentParser(prog="omo governance audit")
    parser.add_argument("--output", "-o", default=None, help="Markdown 报告输出路径(默认 stdout)")
    parser.add_argument("--json", action="store_true", help="同时输出 JSON 数据")
    parser.add_argument(
        "--no-history", action="store_true",
        help="不写入治理历史 JSONL(默认会写)",
    )
    args = parser.parse_args(argv)

    report = run_governance_audit()
    md = report.to_markdown()
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"[AUDIT] Markdown 报告: {out_path}")
    else:
        print(md)

    if args.json:
        json_target = Path(args.output) if args.output else Path("/tmp/governance_audit.json")
        json_path = json_target.with_suffix(".json")
        json_path.write_text(
            json.dumps(asdict(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[AUDIT] JSON 数据: {json_path}")

    print(f"\n[AUDIT] 总分: {report.total_score} ({report.grade})")
    if report.watchlist:
        print(f"[AUDIT] 新发现潜在债务: {len(report.watchlist)} 条")

    if not args.no_history:
        try:
            from omo.omo_history import append_entry

            target = append_entry({
                "total_score": report.total_score,
                "grade": report.grade,
                "checks": [
                    {"name": c.name, "category": c.category, "score": c.score, "severity": c.severity}
                    for c in report.checks
                ],
                "watchlist_count": len(report.watchlist),
            })
            print(f"[AUDIT] 治理历史已 append: {target}")
        except Exception as exc:
            print(f"[AUDIT] 治理历史写入失败(不影响主流程): {exc}", file=sys.stderr)
    return 0


def governance_history_main(argv: list[str] | None = None) -> int:
    """CLI: omo governance history [--limit N] [--trend] [--path P]."""
    parser = argparse.ArgumentParser(prog="omo governance history")
    parser.add_argument("--limit", type=int, default=30, help="显示条数")
    parser.add_argument("--trend", action="store_true", help="显示趋势图")
    parser.add_argument("--path", default=None, help="历史 JSONL 路径(默认内置)")
    args = parser.parse_args(argv)

    from omo.omo_history import read_history, render_trend_chart

    path = Path(args.path) if args.path else None
    if args.trend:
        print(render_trend_chart(path=path))
        return 0
    entries = read_history(path=path, limit=args.limit)
    if not entries:
        print("(无历史记录)")
        return 0
    for e in entries:
        score = e.get("total_score", 0.0)
        grade = e.get("grade", "?")
        watchlist = e.get("watchlist_count", 0)
        date = e.get("date", "?")
        print(f"{date}  {score:5.1f}  ({grade})  watchlist={watchlist}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """主 CLI 入口: `omo audit` 子命令路由."""
    parser = argparse.ArgumentParser(prog="omo audit", description="OMO governance audit")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("governance", help="Run 6-check workspace compliance audit")
    sub.add_parser("history", help="View governance history")
    args = parser.parse_args(argv)
    if args.cmd == "governance":
        return governance_main()
    if args.cmd == "history":
        return governance_history_main()
    parser.print_help()
    return 0


__all__ = (
    # Section 1 — debt action audit trail
    "record",
    "query",
    "summary",
    # Section 2 — governance compliance checks
    "CheckResult",
    "GovernanceReport",
    "Severity",
    "build_recommendations",
    "build_watchlist",
    "compute_grade",
    "governance_check_adr_links",
    "governance_check_agora_health",
    "governance_check_debt_integrity",
    "governance_check_lint",
    "governance_check_task_consistency",
    "governance_check_test_coverage",
    "render_markdown",
    "run_governance_audit",
    # Section 3 — CLI
    "governance_main",
    "governance_history_main",
    "main",
)


if __name__ == "__main__":
    raise SystemExit(main())
