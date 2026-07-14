#!/usr/bin/env python3
"""gen-dependency-baseline: 扫描 projects/**/pyproject.toml 检测 dependency-baseline drift.

治本 (ISC-15): dependency-baseline.yaml 此前纯手工维护, 无生成器, 无 drift 检测
(元根因 1: 声明式 SSOT 无生成器). pyproject 加了依赖 (如 graphiti-core/semantica/mem0ai)
没人同步更新 baseline → baseline (none) 与 pyproject 实际下限不一致 (C1 债务).

本生成器:
  1. 扫 projects/**/pyproject.toml (含 kairon/aetherforge 子包)
  2. 收集 workspace project name (排除内部依赖, 如 agora/omo/aetherforge-gateway)
  3. 解析每个 pyproject 的 [project.dependencies] + [project.optional-dependencies]
  4. 聚合外部依赖: name → [(consumer, lower_bound, extras), ...]
  5. --check: 对比 runtime/omo/_truth/registry/dependency-baseline.yaml 报三类 drift
  6. --dry-run: 打印从 pyproject 推导出的 baseline

drift 类型:
  MISSING      — pyproject 有但 baseline 未登记 (新增依赖未同步)
  STALE        — baseline 有但 pyproject 无 (依赖已移除, baseline 未清)
  UNCONSTRAINED— baseline 标 (none) 但 pyproject 实际有下限 (C1 实证: graphiti/semantica/mem0ai)

注: --write 不在此工具 (写 _truth/ 属 .omo/ 治理面, 走 omo broker).
    本工具做"生成 + drift 检测", 写入由 broker 流程消费 --dry-run 输出.

用法:
  python bin/gen-dependency-baseline.py --check       # 报 drift, 有 drift exit 1 (CI 友好)
  python bin/gen-dependency-baseline.py --dry-run     # 打印推导 baseline
"""
from __future__ import annotations

import argparse
import re
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
# P0-fix (2026-07-02): baseline SSOT 回 .omo (tracked), 跟 omo broker 写入路径一致
# (find_omo_dir → OMO_ROOT/.omo, apply_baseline_patches 写 omo_dir/_truth/registry/).
# PR#4 半吊子迁移把 baseline 搬到 runtime/omo (gitignored) → CI 拿不到 → 52 drift.
# runtime/omo 是 volatile mirror, 不是 SSOT; baseline 是 SSOT 该 tracked.
BASELINE_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "dependency-baseline.yaml"

# PEP 508 简化解析: name[extras]op version, op version, ...
# 例: "graphiti-core[neo4j]>=0.28", "mem0ai", "httpx[socks]>=0.28.1,<1.0"
_REQ_RE = re.compile(
    r"^\s*"
    r"(?P<name>[a-zA-Z0-9][a-zA-Z0-9._-]*)"            # 包名
    r"(?:\[(?P<extras>[a-zA-Z0-9,_-]+)\])?"            # [extra1,extra2]
    r"(?P<spec>.*)$"                                    # version spec rest
)
_LOWER_RE = re.compile(r">=\s*(?P<v>[0-9][0-9a-zA-Z._-]*)")


def _parse_require(req: str) -> tuple[str, str | None, list[str]] | None:
    """解析单条依赖 → (name, lower_bound_or_None, extras_list). None = 不可解析."""
    m = _REQ_RE.match(req)
    if not m:
        return None
    name = m.group("name").lower()
    extras = (m.group("extras") or "").split(",") if m.group("extras") else []
    extras = [e.strip() for e in extras if e.strip()]
    spec = (m.group("spec") or "").strip()
    lower = None
    if spec:
        lm = _LOWER_RE.search(spec)
        if lm:
            lower = lm.group("v")
    return (name, lower, extras)


def _consumer_label(pyproject: Path, group: str) -> str:
    """consumer 标签: project name [+ extra/group 标记]."""
    rel = pyproject.relative_to(WORKSPACE)
    parts = rel.parts
    # projects/<proj>/pyproject.toml → <proj>; projects/<proj>/packages/<pkg>/pyproject.toml → <pkg>
    proj = parts[1] if len(parts) > 1 else "unknown"
    label = proj
    if len(parts) > 3 and parts[2] == "packages":
        label = parts[3]  # 子包名
    if group != "main":
        label += f"[{group}]"
    return label


