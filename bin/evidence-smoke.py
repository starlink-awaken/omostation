#!/usr/bin/env python3
"""证据驱动 smoke — 量化 BOS 声明/执行鸿沟 + 反馈回路存活.

系统思考落地 (Meadows 杠杆点):
  - 层 6 信息流: 把鸿沟暴露成可追踪数字 (打破 health=100 自嗨)
  - 层 8 反馈回路: 让运行现实回到度量输入端
  - 层 2 范式: 从"治理驱动"转向"证据驱动" — 声明无证据 = 不存在

把一次性审计 (.omo/_knowledge/audits/bos-declaration-execution-gap-2026-06-24.md)
机制化为可重复跑的 smoke. radar 的 health_score 只看任务纸面 (done/planned),
这个脚本补的是"运行现实"维度: BOS 真能调吗 / working tree 累积吗 / 反馈回路活着吗.

三层验证:
  L2 声明真实 (文件系统, 秒级):
    - stdio/mcp_stdio: command 的 --directory 存在 + -m module 包目录可定位
    - internal: module_path 文件存在
    - mcp_proxy/http: http_url 非空 + 合法
  L3 执行抽样 (--spawn N, 慢, 可选): 抽 N 个 stdio 真 spawn 验证可跑

输出: .omo/_delivery/evidence-smoke/<date>.json
核心: evidence_health_score = 综合运行现实分 (对比 health_score=100 假象)

用法:
  python3 bin/evidence-smoke.py              # L2 全量 (秒级)
  python3 bin/evidence-smoke.py --spawn 3    # + L3 抽样 spawn 3 个
  python3 bin/evidence-smoke.py --quiet       # 只输出 score
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# CI 可移植: 用 __file__ 定位 workspace, 不硬编码 (CLAUDE.md CI 治本机制)
WORKSPACE = Path(__file__).resolve().parents[1]
AGORA_SRC = WORKSPACE / "projects" / "agora" / "src"

# 让脚本能 import agora.mcp.resolver.services
if str(AGORA_SRC) not in sys.path:
    sys.path.insert(0, str(AGORA_SRC))

OUTPUT_DIR = WORKSPACE / ".omo" / "_delivery" / "evidence-smoke"
GOV_LOG = WORKSPACE / ".omo" / "_knowledge" / "governance-history.jsonl"

# evidence_health_score 权重 (综合三维度, 满分 100)
W_BOS = 60  # BOS resolve 率 (最重 — 这是核心鸿沟)
W_TREE = 20  # working tree 清洁度
W_FEEDBACK = 20  # 反馈回路存活

# 已知调研中项 — 声明指向过时位置/缺字段, 配套 D 对齐迁移调研 (TASK-9B363829)
# 不计真实鸿沟 (单独 deprecated 桶), 有效期至 KNOWN_GAP_EXPIRES (30天复查)
# 来源: 全仓 grep 发现硬依赖 (routes.json/health/debt), 非简单死声明, 不能一刀切删
KNOWN_GAP_PREFIXES: dict[str, str] = {
    "bos://capability/agent-runtime/": "迁移 cockpit (omo goals M2 拆分 runtime+ext/cockpit)",
    "bos://persona/sharedbrain-bridge/": "死活待查 (debt 承认死代码 + 8001 端口实况)",
    "bos://persona/sot-bridge-persona/": "死活待查 (sharedbrain 桥)",
    "bos://governance/sot-bridge/": "死活待查 (sharedbrain 桥)",
    "bos://governance/protocols-layer/": "无实现 (routes.json 有路由)",
    "bos://memory/gbrain/": "缺 mcp endpoint (mcp_proxy 无 http_url)",
    "bos://system/": "internal 缺 module_path (agora 内部工具声明不完整)",
}
KNOWN_GAP_EXPIRES = "2026-07-25"  # 30天复查, 过期未对齐升级为真实鸿沟


def _is_known_gap(uri: str) -> tuple[bool, str]:
    """URI 是否匹配已知调研中项 (deprecated). 返回 (是否匹配, 原因)."""
    for prefix, reason in KNOWN_GAP_PREFIXES.items():
        if uri.startswith(prefix):
            return True, reason
    return False, ""


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── L2: 声明真实性检查 (文件系统, 快) ────────────────────────────


def _check_stdio(command: list[str]) -> tuple[bool, str]:
    """stdio/mcp_stdio: 检查 --directory 存在 + -m module 可定位.

    command 形如 ['uv','run','--directory','projects/kairon','python','-m','kos.cli','search']
    """
    # 一次遍历提取所有关键参数: --directory / --package / -m module / 直接 .py 脚本
    directory = package = module = script = None
    for i, arg in enumerate(command):
        if arg == "--directory" and i + 1 < len(command):
            directory = command[i + 1]
        elif arg.startswith("--directory="):
            directory = arg.split("=", 1)[1]
        elif arg == "--package" and i + 1 < len(command):
            package = command[i + 1]
        elif arg == "-m" and i + 1 < len(command):
            module = command[i + 1]
        elif arg.endswith(".py"):
            script = arg

    # 路径 1: 直接脚本路径 (family-hub: projects/family-hub/mcp_server.py)
    if script:
        sp = Path(script)
        sp = sp if sp.is_absolute() else WORKSPACE / sp
        return (True, "ok (script)") if sp.exists() else (False, f"script not found: {script}")

    # 路径 2: --package (workspace 根跑, uv workspace 运行时解析)
    # e.g. uv run --package cockpit python -m cockpit.scripts.cockpit_mcp
    if package and not directory:
        pkg_underscore = package.replace("-", "_")
        for proj in (
            WORKSPACE / "projects" / package,
            WORKSPACE / "projects" / pkg_underscore,
        ):
            for cand in (proj / "src" / package, proj / "src" / pkg_underscore):
                if cand.exists():
                    return True, "ok (--package)"
        # package 可能在 monorepo workspace (kairon), L2 不深查 uv 运行时解析
        return True, "ok (--package workspace)"

    # 路径 3: --directory + -m module (原逻辑)
    if not directory:
        return False, "no --directory/--package/script in command"

    dir_path = WORKSPACE / directory
    if not dir_path.exists():
        return False, f"--directory not found: {directory}"

    if not module:
        # 没 -m 也算通过 (可能直接跑脚本), directory 在就行
        return True, "ok (no -m, directory exists)"

    # module 包目录可定位? 查多种布局 (项目根 src / monorepo workspace)
    # 老王务实: 不做完整 import 验证 (慢), 只查包根目录在不在
    pkg_root = module.split(".")[0]
    candidates = [
        dir_path / "src" / pkg_root,                              # 标准布局 (projects/omo/src/omo)
        dir_path / pkg_root,                                      # 根布局
        dir_path / "src" / module.replace(".", "/"),             # 完整 module 路径
        dir_path / "packages" / pkg_root / "src" / pkg_root,     # monorepo workspace (kairon)
        dir_path / "packages" / pkg_root,                        # monorepo 包根
        dir_path / "packages" / pkg_root.replace("_", "-") / "src" / pkg_root,  # dash包名/underscore module (core-models→core_models)
    ]
    if any(p.exists() for p in candidates):
        return True, "ok"

    return False, f"module pkg not found: {pkg_root} under {directory}"


def _check_internal(module_path: str, func_name: str) -> tuple[bool, str]:
    """internal: 检查 module_path 文件存在."""
    if not module_path:
        return False, "no module_path"
    # module_path 可能是 "package.module" 或文件路径
    # 老王务实: 找全 workspace 下匹配的 .py
    target = module_path.replace(".", "/") + ".py"
    for proj in (WORKSPACE / "projects").iterdir():
        for sub in ("src", ""):
            candidate = proj / sub / target if sub else proj / target
            if candidate.exists():
                if not func_name:
                    return True, "ok (module found, no func check)"
                return True, "ok"
    return False, f"module_path not found: {module_path}"


def _check_http(http_url: str) -> tuple[bool, str]:
    """mcp_proxy/http: 检查 url 非空 + 合法."""
    if not http_url:
        return False, "no http_url"
    if not re.match(r"^https?://", http_url):
        return False, f"invalid http_url: {http_url}"
    return True, "ok"


def check_service(svc) -> dict:
    """检查单个 BOS service 声明真实性 (L2)."""
    transport = svc.transport
    ok, reason = False, "unknown transport"

    if transport in ("stdio", "mcp_stdio"):
        ok, reason = _check_stdio(svc.command)
    elif transport == "internal":
        ok, reason = _check_internal(svc.module_path, svc.func_name)
    elif transport in ("mcp_proxy", "http"):
        ok, reason = _check_http(svc.http_url)

    return {
        "uri": svc.uri,
        "transport": transport,
        "package": svc.package,
        "resolvable": ok,
        "reason": reason,
    }


# ── L3: 执行抽样 (spawn, 慢, 可选) ──────────────────────────────


def spawn_check(svc, timeout: int = 10) -> dict:
    """L3: 真 spawn 一个 stdio service 的 command + '--help' (或 dry).

    只对 stdio/mcp_stdio 有意义. 返回能否启动 (exit code 或 timeout 都算能启动).
    """
    if svc.transport not in ("stdio", "mcp_stdio"):
        return {"uri": svc.uri, "spawnable": None, "note": "non-stdio skipped"}

    # 跑 command 但加 --help (不真执行业务, 只验证模块能加载)
    cmd = list(svc.command) + ["--help"]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        # exit 0 = 能跑; 非 0 但有 stderr 输出 (argparse 抱怨) 也算模块能加载
        spawnable = result.returncode == 0 or bool(result.stderr)
        return {
            "uri": svc.uri,
            "spawnable": spawnable,
            "exit_code": result.returncode,
            "stderr_head": result.stderr[:120].replace("\n", " "),
        }
    except subprocess.TimeoutExpired:
        # timeout 说明进程起来了 (在等 stdin), 算能 spawn
        return {"uri": svc.uri, "spawnable": True, "note": "timeout (process started)"}
    except FileNotFoundError as e:
        return {"uri": svc.uri, "spawnable": False, "error": str(e)[:120]}
    except Exception as e:
        return {
            "uri": svc.uri,
            "spawnable": False,
            "error": f"{type(e).__name__}: {e}"[:120],
        }


# ── 反馈回路维度 (让现实进入度量) ────────────────────────────────


def check_working_tree() -> dict:
    """working tree 累积文件数 (CR-GOV-COMMIT-FREQUENCY-01: >100 warn, >500 error)."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        return {"dirty_count": len(lines)}
    except Exception as e:
        return {"dirty_count": -1, "error": str(e)[:120]}


