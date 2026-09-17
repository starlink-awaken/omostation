#!/usr/bin/env python3
"""公文审查能力腿 — journey-document-review 的 action 实现（纯函数，零副作用）.

背景（2026-09-17）: `journey-document-review` 声明了 5 个能力腿
（load_document / check_format / check_sensitivity / verify_basis / record_decision），
但 `journey-engine._execute_action` 未实现它们 —— 全部落到默认分支返回
`{"status": "succeeded"}` 但不做任何事。结果是"能力腿声明存在、执行是空壳"，
任何基于该旅程的校准样本都不代表真实审查工作。

本模块让能力腿真正工作，且**复用既有规则**而非另立一套（避免规则漂移）:

| action              | 规则来源                                                         |
|---------------------|------------------------------------------------------------------|
| `load_document`     | 文件 + YAML frontmatter 解析                                      |
| `check_format`      | `bin/gac/check-doc-freshness-gate.py`（90d）+ `docs/templates/*.md` 必填字段 |
| `check_sensitivity` | `cockpit.observatory.query_engine` 的 SECRET / ASSIGNMENT_SECRET 正则族 |
| `verify_basis`      | `bin/gac/doc-link-check.py`（相对链接）+ `evidence://` 引用约定     |

统一返回: `{"ok": bool, "checks": int, "passed": int, "issues": [...], ...}`
`confidence_of()` 把多次检查结果聚合成 0..1 置信度（驱动 human_gate 分支）。
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ── 规则常量（与既有实现对齐，改动需同步上游）─────────────────────────

STALE_DAYS = 90  # 对齐 bin/gac/check-doc-freshness-gate.py
REQUIRED_FRONTMATTER = ("type", "owner", "last-reviewed")  # 对齐 docs/templates/*-template.md

# 对齐 cockpit/observatory/query_engine.py 的 SECRET / ASSIGNMENT_SECRET
SECRET_RE = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{12,}|sk-[A-Za-z0-9_-]{16,})\b")
ASSIGNMENT_SECRET_RE = re.compile(
    r"(?i)(bearer\s+|(?:password|secret|token|api[-_]?key)\s*[:=]\s*)[^\s,;]+"
)
# 私密绝对路径（公文不应外泄本机路径）
PRIVATE_PATH_RE = re.compile(r"(?:/Users/[A-Za-z0-9._-]+/(?:Documents|Library|\.ssh|\.aws))")
# markdown 相对链接 / evidence 引用
MD_LINK_RE = re.compile(r"\]\(([^)#\s]+?)(?:#[^)\s]*)?\)")
EVIDENCE_REF_RE = re.compile(r"evidence://[^\s)\"']+")
MIN_LINES = 3  # 少于 3 行视为空壳文档


def _frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """解析 YAML frontmatter（无则返回空 dict 与全文）."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    raw = text[3:end]
    try:
        import yaml
        data = yaml.safe_load(raw)
        return (data if isinstance(data, dict) else {}), text[end + 4:]
    except Exception:
        return {}, text[end + 4:]


def _age_days(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value)
    try:
        if hasattr(value, "year"):
            when = datetime(value.year, value.month, value.day, tzinfo=UTC)
        else:
            when = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
    except Exception:
        return None
    return (datetime.now(UTC) - when).days


# ── 能力腿 ─────────────────────────────────────────────────────────────


def load_document(path: str | Path, root: Path) -> dict[str, Any]:
    """读取待审文档（路径越界拒绝；仅读不写）."""
    target = Path(path)
    if not target.is_absolute():
        target = root / target
    try:
        resolved = target.resolve()
        if root.resolve() not in resolved.parents and resolved != root.resolve():
            return {"ok": False, "reason": "path_outside_workspace", "path": str(path)}
    except OSError:
        return {"ok": False, "reason": "path_unresolvable", "path": str(path)}
    if not resolved.is_file():
        return {"ok": False, "reason": "file_missing", "path": str(path)}
    try:
        text = resolved.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return {"ok": False, "reason": f"read_error: {exc}", "path": str(path)}
    frontmatter, body = _frontmatter(text)
    return {
        "ok": True,
        "path": str(resolved.relative_to(root.resolve())),
        "frontmatter": frontmatter,
        "lines": len(body.splitlines()),
        "chars": len(text),
        "text": text,
    }


