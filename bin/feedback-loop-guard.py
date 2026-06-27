#!/usr/bin/env python3
"""feedback-loop-guard — 自反馈回路存活监控 + escalation.

任务: TASK-26348641 (P0 自反馈闭环: governance停摆/mypy假绿无报警).

监控 3 个反馈回路维度:
  1. governance-history.jsonl 写入新鲜度 (回看时间戳 ≤ 24h)
  2. ingress-audit.jsonl 写入新鲜度 (回看时间戳 ≤ 24h)
  3. 工作树未提交文件数 (L0:CR-GOV-COMMIT-FREQUENCY-01 — >100 warn, >500 error)

任何维度越界 → 通过 omo event emit 触发 escalation signal,
供 cockpit / kairon-agent 消费. cron 友好 (退出码 0/1/2).

用法:
  feedback-loop-guard.py              # 检查 + 越界时 emit (default 模式)
  feedback-loop-guard.py --check      # 只检查, 不 emit, 退出码反映状态
  feedback-loop-guard.py --json       # 输出 JSON 报告 (证据集成)
  feedback-loop-guard.py --dry-run    # 只打印, 不 emit

退出码:
  0 — 全部维度健康
  1 — 越界 (警告或错误)
  2 — 运行错误 (无法读取日志等)

来源: CR-GOV-COMMIT-FREQUENCY-01 (L0:X1), CR-AUDIT-5REPOS-01 治理存活 (GOV-X4)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
OMO_DIR = WORKSPACE_ROOT / ".omo"
GOV_LOG = OMO_DIR / "_knowledge" / "governance-history.jsonl"
INGRESS_LOG = OMO_DIR / "_delivery" / "ingress" / "ingress-audit.jsonl"
OMO_VENV = WORKSPACE_ROOT / "projects" / "omo" / ".venv" / "bin" / "python"

# 阈值 (单位: 小时 / 文件数)
GOV_STALENESS_HOURS = 24.0
INGRESS_STALENESS_HOURS = 24.0
TREE_WARN_FILES = 100
TREE_ERROR_FILES = 500


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _file_age_hours(path: Path) -> float | None:
    """文件最后修改距今的小时数, 不可读返回 None."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return (_utc_now().timestamp() - mtime) / 3600.0


def _log_last_entry_ts(path: Path) -> str | None:
    """从 JSONL 文件最后一行提取 timestamp 字段 (健壮解析)."""
    if not path.exists():
        return None
    try:
        # 取最后 64KB 足以覆盖大多数治理记录的尾段
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 65536))
            data = f.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    # 从尾向头扫描找到第一个可解析的 JSON 行
    lines = [ln for ln in data.splitlines() if ln.strip()][-200:]
    for line in reversed(lines):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = rec.get("timestamp") or rec.get("ts") or rec.get("date")
        if isinstance(ts, str):
            return ts
    return None


def _age_hours_from_ts(ts: str) -> float | None:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (_utc_now() - dt).total_seconds() / 3600.0


