"""cockpit command-audit — 15 维命令评分卡 SSOT 管理体系.

子命令:
  init      按命令树枚举生成缺失的评分卡骨架 yaml
  validate  schema 校验 (15 维齐全 / score 值域 / evidence / 禁手写 total)
  report    汇总生成 docs/command-audit/_REPORT.md
  lint      覆盖率 + 过期 + schema 检查 (CI/pre-pr gate, 有违规非零退出)
"""

from __future__ import annotations

import argparse
import datetime as _dt
from pathlib import Path

import yaml

AUDIT_DIR = Path("docs/command-audit")

# 15 维评分卡维度 (key → 中文名), 顺序即展示顺序。
DIMENSIONS: dict[str, str] = {
    "functionality": "功能完整度",
    "use_case": "应用场景",
    "goal_clarity": "目标清晰度",
    "usability": "可用性",
    "io_readability": "输入输出易读性",
    "performance": "性能",
    "stability": "稳定性",
    "observability": "可观察性",
    "logging_alerting": "日志监控告警",
    "operability": "可运营性",
    "maintainability": "可维护性",
    "extensibility": "扩展性",
    "evolvability": "可进化能力",
    "agent_friendliness": "Agent 友好度",
    "state_memory": "状态与长期记忆",
}

VALID_SCORES = {1, 2, 3, 4, 5, None}
STALE_DAYS = 180

# P0 高频命令 (report 达标率统计口径)
P0_COMMANDS = [
    "research", "memory", "knowledge", "health", "status", "daily", "audit",
    "gac", "bos", "agent", "agent-workflow", "omo", "debt", "scenario",
    "chain", "data", "search", "brain", "dashboard", "help", "quickstart",
    "capabilities", "ops", "mesh", "workflow", "iterate", "compass", "journey",
]

HELP_HEADER = "cockpit command-audit — 15 维命令评分卡管理 (功能完整度/应用场景/目标清晰度/可用性/输入输出易读性/性能/稳定性/可观察性/日志监控告警/可运营性/可维护性/扩展性/可进化能力/Agent 友好度/状态与长期记忆)"


# ── 命令树枚举 (权威节点来源) ────────────────────────────────────────────────

def walk_command_tree() -> list[str]:
    """从 create_parser() 递归枚举全部命令节点, 如 ["research", "research.list"].

    REMAINDER 型委派命令 (无子 parser) 仅记根节点; alias 不重复计数
    (同一 parser 注册多个名时只取首个主名)。
    """
    from cockpit.cli import create_parser

    parser, sub, _cls = create_parser()
    seen_parsers: set[int] = set()
    nodes: list[str] = []

    def walk(prefix: str, action: argparse._SubParsersAction) -> None:
        for name, child in action.choices.items():
            path = f"{prefix}.{name}" if prefix else name
            if id(child) in seen_parsers:
                continue  # alias → 同一 parser, 跳过
            seen_parsers.add(id(child))
            nodes.append(path)
            for act in child._actions:
                if isinstance(act, argparse._SubParsersAction):
                    walk(path, act)

    nodes.append("")  # placeholder removed below
    nodes.clear()
    walk("", sub)
    return nodes


# ── 评分卡读写 ────────────────────────────────────────────────────────────────

def card_path(cmd_path: str, root: Path | None = None) -> Path:
    return (root or AUDIT_DIR) / f"{cmd_path}.yaml"


