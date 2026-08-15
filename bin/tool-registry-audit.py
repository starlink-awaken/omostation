#!/usr/bin/env python3
"""Bin 工具清单与能力下沉治理脚本.

目标:
- 盘点 bin 下每个可执行/入口脚本。
- 识别同名命令冲突、legacy 命名、缺失 shebang 入口。
- 抽取跨脚本调用关系，输出可复用依赖拓扑指标。
- 产出可归档快照，支撑长期下沉与复盘。
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import stat
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]
BIN_DIR = WORKSPACE / "bin"
IGNORE_NAMES = {"__init__.py"}
IGNORE_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", ".mypy_cache"}
DOC_EXTS = {".md", ".rst", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".json", ".toml", ".yaml", ".yml"}
SCRIPT_EXTS = {".py", ".sh", ".bash", ".zsh", ".pl", ".rb", ".tsx", ".ts", ".js"}
NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
SCRIPT_CALL_RE = re.compile(r"(?:^|[\s\"'\(])(?:\.?/)?bin/([A-Za-z0-9_./-]+)")
MAX_LINES_FOR_NOTE = 220


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _has_shebang(path: Path) -> bool:
    text = _read_text(path)
    first_line = text.splitlines()[0] if text else ""
    return first_line.startswith("#!")


def _is_executable(path: Path) -> bool:
    try:
        mode = path.stat().st_mode
    except OSError:
        return False
    return bool(mode & stat.S_IXUSR)


def _is_candidate(path: Path) -> bool:
    if not path.is_file() or path.name in IGNORE_NAMES:
        return False
    if path.suffix.lower() in DOC_EXTS:
        return False
    rel_parts = path.relative_to(BIN_DIR).parts
    if any(part in IGNORE_DIRS for part in rel_parts[:-1]):
        return False
    if rel_parts[0] == "lib":
        return False
    if _is_executable(path):
        return True
    if path.suffix.lower() in SCRIPT_EXTS:
        return _has_shebang(path)
    if path.suffix == "":
        return _has_shebang(path)
    return False


def _domain(rel_path: Path) -> str:
    if rel_path.parent == Path("."):
        return "root"
    return rel_path.parts[0]


def _line_count(path: Path) -> int:
    return len(_read_text(path).splitlines())


def _looks_like_legacy_snake_case(name: str) -> bool:
    return "_" in name and "-" not in name


def _extract_python_imports(path: Path) -> list[str]:
    if path.suffix != ".py":
        return []
    text = _read_text(path)
    try:
        module = ast.parse(text)
    except SyntaxError:
        return []
    imports = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = (alias.name or "").split(".")[0]
                if top:
                    imports.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top:
                    imports.add(top)
    return sorted(imports)


def _normalize_script_path(raw: str) -> str:
    rel = raw.replace("\\", "/").strip()
    rel = rel.removeprefix("./")
    rel = rel.removeprefix("../")
    rel = rel.removeprefix("../")
    rel = rel.removeprefix("bin/")
    rel = rel.strip("/ ")
    return rel


def _path_aliases(path: str) -> list[str]:
    rel = path.strip("/")
    out = {rel}
    if rel.endswith("/"):
        rel = rel.rstrip("/")
        out.add(rel)
    for ext in (".py", ".sh", ".bash", ".zsh", ".pl", ".rb", ".js", ".ts", ".tsx"):
        if rel.endswith(ext):
            out.add(rel[:-len(ext)])
    return sorted(out)


def _extract_script_calls(path: Path) -> list[str]:
    calls = set()
    for match in SCRIPT_CALL_RE.finditer(_read_text(path)):
        calls.add(_normalize_script_path(match.group(1)))
    return sorted(calls)


def _build_entries(scope: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(BIN_DIR.rglob("*")):
        if not _is_candidate(path):
            continue
        rel = path.relative_to(BIN_DIR)
        if scope != "all" and rel.parts and rel.parts[0] != scope:
            continue
        name = path.stem if path.suffix else path.name
        path_str = rel.as_posix()
        entries.append(
            {
                "path": path_str,
                "domain": _domain(rel),
                "command": name,
                "extension": path.suffix or "<noext>",
                "executable": _is_executable(path),
                "has_shebang": _has_shebang(path),
                "size_bytes": path.stat().st_size if path.is_file() else 0,
                "lines": _line_count(path),
                "kebab_name": bool(NAME_RE.match(name)),
                "legacy_snake": _looks_like_legacy_snake_case(name),
                "imports": _extract_python_imports(path),
                "script_calls": _extract_script_calls(path),
            }
        )
    return entries


def _build_indexes(entries: list[dict[str, Any]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    by_path: dict[str, set[str]] = defaultdict(set)
    by_name: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        path_key = entry["path"]
        by_name[entry["command"]].add(path_key)
        by_name[path_key.rsplit("/", 1)[-1]].add(path_key)
        by_name[path_key.rsplit("/", 1)[-1].removesuffix(".py")].add(path_key)
        for alias in _path_aliases(path_key):
            by_path[alias].add(path_key)
    return by_path, by_name


def _resolve_script_dependency(item: dict[str, Any], by_path: dict[str, set[str]], by_name: dict[str, set[str]]) -> set[str]:
    deps: set[str] = set()
    for hit in item["script_calls"]:
        hit = hit.strip()
        if not hit:
            continue
        matched = False
        for alias in _path_aliases(hit):
            if alias in by_path:
                deps.update(by_path[alias])
                matched = True
                break
        if matched:
            continue
        base = hit.split("/")[-1]
        if base in by_path:
            deps.update(by_path[base])
            continue
        if base in by_name:
            deps.update(by_name[base])
    return {dep for dep in deps if dep != item["path"]}


def _detect_cycles(edges: list[tuple[str, str]]) -> list[str]:
    adj: dict[str, set[str]] = defaultdict(set)
    indeg = Counter()
    nodes: set[str] = set()
    for src, dst in edges:
        adj[src].add(dst)
        indeg[dst] += 1
        nodes.add(src)
        nodes.add(dst)
    for node in nodes:
        indeg.setdefault(node, 0)
    q = deque([n for n in nodes if indeg[n] == 0])
    visited: set[str] = set()
    while q:
        node = q.popleft()
        visited.add(node)
        for nxt in sorted(adj.get(node, set())):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    return sorted(nodes - visited)


def _audit(entries: list[dict[str, Any]]) -> dict[str, Any]:
    by_domain = Counter(item["domain"] for item in entries)
    by_ext = Counter(item["extension"] for item in entries)

    by_command = defaultdict(list)
    for item in entries:
        by_command[item["command"]].append(item["path"])

    duplicate_commands = []
    for command, paths in sorted(by_command.items()):
        if len(paths) > 1:
            duplicate_commands.append(
                {
                    "command": command,
                    "count": len(paths),
                    "paths": sorted(paths),
                    "severity": "high" if len(paths) > 2 else "warn",
                }
            )

    legacy_names = [
        item["path"]
        for item in entries
        if item["legacy_snake"] and item["domain"] != "_archive"
    ]
    no_shebang = [
        item["path"]
        for item in entries
        if item["extension"] in SCRIPT_EXTS and not item["has_shebang"]
    ]
    thick_entries = [
        {
            "path": item["path"],
            "domain": item["domain"],
            "command": item["command"],
            "lines": item["lines"],
        }
        for item in entries
        if item["lines"] >= MAX_LINES_FOR_NOTE and item["extension"] in SCRIPT_EXTS
    ]
    thick_entries.sort(key=lambda item: item["lines"], reverse=True)

    by_path, by_name = _build_indexes(entries)
    dep_graph: list[dict[str, Any]] = []
    edges: list[tuple[str, str]] = []
    for item in entries:
        deps = sorted(_resolve_script_dependency(item, by_path, by_name))
        dep_graph.append({"from": item["path"], "to": deps})
        for dep in deps:
            edges.append((item["path"], dep))

    dep_out = Counter()
    dep_in = Counter()
    for src, dst in edges:
        dep_out[src] += 1
        dep_in[dst] += 1

    cycle_nodes = _detect_cycles(edges)

    dependency = {
        "edges": dep_graph,
        "out_degree_top": [
            {"path": path, "out_degree": degree}
            for path, degree in dep_out.most_common(20)
        ],
        "in_degree_top": [
            {"path": path, "in_degree": degree}
            for path, degree in dep_in.most_common(20)
        ],
    }

    return {
        "total_commands": len(entries),
        "domains": len(by_domain),
        "commands_by_domain": sorted(by_domain.items()),
        "extensions": dict(by_ext),
        "duplicate_count": len(duplicate_commands),
        "duplicate_commands": duplicate_commands,
        "legacy_snake_case": sorted(legacy_names),
        "missing_shebang": sorted(no_shebang),
        "thick_entries": thick_entries,
        "dependency": dependency,
        "cycle_nodes": cycle_nodes,
    }


def _issue_level(count: int) -> str:
    if count <= 1:
        return "ok"
    if count == 2:
        return "warn"
    return "high"


def _build_payload(scope: str) -> dict[str, Any]:
    entries = _build_entries(scope)
    audit = _audit(entries)

    issues = []
    if audit["duplicate_count"] > 0:
        issues.append(
            {
                "type": "duplicate_commands",
                "count": audit["duplicate_count"],
                "severity": "high",
                "message": "同名入口命令重复，请先定义迁移顺序再收敛",
            }
        )
    if audit["missing_shebang"]:
        issues.append(
            {
                "type": "missing_shebang",
                "count": len(audit["missing_shebang"]),
                "severity": "warn",
                "message": "检测到无 shebang 的可执行入口",
            }
        )
    if audit["legacy_snake_case"]:
        issues.append(
            {
                "type": "legacy_snake_case",
                "count": len(audit["legacy_snake_case"]),
                "severity": "warn",
                "message": "存在 snake_case 命名，建议逐步迁移为 kebab-case 并保留兼容 shim",
            }
        )
    if audit["cycle_nodes"]:
        issues.append(
            {
                "type": "dependency_cycle",
                "count": len(audit["cycle_nodes"]),
                "severity": "warn",
                "message": "存在依赖闭环，优先打断跨脚本耦合路径",
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "totals": audit,
        "issues": issues,
    }


def _run_text(payload: dict[str, Any]) -> int:
    totals = payload["totals"]
    issues = payload["issues"]
    print(f"[tool-registry-audit] scope={payload['scope']} generated_at={payload['generated_at']}")
    print(
        f"总入口: {totals['total_commands']} | "
        f"重复命令: {totals['duplicate_count']} | "
        f"legacy 命名: {len(totals['legacy_snake_case'])} | "
        f"缺少 shebang: {len(totals['missing_shebang'])} | "
        f"厚脚本: {len(totals['thick_entries'])} | "
        f"闭环节点: {len(totals['cycle_nodes'])}"
    )
    if totals["commands_by_domain"]:
        print(f"域分布: {dict(totals['commands_by_domain'])}")
    if totals["extensions"]:
        print(f"扩展分布: {totals['extensions']}")

    if issues:
        print(f"发现 {len(issues)} 类治理关注点:")
        for item in issues:
            print(f"  - [{item['severity']}] {item['type']} x{item['count']} | {item['message']}")

        if totals["duplicate_commands"]:
            print("重复命令 Top5:")
            for item in totals["duplicate_commands"][:5]:
                print(f"  - {item['command']} -> {item['count']} ({', '.join(item['paths'])})")

        if totals["dependency"]["out_degree_top"]:
            print("调用边高度节点 Top5:")
            for item in totals["dependency"]["out_degree_top"][:5]:
                print(f"  - {item['path']} ({item['out_degree']})")

        if totals["cycle_nodes"]:
            print("依赖闭环样本:")
            for path in totals["cycle_nodes"][:10]:
                print(f"  - {path}")

        return 0

    print("未检测到治理异常，当前状态可作为基线")
    return 0


def _run_json(payload: dict[str, Any], emit: str | None) -> int:
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if emit:
        emit_path = Path(emit)
        emit_path.parent.mkdir(parents=True, exist_ok=True)
        emit_path.write_text(json_text + "\n", encoding="utf-8")
        print(f"已写入快照: {emit_path}")
    print(json_text)
    return 0


def _evaluate_strict(payload: dict[str, Any]) -> int:
    totals = payload["totals"]
    if totals["duplicate_count"] > 0:
        return 1
    if totals["missing_shebang"]:
        return 1
    if totals["cycle_nodes"]:
        return 1
    return 0


def _available_scopes() -> list[str]:
    scopes = {"all"}
    if not BIN_DIR.is_dir():
        return sorted(scopes)
    for item in BIN_DIR.iterdir():
        if item.is_dir() and not item.name.startswith(".") and item.name not in IGNORE_DIRS:
            scopes.add(item.name)
    return sorted(scopes)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="bin 工具能力下沉前置盘点")
    parser.add_argument(
        "--scope",
        default="all",
        help="按域过滤（all 表示全量）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON（默认人类可读摘要）",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式，发现阻断问题返回非 0",
    )
    parser.add_argument(
        "--emit",
        metavar="PATH",
        help="快照落盘路径（与 --json 一同工作）",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.scope not in _available_scopes():
        parser.error(f"非法 scope={args.scope}；支持: {', '.join(_available_scopes())}")

    payload = _build_payload(args.scope)

    if args.json or args.emit:
        rc = _run_json(payload, args.emit)
    else:
        rc = _run_text(payload)

    if args.strict:
        strict_rc = _evaluate_strict(payload)
        if strict_rc != 0:
            return strict_rc
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