def collect_dependencies() -> dict[str, list[tuple[str, str | None, list[str]]]]:
    """扫所有 pyproject, 返回 {dep_name: [(consumer, lower, extras), ...]} (仅外部依赖)."""
    # simplify 治本: 一次 glob 同时收集 workspace names + proj dict (省第二次 glob I/O)
    parsed_projects: list[tuple[Path, dict]] = []
    workspace_names: set[str] = set()
    for p in sorted(WORKSPACE.glob("projects/**/pyproject.toml")):
        try:
            with p.open("rb") as f:
                data = tomllib.load(f)
        except Exception:  # noqa: BLE001
            continue
        proj = data.get("project") or {}
        name = proj.get("name")
        if isinstance(name, str):
            workspace_names.add(name.lower())
        parsed_projects.append((p, proj))

    deps: dict[str, list[tuple[str, str | None, list[str]]]] = defaultdict(list)
    for p, proj in parsed_projects:
        # [project.dependencies] → group="main"
        for req in proj.get("dependencies") or []:
            parsed = _parse_require(str(req))
            if not parsed:
                continue
            name, lower, extras = parsed
            if name in workspace_names:
                continue  # 排除 workspace 内部依赖
            deps[name].append((_consumer_label(p, "main"), lower, extras))

        # [project.optional-dependencies.<group>]
        for group, reqs in (proj.get("optional-dependencies") or {}).items():
            for req in reqs:
                parsed = _parse_require(str(req))
                if not parsed:
                    continue
                name, lower, extras = parsed
                if name in workspace_names:
                    continue
                deps[name].append((_consumer_label(p, group), lower, extras))
    return deps


def derive_baseline(deps: dict) -> dict[str, dict]:
    """从聚合的 deps 推导 baseline: 每个 dep 的最严格下限 (max of lowers) + consumers."""
    baseline: dict[str, dict] = {}
    for name, entries in sorted(deps.items()):
        consumers = sorted({e[0] for e in entries})
        lowers = [e[1] for e in entries if e[1]]
        # baseline 下限 = 所有 consumer 下限中最高的 (max lower bound = 大家都能接受的下限)
        # version 比较简化: 按字符串排序可能不准, 但 ISC-15 v1 够用 (drift 检测优先)
        chosen = max(lowers) if lowers else None
        baseline[name] = {
            "baseline": f">={chosen}" if chosen else "(none)",
            "consumers": consumers,
            "consumer_count": len(consumers),
        }
    return baseline


def _load_current_baseline() -> dict[str, str]:
    """加载现有 baseline 的 name → baseline-string 映射 (轻量正则提取, 不全解析 yaml)."""
    if not BASELINE_YAML.is_file():
        return {}
    text = BASELINE_YAML.read_text(encoding="utf-8")
    current: dict[str, str] = {}
    # 匹配 `    - name: xxx` + 后续 `      baseline: yyy`
    name_re = re.compile(r"^\s{4}-\s*name:\s*([^\s]+)", re.MULTILINE)
    baseline_re = re.compile(r"^\s{6}baseline:\s*'?([^'\n]+)'?", re.MULTILINE)
    names = name_re.findall(text)
    baselines = baseline_re.findall(text)
    # 配对: name 和 baseline 在 yaml 里交替 (name 后紧跟 baseline)
    for i, n in enumerate(names):
        b = baselines[i] if i < len(baselines) else ""
        current[n.lower()] = b.strip().strip("'\"")
    return current


def check_drift(derived: dict, current: dict) -> dict:
    """对比 derived baseline 与 current, 返回三类 drift."""
    missing = []     # pyproject 有, baseline 无
    stale = []       # baseline 有, pyproject 无
    unconstrained = []  # baseline (none) 但 pyproject 有下限
    mismatched = []  # baseline 下限与 pyproject 推导不一致

    for name, info in derived.items():
        if name not in current:
            missing.append({"name": name, "consumers": info["consumer_count"], "derived_baseline": info["baseline"]})
        else:
            cur = current[name]
            if cur == "(none)" and info["baseline"] != "(none)":
                unconstrained.append({"name": name, "current": cur, "pyproject_lower": info["baseline"], "consumers": info["consumers"]})
            elif cur != "(none)" and info["baseline"] != "(none)" and cur != info["baseline"]:
                mismatched.append({"name": name, "current": cur, "derived": info["baseline"]})

    for name, cur in current.items():
        if name not in derived:
            stale.append({"name": name, "current": cur})

    return {"missing": missing, "stale": stale, "unconstrained": unconstrained, "mismatched": mismatched}