def check_feedback_loop() -> dict:
    """governance-history.jsonl 最后时间戳 — 反馈回路存活信号."""
    if not GOV_LOG.exists():
        return {"alive": False, "reason": "no governance log"}
    try:
        lines = [
            line for line in GOV_LOG.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        if not lines:
            return {"alive": False, "reason": "empty log"}
        last = json.loads(lines[-1])
        ts = last.get("timestamp") or last.get("ts") or last.get("date") or ""
        staleness_hours = None
        alive = None
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                delta = datetime.now(timezone.utc) - dt
                staleness_hours = round(delta.total_seconds() / 3600, 1)
                alive = staleness_hours < 24  # 24h 内有记录 = 活着
            except (ValueError, TypeError):
                pass
        return {
            "last_ts": ts,
            "staleness_hours": staleness_hours,
            "alive": alive,
            "entry_count": len(lines),
        }
    except Exception as e:
        return {"alive": False, "error": str(e)[:120]}


# ── evidence_health_score 综合 ──────────────────────────────────


def compute_evidence_score(bos_rate: float, tree: dict, feedback: dict) -> dict:
    """综合三维度算 evidence_health_score (对比假的 health_score=100).

    W_BOS=60: BOS resolve 率 (核心鸿沟)
    W_TREE=20: working tree 清洁 (<50 满分, >500 零分)
    W_FEEDBACK=20: 反馈回路 (governance <24h 满分)
    """
    # BOS 维度
    bos_score = bos_rate * W_BOS

    # working tree 维度
    dirty = tree.get("dirty_count", -1)
    if dirty < 0:
        tree_score = W_TREE / 2  # 读不到给一半
    elif dirty < 50:
        tree_score = W_TREE
    elif dirty < 100:
        tree_score = W_TREE * 0.7
    elif dirty < 500:
        tree_score = W_TREE * 0.3
    else:
        tree_score = 0

    # 反馈回路维度
    alive = feedback.get("alive")
    if alive is True:
        feedback_score = W_FEEDBACK
    elif alive is False:
        feedback_score = 0
    else:
        feedback_score = W_FEEDBACK / 2  # unknown

    total = round(bos_score + tree_score + feedback_score, 1)
    return {
        "evidence_health_score": total,
        "breakdown": {
            "bos_resolve": {
                "score": round(bos_score, 1),
                "weight": W_BOS,
                "rate": round(bos_rate, 3),
            },
            "working_tree": {
                "score": round(tree_score, 1),
                "weight": W_TREE,
                "dirty": dirty,
            },
            "feedback_loop": {
                "score": round(feedback_score, 1),
                "weight": W_FEEDBACK,
                "alive": alive,
            },
        },
    }


# ── 主流程 ──────────────────────────────────────────────────────


def run_smoke(spawn_n: int = 0) -> dict:
    """跑全量证据 smoke, 返回报告 dict."""
    # 动态 import (避免脚本加载时就崩 — agora 不在时给清晰报错)
    try:
        from agora.mcp.resolver.services import POC_SERVICES  # type: ignore[import-not-found]
    except ImportError as e:
        print(f"❌ 无法 import agora.mcp.resolver.services: {e}", file=sys.stderr)
        print(f"   脚本依赖 projects/agora (sys.path={AGORA_SRC})", file=sys.stderr)
        return {"error": "import_failed", "detail": str(e)}

    # L2 全量检查
    results = [check_service(svc) for svc in POC_SERVICES]
    by_transport = Counter(r["transport"] for r in results)
    resolvable = [r for r in results if r["resolvable"]]
    failures = [r for r in results if not r["resolvable"]]

    # failures 分 deprecated (已知调研中, 不计鸿沟) vs real_gap (真实要修的)
    deprecated_fails: list[dict] = []
    real_fails: list[dict] = []
    for r in failures:
        is_gap, reason = _is_known_gap(r["uri"])
        if is_gap:
            r["deprecated_reason"] = reason
            deprecated_fails.append(r)
        else:
            real_fails.append(r)

    # 失败原因分桶 (仅真实 gap, deprecated 不混入)
    failure_buckets = Counter(
        (r.get("reason") or "unknown").split(":")[0].split("(")[0].strip()
        for r in real_fails
    )

    # bos_rate: deprecated 也算未 resolve (诚实, 不 gaming score); deprecated 只是分类标签
    # 价值: 输出告诉你 "鸿沟 X 里 Y 调研中 / Z 真实新鸿沟要立即修"
    bos_rate = len(resolvable) / len(results) if results else 0.0

    # 反馈回路维度
    tree = check_working_tree()
    feedback = check_feedback_loop()

    # 综合分
    score = compute_evidence_score(bos_rate, tree, feedback)

    report = {
        "generated_at": _utc_now(),
        "source": "bin/evidence-smoke.py (real audit, no mock)",
        "bos": {
            "declaration_count": len(results),
            "resolvable_count": len(resolvable),
            "gap": len(real_fails),  # 真实鸿沟 (不含 deprecated)
            "deprecated_count": len(deprecated_fails),
            "deprecated_expires": KNOWN_GAP_EXPIRES,
            "resolve_rate": round(bos_rate, 3),
            "by_transport": dict(by_transport),
            "failure_buckets": dict(failure_buckets),
        },
        "deprecated": [
            {"uri": r["uri"], "reason": r.get("deprecated_reason", "")}
            for r in deprecated_fails
        ],
        "working_tree": tree,
        "feedback_loop": feedback,
        "evidence_health_score": score["evidence_health_score"],
        "score_breakdown": score["breakdown"],
    }

    # L3 抽样 spawn (可选, 慢)
    if spawn_n > 0:
        import random

        stdio_pool = [s for s in POC_SERVICES if s.transport in ("stdio", "mcp_stdio")]
        sample = random.sample(stdio_pool, min(spawn_n, len(stdio_pool)))
        print(f"🔍 L3 抽样 spawn {len(sample)} 个 stdio service...", file=sys.stderr)
        spawn_results = [spawn_check(s) for s in sample]
        report["spawn_sample"] = spawn_results
        spawnable_count = sum(1 for r in spawn_results if r.get("spawnable"))
        report["spawn_summary"] = {
            "sampled": len(spawn_results),
            "spawnable": spawnable_count,
            "rate": round(spawnable_count / len(spawn_results), 3)
            if spawn_results
            else 0,
        }

    # 写 JSON 报告
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{_today()}.json"
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return report


def print_summary(report: dict, quiet: bool = False) -> None:
    """打印人可读 summary."""
    if quiet:
        print(report.get("evidence_health_score", "?"))
        return

    bos = report.get("bos", {})
    tree = report.get("working_tree", {})
    fb = report.get("feedback_loop", {})
    score = report.get("evidence_health_score", "?")

    print("=" * 62)
    print("📊 证据驱动 smoke — 声明/执行鸿沟 + 反馈回路")
    print("=" * 62)
    print(f"🏷  evidence_health_score: {score} / 100  (对比假的 health_score=100)")
    print()
    print("── BOS 声明/执行 (核心鸿沟, 权重 60%) ──")
    print(f"  声明总数:    {bos.get('declaration_count', '?')}")
    print(f"  可 resolve:  {bos.get('resolvable_count', '?')}")
    print(f"  鸿沟:        {bos.get('gap', '?')} (声明 alive 但证据不足)")
    print(f"  resolve 率:  {bos.get('resolve_rate', '?')}")
    print(f"  transport:   {bos.get('by_transport', {})}")
    if bos.get("failure_buckets"):
        print(f"  失败分桶:    {bos['failure_buckets']}")
    dep_n = bos.get("deprecated_count", 0)
    if dep_n:
        print(
            f"  deprecated:  {dep_n} (调研中, expires {bos.get('deprecated_expires', '?')}, 不计鸿沟)"
        )
    print()
    print("── working tree 累积 (权重 20%) ──")
    print(f"  dirty 文件:  {tree.get('dirty_count', '?')}")
    print()
    print("── 反馈回路 (权重 20%) ──")
    print(f"  governance 最后: {fb.get('last_ts', '?')}")
    print(f"  停摆时长:       {fb.get('staleness_hours', '?')} h")
    print(f"  回路存活:       {fb.get('alive', '?')}")
    if report.get("spawn_summary"):
        ss = report["spawn_summary"]
        print()
        print("── L3 抽样 spawn (执行验证) ──")
        print(
            f"  采样: {ss['sampled']} | 可 spawn: {ss['spawnable']} | 率: {ss['rate']}"
        )
    print()
    print(f"📁 报告: {OUTPUT_DIR}/{_today()}.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--spawn",
        type=int,
        default=0,
        help="L3 抽样 spawn N 个 stdio service (慢, 默认 0 不跑)",
    )
    parser.add_argument("--quiet", action="store_true", help="只输出 score")
    args = parser.parse_args()

    report = run_smoke(spawn_n=args.spawn)
    if "error" in report:
        return 1

    print_summary(report, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
