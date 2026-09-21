#!/usr/bin/env python3
"""主仓测试集可收集性守卫 — 防"孤儿测试"腐烂 (P85 配套).

## 背景

2026-09-21 实测: 主仓 364 个测试文件、3496 个测试可收集, 但 4 个文件在
collection 阶段抛错即让 `pytest tests/` **整体 Interrupted** ——
测试集既无法本地全量跑, 也无法接入 CI。

根因是**孤儿测试**: CI 仅在 `governance-check.yml` 跑 7 个 +
`gac-gate.yml` 跑 2 个 cockpit 文件 ≈ 9-11 个, 余下 ~353 个存在
"不运行 → 腐烂无人知" 的盲区。实证腐化形态:
  - 引用已归档脚本 (`bin/gac/daemon-watchdog.py` 等被 bin 配额腾挪)
  - fixture 落后于多轮契约演进 (漏必填 kwarg / 缺 admission 字段)

## 口径

以 `pytest --collect-only` 为准: **不执行测试**, 只保证每个测试文件
都能被 import。故不受存量逻辑失败影响 (实测全量运行有百余失败, 属
独立议题), 只拦截"文件根本无法加载"这一类腐化。

## 分类 (防误报)

| 类别 | 判据 | 结果 |
|---|---|---|
| 仓内腐化 | 引用仓内已删文件 / 语法错误 / 坏 import | **FAIL** |
| 环境缺失 | 子模块未 init / 第三方包未装 | 报告但不 FAIL |

CI 侧 `actions/checkout` 带 `submodules: recursive`, 故环境齐备;
本地缺环境不应阻塞开发者。

## 用法 / 退出码

    python3 bin/gac/check-test-collection.py [--json] [--paths tests/]

    0 = 无仓内腐化 (可能含环境性跳过)
    1 = 存在仓内腐化
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

# 外部依赖缺失的典型 Python 异常 (环境性, 非仓内腐化)
_ENV_ERROR_MARKERS = (
    "ModuleNotFoundError",
    "No module named",
    "cannot import name",
)
# 第三方包/子模块外部依赖的 import 名, 命中即视为环境性
_ENV_TOPS = frozenset(
    {
        "aiosqlite",
        "sqlalchemy",
        "psycopg",
        "psycopg2",
        "fastapi",
        "pydantic",
        "httpx",
        "torch",
        "numpy",
        "pandas",
        "yaml",
        "pytest",
    }
)


def _uninitialized_submodules() -> list[str]:
    """未物化的子模块 (git submodule status 以 '-' 开头的行)。"""
    try:
        proc = subprocess.run(
            ["git", "submodule", "status"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    out = []
    for line in proc.stdout.splitlines():
        if line.startswith("-"):
            parts = line.split()
            if len(parts) >= 2:
                out.append(parts[1])
    return out


def _classify(reason: str) -> str:
    """把 collection 错误归类为 'env' 或 'repo'。"""
    if "FileNotFoundError" in reason:
        # 指向仓内路径的缺失 = 腐化 (指向未物化子模块的情形另行降级)
        return "repo"
    if "SyntaxError" in reason:
        return "repo"
    if "ImportError" in reason or any(marker in reason for marker in _ENV_ERROR_MARKERS):
        # 1) 显式第三方包名 (任一形态: "No module named 'x'" / "simulated: x unavailable")
        for top in _ENV_TOPS:
            if re.search(rf"(?<![A-Za-z0-9_.]){re.escape(top)}(?![A-Za-z0-9_])", reason):
                return "env"
        # 2) 顶层 import 名解析: 仓内目录/项目 → 仓内腐化; 否则视为环境依赖
        match = re.search(r"No module named '([^']+)'", reason)
        if match:
            top = match.group(1).split(".", 1)[0]
            in_repo = (WORKSPACE / "projects" / top).exists() or (WORKSPACE / top).exists()
            return "repo" if in_repo else "env"
        # 3) 无法解析的 import 失败: 若提及仓内已知路径片段则判腐化, 否则按环境
        if re.search(r"(bin|lib|projects|tests)/", reason):
            return "repo"
        return "env"
    return "repo"


def _missing_path_in_uninit_submodule(reason: str, uninit: list[str]) -> bool:
    """缺失路径是否落在未初始化/部分物化的子模块内。

    部分物化 (目录存在但 checkout 不完整) 与完全未 init 都属环境性:
    开发者未必能/需要拉齐全部子模块, 不该因此被 gate 阻塞。
    """
    match = re.search(r"No such file or directory: '([^']+)'", reason)
    if not match:
        return False
    path = match.group(1)
    for rel in uninit:
        marker = f"/{rel}/"
        if marker in path:
            return True
    return False


def _pytest_available() -> bool:
    """当前解释器是否可加载 pytest (守卫的硬依赖)。"""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def collect(paths: list[str], timeout: int = 600) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *paths,
        "--collect-only",
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "collected": None, "errors": [], "timeout": True}

    output = proc.stdout + proc.stderr
    errors: list[dict[str, str]] = []
    # pytest 的 short-summary `ERROR <file>` 行不带原因; 稳健做法是解析 ERRORS 段:
    #   ________________ ERROR collecting <file> ________________
    #   ...
    #   E   <ExceptionType>: <message>
    for chunk in re.split(r"ERROR collecting ", output)[1:]:
        lines = chunk.splitlines()
        if not lines:
            continue
        file_part = lines[0].strip().rstrip("_").strip()
        # chunk 末尾可能粘着下一个段; 取首个以 E 开头的异常行
        reason = ""
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("E ") or stripped.startswith("E\t"):
                reason = stripped[2:].strip()
                break
        errors.append({"file": file_part, "reason": reason})

    # 兜底: 部分 pytest 版本/插件在 summary 行直接附原因, 且 ERRORS 段被截断
    if not errors:
        for line in output.splitlines():
            if line.startswith("ERROR "):
                rest = line[len("ERROR ") :].strip()
                file_part, _, reason = rest.partition(" - ")
                errors.append({"file": file_part.strip(), "reason": reason.strip()})

    collected = None
    match = re.search(r"(\d+)\s+tests?\s+collected", output)
    if match:
        collected = int(match.group(1))

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "collected": collected,
        "errors": errors,
        "timeout": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--paths", nargs="*", default=["tests/"], help="待收集路径 (默认 tests/)")
    parser.add_argument("--timeout", type=int, default=600, help="收集超时秒数")
    args = parser.parse_args()

    if not _pytest_available():
        report = {
            "schema": "test-collection-gate/v1",
            "ok": True,
            "status": "env_skip",
            "degraded_reason": "当前解释器无 pytest (环境性); 守卫跳过, 不阻塞",
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("═══ 测试集可收集性 ═══")
            print(f"  ⏭  {report['degraded_reason']}")
        return 0

    result = collect(list(args.paths), timeout=args.timeout)

    if result["timeout"]:
        report = {
            "ok": False,
            "status": "timeout",
            "message": f"collection 超时 (>{args.timeout}s) — 疑似测试文件在 import 期挂起",
        }
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else report["message"])
        return 1

    env_reasons: list[dict[str, str]] = []
    repo_errors: list[dict[str, str]] = []
    uninit = _uninitialized_submodules()
    for err in result["errors"]:
        if _missing_path_in_uninit_submodule(err["reason"], uninit):
            env_reasons.append(err)
        elif _classify(err["reason"]) == "env":
            env_reasons.append(err)
        else:
            repo_errors.append(err)

    report = {
        "schema": "test-collection-gate/v1",
        "collected": result["collected"],
        "collection_errors": len(result["errors"]),
        "repo_errors": repo_errors,
        "env_skipped": env_reasons,
        "uninitialized_submodules": uninit,
        "ok": not repo_errors,
        "status": "pass",
        "pytest_returncode": result.get("returncode"),
    }

    if env_reasons and not repo_errors:
        report["status"] = "pass_with_env_skips"
        report["degraded_reason"] = f"{len(env_reasons)} 项环境性跳过 (第三方依赖未装)"

    if repo_errors:
        report["status"] = "fail"

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("═══ 测试集可收集性 ═══")
        print(f"可收集测试: {report['collected']}")
        print(f"collection 错误: {report['collection_errors']}")
        for err in report["repo_errors"]:
            print(f"  ❌ [仓内腐化] {err['file']}: {err['reason'][:160]}")
        for err in report["env_skipped"]:
            print(f"  ⏭  [环境依赖] {err['file']}: {err['reason'][:120]}")
        if report.get("degraded_reason"):
            print(f"  ⚠️  {report['degraded_reason']}")
        print(f"测试集可收集性: {'PASS' if report['ok'] else 'FAIL'}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
