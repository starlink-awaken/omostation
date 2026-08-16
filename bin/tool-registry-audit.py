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
import hashlib
import re
import stat
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = ROOT / "bin"
SCRIPTS_BIN_DIR = ROOT / "scripts" / "bin"
SCRIPT_SUFFIXES = {".py", ".sh", ".bash", ".zsh"}
WRAPPER_HINTS = ("Compatibility wrapper", "CLI alias")
DEFAULT_PARALLEL_MANIFEST = ROOT / "docs/operations/bin-scripts-convergence-manifest.json"


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
    if suffix == ".md":
        return False
    if suffix in SCRIPT_SUFFIXES:
        return True
    if is_executable(path) and read_shebang(path):
        return True
    return False


def file_signature(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_parallel_manifest(path: Path) -> dict[str, dict[str, object]]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entries = raw.get("entries") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return {}
    manifest: dict[str, dict[str, object]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        manifest[normalize_name(name)] = {
            "status": entry.get("status"),
            "bin": entry.get("bin"),
            "scripts": entry.get("scripts"),
            "action": entry.get("action", "pending"),
            "owner": entry.get("owner", "governance"),
            "note": entry.get("note", ""),
            "evidence": entry.get("evidence"),
        }
    return manifest


def is_managed_parallel_entry(name: str, manifest_entry: dict[str, object] | None) -> bool:
    if not manifest_entry:
        return False
    status = str(manifest_entry.get("status", "")).strip().lower()
    return status in {"", "managed", "active", "accepted", "approved", "stable"}


def is_compatible_shim_policy(entry: dict[str, object] | None) -> bool:
    if not entry:
        return False
    action = str(entry.get("action", "")).lower()
    return "shim" in action or "compat" in action


def _is_archive_path(path: Path) -> bool:
    return "_archive" in path.relative_to(ROOT).parts or "PACKS" in path.relative_to(ROOT).parts


def _is_shim(path: Path, text: str) -> bool:
    if not text:
        return False
    if "Compatibility wrapper" in text:
        return True
    if "CLI alias" in text:
        return True
    if path.suffix in {".sh", ".bash", ".zsh"} and "exec " in text:
        return True
    return False


def script_role(path: Path) -> str:
    if _is_archive_path(path):
        return "archive"
    if path.suffix == ".md":
        return "doc"
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            text = f.read(4096)
    except OSError:
        text = ""
    return "shim" if _is_shim(path, text) else "implementation"


def script_tier(path: Path) -> str:
    rel_parts = path.relative_to(ROOT).parts
    if _is_archive_path(path):
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


def list_bin_files(scope: str = "bin") -> List[Path]:
    files = []
    roots = []
    if scope in {"bin", "both"} and BIN_DIR.is_dir():
        roots.append(BIN_DIR)
    if scope in {"scripts", "both"} and SCRIPTS_BIN_DIR.is_dir():
        roots.append(SCRIPTS_BIN_DIR)
    for base in roots:
        for path in base.rglob("*"):
            rel = path.relative_to(base)
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


def _parallel_gap_reasons(
    name: str,
    bin_files: List[str],
    script_files: List[str],
    manifest_entry: dict[str, object] | None,
) -> List[str]:
    if not manifest_entry:
        return ["missing_manifest_entry"]

    reasons: List[str] = []
    status = str(manifest_entry.get("status", ""))
    if status and not is_managed_parallel_entry(name, manifest_entry):
        reasons.append("manifest_status_unmanaged")

    manifest_bin = str(manifest_entry.get("bin", "")).strip()
    manifest_scripts = str(manifest_entry.get("scripts", "")).strip()

    if not manifest_bin:
        reasons.append("manifest_bin_missing")
    elif manifest_bin not in bin_files:
        reasons.append("manifest_bin_mismatch")

    if not manifest_scripts:
        reasons.append("manifest_scripts_missing")
    elif manifest_scripts not in script_files:
        reasons.append("manifest_scripts_mismatch")

    return reasons


def analyze_parallel_manifest_gaps(
    duplicates: Dict[str, List[str]],
    parallel_manifest: Dict[str, dict[str, object]],
) -> tuple[List[Dict[str, object]], List[Dict[str, object]], int]:
    parallel_candidates: List[Dict[str, object]] = []
    manifest_gaps: List[Dict[str, object]] = []
    unmanaged_count = 0

    for name, files in sorted(duplicates.items()):
        bin_files = [f for f in files if f.startswith("bin/") and f.split("/")[1:] and not _is_archive_path((ROOT / f).resolve())]
        script_files = [f for f in files if f.startswith("scripts/bin/") and f.split("/")[2:] and not _is_archive_path((ROOT / f).resolve())]
        if not bin_files or not script_files:
            continue
        if not active_duplicate_files(bin_files + script_files):
            continue

        manifest_entry = parallel_manifest.get(name)
        managed = is_managed_parallel_entry(name, manifest_entry)
        if not managed:
            unmanaged_count += 1

        reasons = _parallel_gap_reasons(name, bin_files, script_files, manifest_entry)
        candidate = {
            "name": name,
            "bin_files": sorted(bin_files),
            "scripts_files": sorted(script_files),
            "managed": managed,
            "status": manifest_entry.get("status") if manifest_entry else "missing",
            "parallel_entry": manifest_entry,
            "gap_reasons": reasons,
        }
        if manifest_entry is not None:
            candidate["parallel_entry"] = manifest_entry
        parallel_candidates.append(candidate)

        if reasons:
            manifest_gaps.append(
                {
                    "name": name,
                    "status": candidate["status"],
                    "managed": managed,
                    "bin_files": sorted(bin_files),
                    "scripts_files": sorted(script_files),
                    "gap_reasons": reasons,
                }
            )

    return parallel_candidates, manifest_gaps, unmanaged_count


def mark_cross_tree_mirror_shims(
    duplicates: Dict[str, List[str]],
    roles: Dict[str, str],
    signatures: Dict[str, str],
    parallel_manifest: Dict[str, dict[str, object]],
) -> tuple[Dict[str, str], List[str], int]:
    mirrored: List[str] = []
    adjusted = 0
    for name, files in duplicates.items():
        manifest_entry = parallel_manifest.get(name)
        if manifest_entry and is_managed_parallel_entry(name, manifest_entry) and is_compatible_shim_policy(manifest_entry):
            script_files = [f for f in files if f.startswith("scripts/bin/")]
            if not script_files:
                continue
            for f in script_files:
                if roles.get(f) == "archive":
                    continue
                if roles.get(f) != "shim":
                    roles[f] = "shim"
                    adjusted += 1
            mirrored.append(name)
            continue
        sig_groups: Dict[str, List[str]] = defaultdict(list)
        for rel in files:
            sig = signatures.get(rel)
            if sig:
                sig_groups[sig].append(rel)
        for rels in sig_groups.values():
            if len(rels) < 2:
                continue
            script_files = [f for f in rels if f.startswith("scripts/bin/")]
            bin_files = [f for f in rels if f.startswith("bin/")]
            if not script_files or not bin_files:
                continue
            # 同名脚本在 bin 与 scripts 同步复制时，默认保留 bin 为主动实现，scripts 标为 shim。
            for f in script_files:
                if roles.get(f) == "archive":
                    continue
                if roles.get(f) != "shim":
                    roles[f] = "shim"
                    adjusted += 1
            mirrored.append(name)
    # 去重，保留每个重复名一次
    return roles, sorted(set(mirrored)), adjusted


def classify_duplication_conflicts(
    duplicates: Dict[str, List[str]],
    roles: Dict[str, str],
    parallel_manifest: Dict[str, dict[str, object]],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    high_conflicts: List[Dict[str, object]] = []
    managed_high_conflicts: List[Dict[str, object]] = []
    unmanaged_high_conflicts: List[Dict[str, object]] = []
    for name, files in sorted(duplicates.items()):
        active_files = active_duplicate_files(files)
        if len(active_files) < 2:
            continue
        impl_files = [f for f in active_files if roles.get(f) == "implementation"]
        if len(impl_files) <= 1:
            continue
        active_exts = {Path(file).suffix.lower() for file in active_files}
        if len(active_exts) > 1 and len(active_files) == 2:
            continue
        high_conflicts.append(
            {
                "name": name,
                "active_files": sorted(active_files),
                "roles": {file: roles.get(file, "implementation") for file in active_files},
                "exts": sorted(active_exts),
                "file_count": len(active_files),
                "parallel_entry": parallel_manifest.get(name),
                "managed": is_managed_parallel_entry(name, parallel_manifest.get(name)),
            }
        )
        if is_managed_parallel_entry(name, parallel_manifest.get(name)):
            managed_high_conflicts.append(high_conflicts[-1])
        else:
            unmanaged_high_conflicts.append(high_conflicts[-1])
    return managed_high_conflicts, unmanaged_high_conflicts, high_conflicts


def summarize(paths: List[Path], parallel_manifest: Dict[str, dict[str, object]]) -> Dict:
    types: Counter[str] = Counter()
    duplicates: defaultdict[str, List[str]] = defaultdict(list)
    roles: Dict[str, str] = {}
    signatures: Dict[str, str] = {}
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
        roles[rel] = script_role(path)
        signatures[rel] = file_signature(path)
        if not snake_case(Path(name).stem):
            non_snake.append(rel)

    duplicated = {
        name: files for name, files in duplicates.items() if len(files) > 1
    }
    duplicate_scopes = {name: sorted(files) for name, files in duplicated.items()}
    roles, mirrored_script_duplicates, mirror_adjustments = mark_cross_tree_mirror_shims(
        duplicated, roles, signatures, parallel_manifest
    )
    parallel_candidates, manifest_gaps, unmanaged_parallel = analyze_parallel_manifest_gaps(
        duplicated, parallel_manifest
    )
    managed_duplicates, unmanaged_duplicates, duplicate_conflicts = classify_duplication_conflicts(
        duplicated, roles, parallel_manifest
    )
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
            "managed_parallel_duplicates": len(managed_duplicates),
            "unmanaged_parallel_duplicates": len(unmanaged_duplicates),
            "parallel_candidates": len(parallel_candidates),
            "parallel_manifest_gaps": len(manifest_gaps),
            "unmanaged_parallel_candidates": unmanaged_parallel,
            "mirrored_script_duplicates": len(mirrored_script_duplicates),
            "mirror_adjustments": mirror_adjustments,
            "edges": sum(out_degree.values()),
            "shim_count": sum(1 for role in roles.values() if role == "shim"),
            "archive_count": sum(1 for role in roles.values() if role == "archive"),
            "doc_count": sum(1 for role in roles.values() if role == "doc"),
        },
        "findings": {
            "missing_shebang": sorted(missing_shebang),
            "non_snake": sorted(non_snake),
            "duplicate_names": duplicate_scopes,
            "mirrored_script_duplicates": mirrored_script_duplicates,
            "managed_parallel_duplicates": managed_duplicates,
            "unmanaged_parallel_duplicates": unmanaged_duplicates,
            "parallel_candidates": parallel_candidates,
            "parallel_manifest_gaps": manifest_gaps,
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
    if summary["stats"]["unmanaged_parallel_duplicates"] > 0:
        errors.append(
            f"unmanaged high-confidence duplicate normalized script names: {summary['stats']['unmanaged_parallel_duplicates']}"
        )
    if summary["findings"]["cycles"]:
        errors.append(f"script cycle detected: {len(summary['findings']['cycles'])}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="artifacts/bin-tool-registry-audit.json")
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--parallel-manifest",
        default=str(DEFAULT_PARALLEL_MANIFEST),
        help="manage duplicate policy for bin/scripts parity",
    )
    parser.add_argument(
        "--scope",
        choices=("bin", "scripts", "both"),
        default="bin",
        help="scan directory scope: bin, scripts, or both",
    )
    args = parser.parse_args()

    files = list_bin_files(args.scope)
    payload = summarize(files, load_parallel_manifest(Path(args.parallel_manifest)))
    payload["snapshot"] = str((ROOT / args.snapshot).resolve())
    strict_errors: List[str] = []
    if args.strict:
        strict_errors = strict_checks(payload)
        payload["strict"] = {"enabled": True, "passed": not bool(strict_errors), "errors": strict_errors}
    else:
        payload["strict"] = {"enabled": False, "passed": True, "errors": []}
    if args.emit:
        emit_json(ROOT / args.snapshot, payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2 if args.strict and strict_errors else 0

    print("== Bin Tool Registry Audit ==")
    print(f"total: {payload['stats']['total_scripts']}")
    print(f"by type: {payload['stats']['by_type']}")
    print(f"missing shebang: {payload['stats']['missing_shebang']}")
    print(f"non-snake: {payload['stats']['non_snake']}")
    print(f"duplicate names: {payload['stats']['duplicate_names']}")
    print(f"high-confidence duplicate names: {payload['stats']['high_conflict_duplicates']}")
    print(f"parallel candidates (bin/scripts overlap): {payload['stats']['parallel_candidates']}")
    print(f"parallel manifest gaps: {payload['stats']['parallel_manifest_gaps']}")
    print(f"managed parallel duplicates: {payload['stats']['managed_parallel_duplicates']}")
    print(f"unmanaged parallel duplicates: {payload['stats']['unmanaged_parallel_duplicates']}")
    print(
        "mirrored script duplicates: "
        f"{payload['stats']['mirrored_script_duplicates']} "
        f"(roles adjusted: {payload['stats']['mirror_adjustments']})"
    )
    print(f"cycles: {len(payload['findings']['cycles'])}")
    print(
        "shim / archive / doc: "
        f"{payload['stats']['shim_count']} / {payload['stats']['archive_count']} / {payload['stats']['doc_count']}"
    )
    print("top out-degree:", payload["top_out_degree"][:3])
    print("top in-degree:", payload["top_in_degree"][:3])
    if args.strict:
        if strict_errors:
            print("STRICT FAIL:")
            for item in strict_errors:
                print(f" - {item}")
            return 2
        print("strict checks: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
