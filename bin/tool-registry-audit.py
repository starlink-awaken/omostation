#!/usr/bin/env python3
"""Bin 工具盘点与依赖闭环扫描器。

目标：
- 给 bin 目录下脚本做归一化盘点（脚本数量、语言、命名债务）.
- 抽取脚本间调用（脚本级调用图）并输出出度/入度。
- 检测常见高风险模式：重复命令名、不可达引用、无 shebang 的可执行脚本、循环引用。
- 支持 emit/strict，用于 Makefile 与治理门禁接入（长期迭代）。
"""

from __future__ import annotations

import argparse
import json
import re
import stat
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = ROOT / "bin"
SCRIPT_SUFFIXES = {".py", ".sh", ".bash", ".zsh"}


CALL_RE = re.compile(
    r"""
    (?P<prefix>^\s*(?:source|\.|bash|sh|zsh|python3?|env)\s+)
    (?P<target>[^\s\"']+)
    """,
    re.VERBOSE,
)


def is_executable(path: Path) -> bool:
    mode = path.stat().st_mode
    return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def read_shebang(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            first = f.readline().strip()
    except OSError:
        return None
    return first if first.startswith("#!") else None


def classify(path: Path) -> str:
    if not path.is_file():
        return "other"
    shebang = read_shebang(path) or ""
    if path.suffix == ".py" or "python" in shebang:
        return "python"
    if path.suffix in {".sh", ".bash", ".zsh"} or "sh" in shebang or "bash" in shebang or "zsh" in shebang:
        return "shell"
    return "other"


def is_candidate_script(path: Path) -> bool:
    if not path.is_file():
        return False
    suffix = path.suffix.lower()
    if suffix in SCRIPT_SUFFIXES:
        return True
    if is_executable(path) and read_shebang(path):
        return True
    return False


def script_tier(path: Path) -> str:
    rel_parts = path.relative_to(ROOT).parts
    parts = set(rel_parts)
    if "_archive" in parts:
        return "archive"
    if len(rel_parts) > 1 and rel_parts[1] == "ssot":
        return "ssot"
    return "active"


def snake_case(name: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]*", name))


def normalize_name(name: str) -> str:
    stem = Path(name).name
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", stem)
    return re.sub(r"[-]+", "_", stem.lower())


def list_bin_files() -> List[Path]:
    files = []
    for path in BIN_DIR.rglob("*"):
        rel = path.relative_to(BIN_DIR)
        if rel.parts and rel.parts[0] in {".git", "__pycache__"}:
            continue
        if not path.is_file():
            continue
        if not is_candidate_script(path):
            continue
        files.append(path)
    return files


def parse_script_calls(path: Path) -> List[Path]:
    calls = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return calls

    for line in lines:
        m = CALL_RE.match(line.strip())
        if not m:
            continue
        raw_target = m.group("target")
        raw_target = raw_target.strip("\"'")
        if raw_target == path.name or raw_target == str(path):
            continue
        if raw_target.startswith("bin/"):
            candidate = (ROOT / raw_target).resolve()
            if candidate.is_file() and candidate.is_relative_to(ROOT):
                calls.append(candidate)
                continue
        if raw_target.startswith("./bin/"):
            candidate = (path.parent / raw_target).resolve()
            if candidate.is_file() and candidate.is_relative_to(ROOT):
                calls.append(candidate)
                continue
        if raw_target in {".", ".."}:
            continue
        # 常见：python file 参数写裸名字时，不做硬解析，避免误报
    return calls


def build_graph(paths: List[Path]) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    out_edges: Dict[str, Set[str]] = defaultdict(set)
    in_edges: Dict[str, Set[str]] = defaultdict(set)
    path_by_rel = {str(p.relative_to(ROOT)): p for p in paths}
    for path in paths:
        src = str(path.relative_to(ROOT))
        for target in parse_script_calls(path):
            if not str(target.relative_to(ROOT)) in path_by_rel:
                continue
            dst = str(target.relative_to(ROOT))
            out_edges[src].add(dst)
            in_edges[dst].add(src)
        out_edges.setdefault(src, set())
        in_edges.setdefault(src, in_edges[src])  # 保持孤立节点也可见
    return out_edges, in_edges


def detect_cycles(out_edges: Dict[str, Set[str]]) -> List[List[str]]:
    # 简化版 DFS cycle 检测；返回部分环路证据
    cycles: List[List[str]] = []
    state = {}
    stack = []

    def dfs(node: str) -> None:
        state[node] = "visiting"
        stack.append(node)
        for nxt in sorted(out_edges.get(node, set())):
            if state.get(nxt) == "visiting":
                idx = stack.index(nxt)
                cycles.append(stack[idx:] + [nxt])
            elif state.get(nxt) is None:
                dfs(nxt)
        stack.pop()
        state[node] = "done"

    for n in out_edges:
        if state.get(n) is None:
            dfs(n)
    # 去重：保持短的环路
    uniq = []
    seen = set()
    for c in cycles:
        key = tuple(c)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
    return uniq


def is_self_cycle(cycle: List[str]) -> bool:
    return len(cycle) == 2 and cycle[0] == cycle[1]


def filter_cycles(cycles: List[List[str]]) -> List[List[str]]:
    return [cycle for cycle in cycles if not is_self_cycle(cycle)]


def active_duplicate_files(files: List[str]) -> List[str]:
    active = []
    for f in files:
        try:
            tier = script_tier((ROOT / f).resolve())
        except Exception:
            tier = "active"
        if tier == "active":
            active.append(f)
    return active


def classify_duplication_conflicts(duplicates: Dict[str, List[str]]) -> Tuple[Dict[str, List[str]], List[Dict[str, object]]]:
    high_conflicts: List[Dict[str, object]] = []
    for name, files in sorted(duplicates.items()):
        active_files = active_duplicate_files(files)
        if len(active_files) < 2:
            continue
        active_exts = {Path(file).suffix.lower() for file in active_files}
        if len(active_exts) > 1 and len(active_files) == 2:
            continue
        high_conflicts.append(
            {
                "name": name,
                "active_files": sorted(active_files),
                "exts": sorted(active_exts),
                "file_count": len(active_files),
            }
        )
    return duplicates, high_conflicts


def summarize(paths: List[Path]) -> Dict:
    types: Counter[str] = Counter()
    duplicates: defaultdict[str, List[str]] = defaultdict(list)
    missing_shebang: List[str] = []
    non_snake: List[str] = []
    for path in paths:
        rel = str(path.relative_to(ROOT))
        lang = classify(path)
        types[lang] += 1
        if is_executable(path) and read_shebang(path) is None:
            missing_shebang.append(rel)
        name = path.name
        norm = normalize_name(name)
        duplicates[norm].append(rel)
        if not snake_case(Path(name).stem):
            non_snake.append(rel)

    duplicated = {
        name: files for name, files in duplicates.items() if len(files) > 1
    }
    duplicate_scopes, duplicate_conflicts = classify_duplication_conflicts(duplicated)
    out_edges, in_edges = build_graph(paths)
    out_degree = {k: len(v) for k, v in out_edges.items()}
    in_degree = {k: len(v) for k, v in in_edges.items()}
    cycles = filter_cycles(detect_cycles(out_edges))
    top_out = sorted(out_degree.items(), key=lambda i: i[1], reverse=True)[:10]
    top_in = sorted(in_degree.items(), key=lambda i: i[1], reverse=True)[:10]

    convergence = []
    for node, outd in top_out:
        convergence.append({"path": node, "type": "hub_out", "out_degree": outd})
    for node, ind in top_in:
        convergence.append({"path": node, "type": "hub_in", "in_degree": ind})

    return {
        "stats": {
            "total_scripts": len(paths),
            "by_type": dict(types),
            "missing_shebang": len(missing_shebang),
            "non_snake": len(non_snake),
            "duplicate_names": len(duplicated),
            "high_conflict_duplicates": len(duplicate_conflicts),
            "edges": sum(out_degree.values()),
        },
        "findings": {
            "missing_shebang": sorted(missing_shebang),
            "non_snake": sorted(non_snake),
            "duplicate_names": duplicate_scopes,
            "duplicate_conflicts": duplicate_conflicts,
            "cycles": cycles[:20],
        },
        "top_out_degree": top_out,
        "top_in_degree": top_in,
        "convergence_candidates": convergence,
        "graph": {"out": {k: sorted(v) for k, v in out_edges.items()}},
    }


def emit_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def strict_checks(summary: Dict) -> List[str]:
    errors = []
    if summary["stats"]["missing_shebang"] > 0:
        errors.append(f"executable scripts missing shebang: {summary['stats']['missing_shebang']}")
    if summary["stats"]["high_conflict_duplicates"] > 0:
        errors.append(f"high-confidence duplicate normalized script names: {summary['stats']['high_conflict_duplicates']}")
    if summary["findings"]["cycles"]:
        errors.append(f"script cycle detected: {len(summary['findings']['cycles'])}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="artifacts/bin-tool-registry-audit.json")
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    files = list_bin_files()
    payload = summarize(files)
    payload["snapshot"] = str((ROOT / args.snapshot).resolve())
    if args.emit:
        emit_json(ROOT / args.snapshot, payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("== Bin Tool Registry Audit ==")
    print(f"total: {payload['stats']['total_scripts']}")
    print(f"by type: {payload['stats']['by_type']}")
    print(f"missing shebang: {payload['stats']['missing_shebang']}")
    print(f"non-snake: {payload['stats']['non_snake']}")
    print(f"duplicate names: {payload['stats']['duplicate_names']}")
    print(f"high-confidence duplicate names: {payload['stats']['high_conflict_duplicates']}")
    print(f"cycles: {len(payload['findings']['cycles'])}")
    print("top out-degree:", payload["top_out_degree"][:3])
    print("top in-degree:", payload["top_in_degree"][:3])
    if args.strict:
        errors = strict_checks(payload)
        if errors:
            print("STRICT FAIL:")
            for item in errors:
                print(f" - {item}")
            return 2
        print("strict checks: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
