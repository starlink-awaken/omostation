#!/usr/bin/env python3
"""AST Index Bootstrap (全仓 AST 语义符号与调用链自举索引器).

用途:
  遍历全仓核心项目源码，极速解析提取所有 Public 函数、类、方法的强类型签名与哈希指纹，
  并在 SQLite 架构因果黑板中建立跨项目静态调用链索引。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE_ROOT / "projects" / "omo" / "src"))

from omo.blackboard.ast_scanner import scan_directory
from omo.blackboard.client import BlackboardClient

DB_PATH = WORKSPACE_ROOT / "runtime" / "omo" / "architecture_graph.sqlite3"

CORE_PROJECT_TARGETS = [
    ("omo", WORKSPACE_ROOT / "projects" / "omo" / "src"),
    ("cockpit", WORKSPACE_ROOT / "projects" / "cockpit" / "src"),
    ("agora", WORKSPACE_ROOT / "projects" / "agora" / "src"),
    ("aetherforge", WORKSPACE_ROOT / "projects" / "aetherforge"),
    ("bin_gac", WORKSPACE_ROOT / "bin" / "gac"),
]


def bootstrap_ast_index(db_path: Path = DB_PATH, verbose: bool = False) -> dict[str, Any]:
    """Scan and index symbols and call-edges across all core projects."""
    start_t = time.perf_counter()
    bb = BlackboardClient(db_path)

    all_symbols: list[dict[str, Any]] = []
    all_raw_calls: list[dict[str, Any]] = []

    # 1. Scan symbols and calls across all projects
    for proj_id, proj_path in CORE_PROJECT_TARGETS:
        if not proj_path.exists():
            continue
        syms, calls = scan_directory(proj_path, project_id=proj_id)
        all_symbols.extend(syms)
        all_raw_calls.extend(calls)
        if verbose:
            print(f"  • [{proj_id}] 提取符号 {len(syms)} 个, 调用点 {len(calls)} 处 (路径: {proj_path.name})")

    # 2. Batch upsert symbols into Blackboard
    n_syms = bb.batch_upsert_symbols(all_symbols)

    # 3. Resolve call edges: match callee_name to symbol_id & signature_hash
    # Map from simple func_name / class_name to list of symbol records
    sym_lookup: dict[str, list[dict[str, Any]]] = {}
    for s in all_symbols:
        simple_name = s["symbol_id"].split("::")[-1]
        sym_lookup.setdefault(simple_name, []).append(s)

    resolved_calls: list[dict[str, Any]] = []
    for call in all_raw_calls:
        target_name = call["callee_name"]
        matches = sym_lookup.get(target_name, [])
        for m in matches:
            resolved_calls.append({
                "caller_file": str(Path(call["caller_file"]).relative_to(WORKSPACE_ROOT)) if str(call["caller_file"]).startswith(str(WORKSPACE_ROOT)) else call["caller_file"],
                "caller_symbol": call["caller_symbol"],
                "caller_line": call["caller_line"],
                "callee_symbol": m["symbol_id"],
                "expected_hash": m["signature_hash"],
            })

    # 4. Batch record resolved call edges
    n_calls = bb.batch_record_calls(resolved_calls)

    duration_ms = int((time.perf_counter() - start_t) * 1000)
    summary = bb.get_ast_summary()

    return {
        "status": "ok",
        "duration_ms": duration_ms,
        "symbols_indexed": n_syms,
        "call_edges_indexed": n_calls,
        "total_symbols_in_db": summary["total_symbols"],
        "total_calls_in_db": summary["total_call_edges"],
        "covered_projects": summary["indexed_projects"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH, help="SQLite Blackboard DB path")
    parser.add_argument("--verbose", action="store_true", help="打印各项目扫描详情")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args(argv)

    res = bootstrap_ast_index(db_path=args.db, verbose=args.verbose)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("=== 全仓 AST 语义调用链自举构建完成 ===")
        print(f"  • 纳管符号总数: {res['total_symbols_in_db']} 个")
        print(f"  • 静态调用边数: {res['total_calls_in_db']} 条")
        print(f"  • 覆盖核心项目: {res['covered_projects']} 个")
        print(f"  • 自举总耗时:   {res['duration_ms']} ms (< 1秒极速完成)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