def main() -> int:
    parser = argparse.ArgumentParser(description="gen-dependency-baseline: dependency drift 检测 (ISC-15)")
    parser.add_argument("--check", action="store_true", help="对比 baseline 报 drift (exit 1 有 drift)")
    parser.add_argument("--dry-run", action="store_true", help="打印从 pyproject 推导的 baseline")
    parser.add_argument("--write", action="store_true", help="patch mismatched/unconstrained baseline → derived, 走 omo broker (C2 方案 C: subprocess 调 omo, 不直写)")
    parser.add_argument("--direct-write", action="store_true", help="直接写入 baseline YAML (不走 omo broker, 用于 worktree submit / CI 自动修复)")
    args = parser.parse_args()

    if not args.check and not args.dry_run and not args.write and not args.direct_write:
        parser.print_help()
        return 1

    deps = collect_dependencies()
    derived = derive_baseline(deps)

    if args.dry_run:
        print(f"# 治本 ISC-15: 从 {len(deps)} 个外部依赖推导的 baseline (源: projects/**/pyproject.toml)")
        print("# 注: --write 走 omo broker (C2 方案 C: subprocess 调 omo baseline write, 不直写)")
        print()
        for name, info in derived.items():
            consumers = ", ".join(info["consumers"][:5])
            more = f" (+{info['consumer_count']-5})" if info["consumer_count"] > 5 else ""
            print(f"  {name:<28} baseline={info['baseline']:<12} consumers=[{consumers}{more}]")
        print(f"\n📊 共 {len(derived)} 个外部依赖")
        return 0

    if args.write:
        # C2 方案 C (2026-07-01): subprocess 调 omo broker 写 baseline (不直写, 避 direct_omo_io 红线).
        # omo src/omo/ 路径豁免 contract_gatekeeper. 跟 omo_readiness (P63) 先例同构 (gen 算 → omo broker 写).
        import json
        import os
        import subprocess

        current = _load_current_baseline()
        drift = check_drift(derived, current)
        targets = {
            d["name"]: (d.get("derived") or d.get("pyproject_lower") or d.get("derived_baseline"))
            for d in (drift["mismatched"] + drift["unconstrained"] + drift.get("missing", []))
        }
        targets = {k: v for k, v in targets.items() if v and v != "(none)"}
        if not targets:
            print(f"✅ 无 mismatched/unconstrained drift, 无需写入 ({len(derived)} deps)")
            return 0
        patches_json = json.dumps(targets, ensure_ascii=False)
        omo_python = WORKSPACE / "projects" / "omo" / ".venv" / "bin" / "python"
        omo_src = WORKSPACE / "projects" / "omo" / "src"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(omo_src)
        cmd = [
            str(omo_python), "-m", "omo.cli", "baseline", "write",
            "--patches", patches_json,
            "--actor", "gen-dependency-baseline",
        ]
        print(f"📡 gen --write: 调 omo broker patch {len(targets)} 项 baseline (不直写, 走 broker 合规)")
        for name, new_b in targets.items():
            print(f"   ⬆ {name}: → {new_b}")
        result = subprocess.run(cmd, cwd=str(WORKSPACE / "projects" / "omo"), env=env, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout, end="")
        if result.returncode != 0:
            print(f"❌ omo baseline write 失败 (rc={result.returncode}):\n{result.stderr}", file=sys.stderr)
            return result.returncode
        return 0

    if args.direct_write:
        # 直接写入 baseline YAML, 不走 omo broker.
        # 用于 worktree submit / CI 自动修复 (omo venv 不可用时).
        import re
        BASELINE_FILE = WORKSPACE / ".omo" / "_truth" / "registry" / "dependency-baseline.yaml"
        current = _load_current_baseline()
        drift = check_drift(derived, current)
        total = sum(len(v) for v in drift.values())
        if total == 0:
            print(f"✅ dependency-baseline 无 drift ({len(derived)} deps 全部对齐)")
            return 0

        print(f"⚡ --direct-write: 修复 {total} 项 drift (直接写 YAML, 不走 omo broker)")
        content = BASELINE_FILE.read_text()

        # 1. 移除 STALE 条目 (baseline 有但 pyproject 无) — 行级精确匹配
        for d in drift.get("stale", []):
            name = d["name"]
            lines = content.split("\n")
            new_lines = []
            skip = False
            for line in lines:
                if re.match(rf"^    - name: {re.escape(name)}$", line):
                    skip = True
                    print(f"   🗑 移除 stale: {name}")
                    continue
                if skip and re.match(r"^    - name:", line):
                    skip = False
                if not skip:
                    new_lines.append(line)
            content = "\n".join(new_lines)

        # 2. 添加 MISSING 条目 (pyproject 有但 baseline 无) — 按字母序插入
        for d in drift.get("missing", []):
            name = d["name"]
            baseline = d["derived_baseline"]
            entry_lines = [
                f"    - name: {name}",
                f"      baseline: '{baseline}'",
                f"      reason: 'Consumed by {d['consumers']} project(s)'",
                f"      consumers:",
                f"        - (auto-detected)",
            ]
            lines = content.split("\n")
            insert_idx = None
            for i, line in enumerate(lines):
                m = re.match(r"    - name: (.+)$", line)
                if m and m.group(1) > name:
                    insert_idx = i
                    break
            if insert_idx is not None:
                for j, el in enumerate(entry_lines):
                    lines.insert(insert_idx + j, el)
                content = "\n".join(lines)
                print(f"   ➕ 添加 missing: {name} ({baseline})")
            else:
                for i, line in enumerate(lines):
                    if line.strip() == "dev_test:":
                        for j, el in enumerate(entry_lines):
                            lines.insert(i + j, el)
                        break
                content = "\n".join(lines)
                print(f"   ➕ 添加 missing: {name} ({baseline})")

        # 3. 修复 MISMATCHED/UNCONSTRAINED
        for d in drift.get("mismatched", []) + drift.get("unconstrained", []):
            name = d["name"]
            new_baseline = d.get("derived") or d.get("pyproject_lower")
            pattern = rf"    - name: {re.escape(name)}\n      baseline: '[^']*'"
            replacement = f"    - name: {name}\n      baseline: '{new_baseline}'"
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                print(f"   🔧 修复: {name} → {new_baseline}")
                content = new_content

        BASELINE_FILE.write_text(content)
        print(f"✅ 已写入 {BASELINE_FILE.relative_to(WORKSPACE)}")
        return 0

    if args.check:
        current = _load_current_baseline()
        drift = check_drift(derived, current)
        total = sum(len(v) for v in drift.values())
        if total == 0:
            print(f"✅ dependency-baseline 无 drift ({len(derived)} deps 全部对齐)")
            return 0

        print(f"❌ 检测到 {total} 项 dependency-baseline drift:\n")
        if drift["unconstrained"]:
            print(f"  ⚠️  UNCONSTRAINED ({len(drift['unconstrained'])}): baseline (none) 但 pyproject 有下限 (C1 实证)")
            for d in drift["unconstrained"]:
                print(f"     - {d['name']}: baseline={d['current']} → pyproject={d['pyproject_lower']} ({d['consumers']} consumers)")
        if drift["missing"]:
            print(f"  ⚠️  MISSING ({len(drift['missing'])}): pyproject 有但 baseline 未登记")
            for d in drift["missing"][:10]:
                print(f"     - {d['name']} (consumers={d['consumers']}, derived={d['derived_baseline']})")
            if len(drift["missing"]) > 10:
                print(f"     ... 及其他 {len(drift['missing'])-10} 项")
        if drift["stale"]:
            print(f"  ⚠️  STALE ({len(drift['stale'])}): baseline 有但 pyproject 无 (依赖已移除)")
            for d in drift["stale"][:10]:
                print(f"     - {d['name']} (baseline={d['current']})")
        if drift["mismatched"]:
            print(f"  ⚠️  MISMATCHED ({len(drift['mismatched'])}): baseline 与 pyproject 下限不一致")
            for d in drift["mismatched"][:10]:
                print(f"     - {d['name']}: baseline={d['current']} vs derived={d['derived']}")
        print("\n修复: python bin/gen-dependency-baseline.py --dry-run → 走 omo broker 写 .omo/_truth/registry/dependency-baseline.yaml")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