def _working_tree_uncommitted() -> int | None:
    """git status --short 数量 (根仓 + 子模块)."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=WORKSPACE_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return sum(1 for line in result.stdout.splitlines() if line.strip())


def _emit_event(kind: str, payload: dict) -> bool:
    """通过 omo event emit 触发 escalation. 返回是否成功."""
    if not (OMO_VENV.exists() or shutil.which("omo")):
        return False
    py = OMO_VENV if OMO_VENV.exists() else None
    cmd = []
    if py:
        cmd = [str(py), "-m", "omo.omo_event", "emit", "--type", kind, "--source",
               "feedback-loop-guard", "--payload", json.dumps(payload, ensure_ascii=False)]
    else:
        cmd = ["omo", "event", "emit", "--type", kind, "--source",
               "feedback-loop-guard", "--payload", json.dumps(payload, ensure_ascii=False)]
    try:
        result = subprocess.run(cmd, cwd=WORKSPACE_ROOT, capture_output=True, text=True,
                                timeout=20, check=False)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return result.returncode == 0


def check_all() -> dict:
    """运行所有检查, 返回结构化报告."""
    now = _utc_now().isoformat().replace("+00:00", "Z")
    dimensions: dict = {}

    # 1. governance-history.jsonl — file mtime 兜底 + last entry ts 精确
    gov_mtime_age = _file_age_hours(GOV_LOG)
    gov_last_ts = _log_last_entry_ts(GOV_LOG)
    gov_entry_age = _age_hours_from_ts(gov_last_ts) if gov_last_ts else None
    gov_breached = (gov_entry_age is not None
                    and gov_entry_age > GOV_STALENESS_HOURS)
    dimensions["governance_history"] = {
        "path": str(GOV_LOG.relative_to(WORKSPACE_ROOT)),
        "exists": GOV_LOG.exists(),
        "last_entry_ts": gov_last_ts,
        "last_entry_age_hours": round(gov_entry_age, 2) if gov_entry_age is not None else None,
        "file_mtime_age_hours": round(gov_mtime_age, 2) if gov_mtime_age is not None else None,
        "threshold_hours": GOV_STALENESS_HOURS,
        "breached": gov_breached,
    }

    # 2. ingress-audit.jsonl
    ingress_mtime_age = _file_age_hours(INGRESS_LOG)
    ingress_last_ts = _log_last_entry_ts(INGRESS_LOG)
    ingress_entry_age = _age_hours_from_ts(ingress_last_ts) if ingress_last_ts else None
    ingress_breached = (ingress_entry_age is not None
                        and ingress_entry_age > INGRESS_STALENESS_HOURS)
    dimensions["ingress_audit"] = {
        "path": str(INGRESS_LOG.relative_to(WORKSPACE_ROOT)),
        "exists": INGRESS_LOG.exists(),
        "last_entry_ts": ingress_last_ts,
        "last_entry_age_hours": round(ingress_entry_age, 2) if ingress_entry_age is not None else None,
        "file_mtime_age_hours": round(ingress_mtime_age, 2) if ingress_mtime_age is not None else None,
        "threshold_hours": INGRESS_STALENESS_HOURS,
        "breached": ingress_breached,
    }

    # 3. working tree 未提交 (L0:CR-GOV-COMMIT-FREQUENCY-01)
    tree_count = _working_tree_uncommitted()
    tree_severity = "ok"
    tree_breached = False
    if tree_count is None:
        tree_severity = "unknown"
    elif tree_count > TREE_ERROR_FILES:
        tree_severity = "error"
        tree_breached = True
    elif tree_count > TREE_WARN_FILES:
        tree_severity = "warn"
        tree_breached = True
    dimensions["working_tree"] = {
        "uncommitted_count": tree_count,
        "warn_threshold": TREE_WARN_FILES,
        "error_threshold": TREE_ERROR_FILES,
        "severity": tree_severity,
        "breached": tree_breached,
        "rule_id": "CR-GOV-COMMIT-FREQUENCY-01",
    }

    breached = [k for k, v in dimensions.items() if v.get("breached")]
    return {
        "checked_at": now,
        "workspace_root": str(WORKSPACE_ROOT),
        "any_breach": bool(breached),
        "breached_dimensions": breached,
        "dimensions": dimensions,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="自反馈回路存活监控")
    parser.add_argument("--check", action="store_true",
                        help="只检查, 不 emit escalation (cron 友好退出码)")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    parser.add_argument("--dry-run", action="store_true", help="dry-run, 不 emit")
    args = parser.parse_args(argv)

    try:
        report = check_all()
    except Exception as exc:
        print(f"FATAL: check_all raised: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"feedback-loop-guard @ {report['checked_at']}")
        for name, dim in report["dimensions"].items():
            tag = "BREACH" if dim.get("breached") else "ok"
            print(f"  [{tag:6s}] {name}: {dim}")

    if not report["any_breach"]:
        return 0

    # 越界 → emit escalation (除非 --check / --dry-run)
    if args.check or args.dry_run:
        return 1

    payload = {
        "any_breach": True,
        "breached_dimensions": report["breached_dimensions"],
        "dimensions": report["dimensions"],
    }
    severity = "ok"
    tree = report["dimensions"]["working_tree"]
    if tree.get("severity") == "error":
        severity = "error"
    elif tree.get("severity") == "warn":
        severity = "warn"
    if any(report["dimensions"][k]["breached"] for k in ("governance_history", "ingress_audit")):
        severity = "error" if severity != "error" else severity

    event_kind = f"feedback_loop_{severity}" if severity != "ok" else "feedback_loop_warn"
    emitted = _emit_event(event_kind, payload)
    if not emitted and not args.json:
        print("WARN: omo event emit failed (degraded mode — see JSON report)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())