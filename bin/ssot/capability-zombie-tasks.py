#!/usr/bin/env python3
"""僵尸能力 → 治理待办闭环 (方向 A).

读取 agora 能力目录的有效状态 (capability_catalog.get: active 声明但超 stale_days
零调用 → zombie), 为每个僵尸能力生成/创建 omo 治理待办 (task_type=remediation),
驱动人工 review (移除/归档/恢复), 而非静默拦截。

用法:
    capability-zombie-tasks.py                    # dry-run: 列出僵尸能力 + 将创建的待办
    capability-zombie-tasks.py --apply            # 实际创建 omo 治理待办 (幂等)
    capability-zombie-tasks.py --stale-days 14    # 自定义僵尸阈值
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def _load_capability_catalog(root: Path):
    """importlib 加载 agora capability_catalog (不依赖 agora 安装)。"""
    agora_src = root / "projects/agora/src"
    catalog_path = agora_src / "agora/mcp/capability_catalog.py"
    if not catalog_path.exists():
        return None
    # 把 agora src 加入 sys.path, 使 get() 内部 from agora.mcp import bos_metrics 可解析
    sys.path.insert(0, str(agora_src))
    spec = importlib.util.spec_from_file_location(
        "agora_capability_catalog_projection", catalog_path
    )
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.CapabilityCatalog()


def _list_zombies(catalog, stale_days: float) -> list[dict]:
    """遍历能力声明, 用 get() 有效状态判定真僵尸 (zombie=true)。"""
    caps = catalog.load()
    zombies = []
    for uri in sorted(caps):
        effective = catalog.get(uri, stale_days=stale_days)
        if effective and effective.get("zombie"):
            zombies.append(
                {
                    "uri": uri,
                    "description": effective.get("description", ""),
                    "status": effective.get("status"),
                    "stale_days": effective.get("stale_days"),
                    "calls": effective.get("calls", 0),
                }
            )
    return zombies


def _task_title(zombie: dict) -> str:
    cap = zombie["uri"].replace("bos://", "").replace("/", ":")
    return f"REMEDIATE-ZOMBIE-{cap}"


def _task_body(zombie: dict, stale_days: float) -> str:
    return (
        f"僵尸能力 review (B2 语义路由已拦截): {zombie['uri']}\n"
        f"- 声明状态: {zombie['status']}\n"
        f"- 最近调用: {zombie['calls']} (超 {stale_days} 天零调用)\n"
        f"- 描述: {zombie['description'][:120]}\n"
        f"决策: 移除 / 归档 / 恢复 (从 etc/bos-services.yaml 调整后重新观察)。"
    )


def _create_omo_task(root: Path, zombie: dict, stale_days: float) -> tuple[str, int]:
    """调用 omo task create 创建治理待办。返回 (task_id, exit_code)。"""
    title = _task_title(zombie)
    body = _task_body(zombie, stale_days)
    cmd = [
        sys.executable, "-m", "omo.cli", "task", "create",
        "--title", title,
        "--desc", body,
        "--priority", "medium",
        "--task-type", "remediation",
        "--risk-level", "L1",
        "--source-doc", "bin/ssot/capability-zombie-tasks.py",
        "--test-plan", f"验证 {zombie['uri']} 不再被路由 (deprecated 拦截)",
        "--deliverable", f"{zombie['uri']} 处置决策记录",
        "--evidence-required", f"{zombie['uri']} 使用度量复查记录",
    ]
    # omo 是子模块: 把 projects/omo/src 加入 PYTHONPATH 使 omo.cli 可 import
    env = os.environ.copy()
    omo_src = str(root / "projects/omo/src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{omo_src}{os.pathsep}{existing}" if existing else omo_src
    result = subprocess.run(
        cmd, cwd=root, capture_output=True, text=True, timeout=60, check=False,
        env=env,
    )
    task_id = ""
    for line in result.stdout.splitlines():
        if "TASK-" in line or "IMPORTED-" in line:
            for token in line.split():
                if token.startswith(("TASK-", "IMPORTED-")):
                    task_id = token
                    break
    return task_id, result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="实际创建治理待办 (默认 dry-run)")
    parser.add_argument("--stale-days", type=float, default=7.0, help="僵尸判定阈值")
    parser.add_argument("--root", type=Path, default=WORKSPACE)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    catalog = _load_capability_catalog(root)
    if catalog is None:
        print("capability-zombie-tasks: agora capability_catalog 不可用", file=sys.stderr)
        return 2

    zombies = _list_zombies(catalog, args.stale_days)
    if not zombies:
        print(f"✅ 无僵尸能力 (stale_days={args.stale_days})")
        return 0

    print(f"⚠ 发现 {len(zombies)} 个僵尸能力:")
    for z in zombies:
        print(f"  - {z['uri']} (calls={z['calls']}, stale={z['stale_days']}d)")

    if not args.apply:
        print(f"\n(dry-run) 将创建 {len(zombies)} 个治理待办, 加 --apply 实际创建")
        return 0

    created = 0
    for z in zombies:
        task_id, rc = _create_omo_task(root, z, args.stale_days)
        if rc == 0:
            created += 1
            print(f"  ✅ 创建待办: {task_id or '?'} → {z['uri']}")
        else:
            print(f"  ❌ 创建失败 (exit {rc}): {z['uri']}")
    print(f"\n完成: 创建 {created}/{len(zombies)} 个治理待办")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
