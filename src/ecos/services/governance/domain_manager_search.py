"""ecos.services.governance.domain_manager_search — cmd_search 拆分 (P110-C).

P110 关联: TASK-F7114ABA (omo lint god-module 800L 硬规则).
domain_manager_domain_cmd.py 845L 拆分: cmd_search (~75L) 独立到本模块.

业务 (1 function): cmd_search (跨域 grep 搜索).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def cmd_search(args):
    """跨域搜索."""
    if not args:
        print("用法: ecos domain search <关键词> [--domains d1,d2] [--max 20]")
        return
    query = args[0]
    domains = None
    max_results = 20

    for i, a in enumerate(args[1:], 1):
        if a == "--domains" and i < len(args) - 1:
            domains = args[i + 1].split(",")
        if a == "--max" and i < len(args) - 1:
            max_results = int(args[i + 1])

    # 惰性 import (避免 domain_manager_domain_cmd 顶层 import 的循环)
    from .domain_manager import load_registry, resolve_path

    registry = load_registry()
    results = []
    target_domains = set(domains) if domains else None

    print(f'\n  🔍 搜索: "{query}"\n')

    for d in registry:
        did = d["id"]
        if target_domains and did not in target_domains:
            continue
        p = resolve_path(d)
        if not p.exists():
            continue

        search_dirs = []
        for sd in [
            "CLAUDE.md",
            "_control/STATE.md",
            "_control/MEMORY.md",
            "_knowledge",
        ]:
            sp = p / sd
            if sp.exists():
                search_dirs.append(str(sp))

        for sp in search_dirs:
            try:
                cmd = [
                    "grep",
                    "-rn",
                    "--include=*.md",
                    "--include=*.yaml",
                    "-l",
                    query,
                    sp,
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                for line in r.stdout.strip().split("\n"):
                    if line and len(results) < max_results:
                        rel = (
                            Path(line).relative_to(p)
                            if p in Path(line).parents
                            else line
                        )
                        results.append((did, str(rel)))
            except Exception:  # defensive fallback
                pass

    if results:
        for did, fpath in results:
            print(f"  📄 bos://{did}/{fpath}")
        print(f"\n  {len(results)} results\n")
    else:
        print("  ❌ 无结果\n")