def check_format(doc: dict[str, Any]) -> dict[str, Any]:
    """格式检查: 必填 frontmatter + 新鲜度 + 非空壳（对齐 freshness gate / 模板契约）."""
    issues: list[dict[str, Any]] = []
    if not doc.get("ok"):
        return {"ok": False, "checks": 0, "passed": 0,
                "issues": [{"kind": "unreadable", "detail": doc.get("reason")}]}
    fm = doc.get("frontmatter") or {}
    checks = 0

    checks += 1
    missing = [k for k in REQUIRED_FRONTMATTER if not fm.get(k)]
    if missing:
        issues.append({"kind": "missing_frontmatter", "detail": ",".join(missing)})

    checks += 1
    age = _age_days(fm.get("last-reviewed"))
    if age is None:
        issues.append({"kind": "missing_last_reviewed", "detail": "无法解析 last-reviewed"})
    elif age > STALE_DAYS:
        issues.append({"kind": "stale", "detail": f"last-reviewed {age}d > {STALE_DAYS}d"})

    checks += 1
    if int(doc.get("lines", 0)) < MIN_LINES:
        issues.append({"kind": "too_short", "detail": f"正文 {doc.get('lines')} 行 < {MIN_LINES}"})

    return {"ok": not issues, "checks": checks, "passed": checks - len(issues),
            "issues": issues, "stale_days_limit": STALE_DAYS}


def check_sensitivity(doc: dict[str, Any], *, max_hits: int = 5) -> dict[str, Any]:
    """敏感项检查: 凭据 / 私密绝对路径（复用 cockpit sanitizer 正则族）."""
    if not doc.get("ok"):
        return {"ok": False, "checks": 0, "passed": 0,
                "issues": [{"kind": "unreadable", "detail": doc.get("reason")}]}
    text = doc.get("text", "")
    checks, issues = 1, []
    for name, pattern in (("credential", SECRET_RE),
                          ("assignment_secret", ASSIGNMENT_SECRET_RE),
                          ("private_path", PRIVATE_PATH_RE)):
        hits = pattern.findall(text)
        if hits:
            issues.append({"kind": name, "detail": f"{len(hits)} 处命中",
                           "samples": [str(h)[:40] for h in hits[:max_hits]]})
    # 命中即视为该腿失败（但不泄露原文）
    return {"ok": not issues, "checks": checks, "passed": checks - len(issues),
            "issues": issues}


def verify_basis(doc: dict[str, Any], root: Path) -> dict[str, Any]:
    """依据核验: 相对链接存在性 + evidence:// 引用（对齐 doc-link-check 规则）."""
    if not doc.get("ok"):
        return {"ok": False, "checks": 0, "passed": 0,
                "issues": [{"kind": "unreadable", "detail": doc.get("reason")}]}
    text = doc.get("text", "")
    doc_path = root / str(doc.get("path", ""))
    issues: list[dict[str, Any]] = []

    relative = [m for m in MD_LINK_RE.findall(text)
                if not m.startswith(("http://", "https://", "evidence://", "#", "mailto:"))]
    broken = []
    for link in relative:
        target = (doc_path.parent / link).resolve()
        if not target.exists():
            broken.append(link)
    checks = 1
    if broken:
        issues.append({"kind": "broken_relative_link", "detail": f"{len(broken)} 处",
                       "samples": broken[:5]})

    evidence_refs = EVIDENCE_REF_RE.findall(text)
    return {"ok": not issues, "checks": checks, "passed": checks - len(issues),
            "issues": issues, "relative_links": len(relative), "evidence_refs": len(evidence_refs)}


def confidence_of(*results: dict[str, Any], fallback: float = 0.85) -> float:
    """把各能力腿结果聚合成 0..1 置信度（驱动 human_gate 自动完成/升级分支）.

    无任何可判定检查时回退到 fallback（保持既有 stub 行为，避免影响其它场景）。
    """
    checks = sum(int(r.get("checks", 0)) for r in results)
    passed = sum(int(r.get("passed", 0)) for r in results)
    if checks <= 0:
        return fallback
    return round(max(0.0, min(1.0, passed / checks)), 4)


def review(path: str | Path, root: Path) -> dict[str, Any]:
    """一次性跑完全部能力腿（回灌/独立验证用；journey 内是逐 state 调用）."""
    doc = load_document(path, root)
    fmt = check_format(doc)
    sen = check_sensitivity(doc)
    bas = verify_basis(doc, root)
    return {
        "path": str(path),
        "loaded": doc.get("ok", False),
        "format": fmt,
        "sensitivity": sen,
        "basis": bas,
        "confidence": confidence_of(fmt, sen, bas),
        "issues": fmt["issues"] + sen["issues"] + bas["issues"],
    }