def load_card(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def skeleton(cmd_path: str) -> dict:
    from cockpit.commands.delegation import ensure_delegated_catalog
    from cockpit.commands.registry import COMMAND_CATALOG

    ensure_delegated_catalog()
    top = cmd_path.split(".")[0]
    meta = COMMAND_CATALOG.get(top)
    return {
        "meta": {
            "cmd_path": cmd_path,
            "category": meta.category if meta else "🔧 通用 (General)",
            "owner": "cockpit",
            "maturity": meta.maturity if meta else "stable",
            "delegated_target": meta.delegated_target if meta else None,
            "last_audited": None,
            "auditor": "agent:worker-d-audit",
        },
        "dimensions": {k: {"score": None, "evidence": "", "suggestion": ""} for k in DIMENSIONS},
        "summary": {"grade": None},
    }


def dump_card(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=100)


# ── 校验 / 统计 ───────────────────────────────────────────────────────────────

def validate_card(data: dict, cmd_path: str) -> list[str]:
    """返回违规列表 (空 = 通过)。"""
    errs: list[str] = []
    if set(data) - {"meta", "dimensions", "summary"}:
        errs.append(f"未知顶级字段: {set(data) - {'meta', 'dimensions', 'summary'}}")
    dims = data.get("dimensions") or {}
    missing = set(DIMENSIONS) - set(dims)
    extra = set(dims) - set(DIMENSIONS)
    if missing:
        errs.append(f"缺失维度: {sorted(missing)}")
    if extra:
        errs.append(f"未知维度: {sorted(extra)}")
    for key, dim in dims.items():
        if not isinstance(dim, dict):
            errs.append(f"{key}: 非 mapping")
            continue
        if set(dim) - {"score", "evidence", "suggestion"}:
            errs.append(f"{key}: 未知字段 {set(dim) - {'score', 'evidence', 'suggestion'}}")
        score = dim.get("score")
        if score is not None and (not isinstance(score, int) or isinstance(score, bool) or score not in {1, 2, 3, 4, 5}):
            errs.append(f"{key}: score 非法 ({score!r}), 须为 1-5 或 null")
        if score is not None and not str(dim.get("evidence") or "").strip():
            errs.append(f"{key}: score 非 null 时 evidence 必填")
    summary = data.get("summary") or {}
    if "total" in summary:
        errs.append("summary.total 由 CLI 实算, 手写视为违规")
    if set(summary) - {"grade", "total"}:
        errs.append(f"summary 未知字段: {set(summary) - {'grade', 'total'}}")
    meta = data.get("meta") or {}
    if meta.get("cmd_path") != cmd_path:
        errs.append(f"meta.cmd_path ({meta.get('cmd_path')!r}) 与文件名不一致")
    return errs


def compute_total(data: dict) -> float | None:
    scores = [d.get("score") for d in data.get("dimensions", {}).values() if d.get("score") is not None]
    return round(sum(scores) / len(scores), 2) if scores else None


def grade_of(total: float | None) -> str:
    if total is None:
        return "-"
    if total >= 4.5:
        return "S"
    if total >= 3.5:
        return "A"
    if total >= 2.5:
        return "B"
    if total >= 1.5:
        return "C"
    return "D"


def coverage(nodes: list[str], root: Path | None = None) -> tuple[list[str], list[str]]:
    root = root or AUDIT_DIR
    have = [n for n in nodes if card_path(n, root).exists()]
    return have, [n for n in nodes if n not in have]


def is_stale(data: dict, today: _dt.date | None = None) -> bool:
    la = (data.get("meta") or {}).get("last_audited")
    if not la:
        return True
    try:
        d = _dt.date.fromisoformat(str(la)[:10])
    except ValueError:
        return True
    today = today or _dt.date.today()
    return (today - d).days > STALE_DAYS


# ── 子命令实现 ────────────────────────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> int:
    nodes = walk_command_tree()
    only = set(args.only or [])
    targets = [n for n in nodes if not only or n in only or any(n.startswith(o + ".") for o in only)]
    created = 0
    for n in targets:
        p = card_path(n)
        if p.exists() and not args.force:
            continue
        dump_card(skeleton(n), p)
        created += 1
    have, missing = coverage(nodes)
    print(f"命令树节点: {len(nodes)} · 本次新建: {created} · 已有评分卡: {len(have)}/{len(nodes)} ({len(have) * 100 // len(nodes)}%)")
    if missing:
        print(f"缺失: {', '.join(missing[:20])}{' …' if len(missing) > 20 else ''}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    nodes = walk_command_tree()
    have, missing = coverage(nodes)
    errs_total = 0
    for n in have:
        data = load_card(card_path(n))
        errs = validate_card(data, n)
        for e in errs:
            print(f"[FAIL] {n}: {e}")
            errs_total += 1
    if args.strict and missing:
        print(f"[FAIL] --strict 要求覆盖率 100%, 缺失 {len(missing)} 张: {', '.join(missing[:20])}")
        errs_total += len(missing)
    print(f"validate: {len(have)} 张评分卡, {errs_total} 个违规")
    return 1 if errs_total else 0


def cmd_lint(args: argparse.Namespace) -> int:
    nodes = walk_command_tree()
    have, missing = coverage(nodes)
    violations = 0
    for n in have:
        data = load_card(card_path(n))
        for e in validate_card(data, n):
            print(f"[LINT] schema 违规 {n}: {e}")
            violations += 1
        if any((d.get("score") is not None) for d in data.get("dimensions", {}).values()) and is_stale(data):
            print(f"[LINT] 过期 {n}: last_audited={data.get('meta', {}).get('last_audited')} 超 {STALE_DAYS} 天或未评审")
            violations += 1
    if missing:
        print(f"[LINT] 覆盖不全: {len(missing)}/{len(nodes)} 节点缺评分卡")
        violations += 1
    print(f"lint: 覆盖 {len(have)}/{len(nodes)}, {violations} 项违规")
    return 1 if violations else 0


def cmd_report(args: argparse.Namespace) -> int:
    nodes = walk_command_tree()
    have, missing = coverage(nodes)
    audited: list[tuple[str, dict, float | None]] = []
    schema_errs = 0
    for n in have:
        data = load_card(card_path(n))
        errs = validate_card(data, n)
        if errs:
            schema_errs += len(errs)
            print(f"[WARN] schema 违规 {n}: {errs[0]} (+{len(errs) - 1})")
            continue
        audited.append((n, data, compute_total(data)))

    lines: list[str] = []
    lines.append("# Cockpit 命令评分卡报告 (command-audit)")
    lines.append("")
    lines.append(f"> 生成: {_dt.date.today().isoformat()} · 节点总数: {len(nodes)} · 评分卡: {len(have)} · 覆盖率: {len(have) * 100 // len(nodes)}%")
    lines.append("")

    lines.append("## 各维度均分")
    lines.append("")
    lines.append("| 维度 | 中文名 | 已评数 | 均分 |")
    lines.append("|---|---|---|---|")
    for key, zh in DIMENSIONS.items():
        scores = [d[1]["dimensions"][key]["score"] for d in audited if d[1]["dimensions"][key]["score"] is not None]
        avg = f"{sum(scores) / len(scores):.2f}" if scores else "-"
        lines.append(f"| {key} | {zh} | {len(scores)} | {avg} |")
    lines.append("")

    scored = sorted([a for a in audited if a[2] is not None], key=lambda a: a[2])
    lines.append(f"## 低分 TOP-{args.top}")
    lines.append("")
    lines.append("| cmd_path | total | grade | category |")
    lines.append("|---|---|---|---|")
    for n, data, total in scored[: args.top]:
        lines.append(f"| {n} | {total:.2f} | {grade_of(total)} | {data['meta'].get('category', '')} |")
    lines.append("")

    p0_have = [n for n in P0_COMMANDS if n in have]
    p0_scored = [a for a in audited if a[0] in P0_COMMANDS and a[2] is not None]
    p0_pass = [a for a in p0_scored if a[2] >= 3.5]
    lines.append("## P0 高频命令达标率")
    lines.append("")
    lines.append(f"- P0 列表: {len(P0_COMMANDS)} 个 · 有评分卡: {len(p0_have)} · 已评分: {len(p0_scored)} · 达标 (total≥3.5): {len(p0_pass)}/{len(p0_scored) if p0_scored else 0}")
    for n, data, total in sorted(audited, key=lambda a: a[0]):
        if n in P0_COMMANDS and total is not None:
            mark = "✅" if total >= 3.5 else "❌"
            lines.append(f"  - {mark} {n}: {total:.2f} ({grade_of(total)})")
    lines.append("")
    if schema_errs:
        lines.append(f"⚠ schema 违规 {schema_errs} 处, 详见 validate 输出。")

    out = Path(args.output) if args.output else AUDIT_DIR / "_REPORT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写入 {out} (已评分 {len(scored)}/{len(have)}, schema 违规 {schema_errs})")
    return 0


# ── 注册 ──────────────────────────────────────────────────────────────────────

def register(sub: argparse._SubParsersAction, workspace_parser: type) -> None:
    p = sub.add_parser(
        "command-audit",
        help=HELP_HEADER,
        description=HELP_HEADER,
    )
    sub2 = p.add_subparsers(dest="audit_command", required=True)
    i = sub2.add_parser("init", help="按命令树生成缺失评分卡骨架")
    i.add_argument("--only", nargs="*", help="仅生成指定 cmd_path (含子节点)")
    i.add_argument("--force", action="store_true", help="覆盖已有评分卡")
    i.set_defaults(func=cmd_init)
    v = sub2.add_parser("validate", help="schema 校验")
    v.add_argument("--strict", action="store_true", help="要求覆盖率 100%%")
    v.set_defaults(func=cmd_validate)
    lp = sub2.add_parser("lint", help="覆盖率 + 过期 + schema 检查")
    lp.set_defaults(func=cmd_lint)
    r = sub2.add_parser("report", help="汇总生成 _REPORT.md")
    r.add_argument("--category", help="按 category 过滤 (保留参数)")
    r.add_argument("--top", type=int, default=20, help="低分 TOP-N")
    r.add_argument("--output", help="输出文件 (默认 docs/command-audit/_REPORT.md)")
    r.set_defaults(func=cmd_report)


def cmd_command_audit(args: argparse.Namespace) -> int:
    """cli.py handlers 入口 (与 registry-based dispatch 对齐)."""
    import sys

    handlers = {"init": cmd_init, "validate": cmd_validate, "lint": cmd_lint, "report": cmd_report}
    h = handlers.get(getattr(args, "audit_command", ""))
    if h is None:
        print("用法: cockpit command-audit {init|validate|lint|report}", file=sys.stderr)
        return 2
    return h(args)
