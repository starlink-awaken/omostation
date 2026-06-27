#!/usr/bin/env python3
"""ssot-guardian: SSOT 漂移守门员.

长期机制,防止 system.yaml / goals/current.yaml / tasks/registry/INDEX.md / 子模块指针 /
direct-omo-io 约束与真实状态漂移. 可手动跑、pre-commit 跑、cron 跑.

检测项:
  1. system.yaml task 计数 vs tasks/{active,planned,done} 顶层 yaml 文件数
  2. system.yaml current_wave vs goals/current.yaml current_wave
  3. 子模块指针是否落后于子仓库 HEAD (git submodule status '+' 前缀)
  4. direct-omo-io 红线: 脚本是否直接写入 .omo/

修复项(仅 --auto-fix 时):
  A. 调用 `omo state sync-tasks` 重算 system.yaml task 计数
  B. 如果 goals/current.yaml current_wave 落后 system.yaml, 同步为 system.yaml 的值
  (子模块漂移和 direct-omo-io 无法自动修复, 必须人工/OMO 处理)

用法:
  python3 bin/ssot-guardian.py              # 检测,有漂移返回 1
  python3 bin/ssot-guardian.py --auto-fix   # 检测并修复白名单字段
  python3 bin/ssot-guardian.py --emit       # 无论是否漂移都发事件

退出码:
  0 — 无漂移(或已修复)
  1 — 检测到未修复漂移
  2 — 运行错误
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
OMO_DIR = WORKSPACE_ROOT / ".omo"
SYSTEM_YAML = OMO_DIR / "state" / "system.yaml"
GOALS_YAML = OMO_DIR / "goals" / "current.yaml"
INDEX_MD = OMO_DIR / "tasks" / "registry" / "INDEX.md"
TASKS_DIR = OMO_DIR / "tasks"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def _load_yaml_docs(path: Path) -> list[dict]:
    """极简多文档 YAML 读取: 只取顶层 key: value."""
    docs: list[dict] = []
    current: dict[str, object] = {}
    in_doc = False
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip() == "---":
            if in_doc:
                docs.append(current)
            current = {}
            in_doc = True
            continue
        if not in_doc:
            in_doc = True
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$", line)
        if m:
            key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
            current[key] = val
    if current:
        docs.append(current)
    return docs


def _load_system_value(key: str) -> object | None:
    text = SYSTEM_YAML.read_text(encoding="utf-8")
    for line in text.splitlines():
        m = re.match(rf"^{re.escape(key)}:\s*(.*?)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def _count_tasks() -> dict[str, int]:
    counts = {}
    for sub in ("active", "planned", "done"):
        d = TASKS_DIR / sub
        counts[sub] = len(list(d.glob("*.yaml"))) if d.exists() else 0
    counts["total"] = counts["active"] + counts["planned"] + counts["done"]
    return counts


def _sync_tasks(auto_fix: bool) -> dict:
    """调用 omo state sync-tasks, 返回差异信息."""
    cmd = ["omo", "state", "sync-tasks"]
    if not auto_fix:
        cmd.append("--dry-run")
    try:
        result = _run(cmd, check=False)
    except FileNotFoundError:
        return {"error": "omo CLI not found"}
    output = result.stdout + result.stderr
    drift = "114" not in output or "→" in output  # 粗略判断有变化
    return {
        "returncode": result.returncode,
        "output": output,
        "drift": drift,
    }


def _check_wave() -> dict:
    system_wave = _load_system_value("current_wave")
    docs = _load_yaml_docs(GOALS_YAML)
    goals_wave = docs[-1].get("current_wave") if docs else None
    return {
        "system_wave": system_wave,
        "goals_wave": goals_wave,
        "aligned": system_wave == goals_wave,
    }


def _fix_wave() -> dict:
    """current_wave 自动修复占位.

    当前没有 OMO CLI 子命令可以直接更新 goals/current.yaml current_wave.
    根据 direct-omo-io 约束,禁止在本脚本中直接 write_text() 到 .omo 文件.
    因此 auto-fix 仅发出事件并给出人工/未来 OMO 命令修复建议.
    """
    system_wave = _load_system_value("current_wave")
    if not system_wave:
        return {"fixed": False, "error": "cannot read system.yaml current_wave"}
    return {
        "fixed": False,
        "manual_action_required": True,
        "system_wave": system_wave,
        "suggested_command": "omo goal sync-wave (待 OMO P63+ 实现)",
        "fallback_command": "手动编辑 .omo/goals/current.yaml 使 current_wave 与 system.yaml 一致",
    }


def _emit_event(kind: str, payload: dict) -> None:
    try:
        _run(
            [
                "omo",
                "event",
                "emit",
                "--type",
                kind,
                "--source",
                "ssot-guardian",
                "--payload",
                json.dumps(payload, ensure_ascii=False),
            ],
            check=False,
        )
    except FileNotFoundError:
        pass


def _check_submodules() -> dict:
    """检测子模块指针是否落后于子仓库 HEAD ('+' 前缀).

    '+sha path (heads/main)' 表示子仓库有未 bump 到根仓库的提交.
    """
    result = _run(["git", "submodule", "status"], check=False)
    if result.returncode != 0:
        return {"error": result.stderr, "dirty": []}
    dirty: list[dict] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or not line.startswith("+"):
            continue
        # format: +sha path (ref)
        parts = line[1:].split()
        if len(parts) >= 2:
            dirty.append(
                {"sha": parts[0], "path": parts[1], "ref": " ".join(parts[2:])}
            )
    return {"dirty": dirty, "count": len(dirty)}


OMO_PROJECT_DIR = WORKSPACE_ROOT / "projects" / "omo"


def _run_omo_lint(subcmd: str) -> subprocess.CompletedProcess[str]:
    """调用真正的 omo governance lint 子命令 (projects/omo/.venv).

    全局 PATH 里的 `omo` 已被 oh-my-opencode 占用, 不能直接 `omo lint ...`.
    """
    return _run(
        [
            "uv",
            "run",
            "--project",
            str(OMO_PROJECT_DIR),
            "python",
            "-m",
            "omo.omo_lint",
            subcmd,
        ],
        check=False,
    )


def _check_direct_omo_io() -> dict:
    """运行 omo lint direct-omo-io, 检测直接 .omo/ 写入."""
    result = _run_omo_lint("direct-omo-io")
    passed = "PASS" in result.stdout or result.returncode == 0
    return {
        "passed": passed,
        "returncode": result.returncode,
        "summary": result.stdout.strip().splitlines()[-1] if result.stdout else "",
    }


def _check_bos_unimplemented() -> dict:
    """BOS 期房与失效路由检测.

    检测 bos-services.yaml 中**未**标为 [UNIMPLEMENTED] 的服务，
    验证其 package 是否存在，以及 package 对应的 do_default.py 中是否有分支支持该 action。
    [UNIMPLEMENTED] 是已知占位状态，不视为漂移。
    """
    import yaml

    yaml_path = WORKSPACE_ROOT / "projects" / "agora" / "etc" / "bos-services.yaml"
    if not yaml_path.exists():
        return {"passed": True, "note": "bos-services.yaml not found"}

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        return {"passed": False, "error": f"Failed to parse bos-services.yaml: {e}"}

    services = data.get("services", [])
    broken: list[dict] = []

    for s in services:
        uri = s.get("uri", "")
        desc = s.get("description", "")
        package = s.get("package", "")
        action = s.get("action", "")

        if desc and desc.startswith("[UNIMPLEMENTED]"):
            # 已知未实现占位符，不视为漂移
            continue

        if not package:
            continue

        # 1. 检查 package 物理目录
            pkg_dir = None
            if package:
                # 优先在 projects/kairon/packages/ 寻找
                kairon_pkg = WORKSPACE_ROOT / "projects" / "kairon" / "packages" / package
                generic_pkg = WORKSPACE_ROOT / "projects" / package
                if kairon_pkg.exists():
                    pkg_dir = kairon_pkg
                elif generic_pkg.exists():
                    pkg_dir = generic_pkg

            if not pkg_dir:
                broken.append({
                    "uri": uri,
                    "reason": f"Package '{package}' directory not found in workspace",
                })
                continue

            # 2. 检查 action 是否有代码分支支持 (针对 kairon 包的 do_default.py)
            do_default_py = pkg_dir / "src" / package.replace("-", "_") / "do_default.py"
            main_py = pkg_dir / "src" / package.replace("-", "_") / "__main__.py"

            if do_default_py.exists():
                code = do_default_py.read_text(encoding="utf-8")
                pattern = rf'action\s*==\s*[\'"]{action}[\'"]'
                if not re.search(pattern, code):
                    has_handler = False
                    if main_py.exists():
                        main_code = main_py.read_text(encoding="utf-8")
                        func_pattern = rf'def\s+do_{action.replace("-", "_")}\s*\('
                        if re.search(func_pattern, main_code):
                            has_handler = True
                    if not has_handler:
                        broken.append({
                            "uri": uri,
                            "reason": f"No code branch found for action '{action}' in do_default.py or __main__.py",
                        })
            elif main_py.exists():
                main_code = main_py.read_text(encoding="utf-8")
                func_pattern = rf'def\s+do_{action.replace("-", "_")}\s*\('
                if not re.search(func_pattern, main_code):
                    broken.append({
                        "uri": uri,
                        "reason": f"No handler function 'do_{action}' found in __main__.py",
                    })
            else:
                if s.get("transport") in ("stdio", "mcp_stdio"):
                    broken.append({
                        "uri": uri,
                        "reason": f"Entry file do_default.py or __main__.py not found for stdio transport",
                    })

    return {
        "passed": len(broken) == 0,
        "broken": broken,
        "count": len(broken)
    }


def _check_hygiene() -> dict:
    """CR-HYG-01/02: 工作区卫生 (0字节文件 + 大小写 inode). 复用 gac-hygiene-check (DRY)."""
    result = _run(
        ["python3", str(WORKSPACE_ROOT / "bin" / "gac-hygiene-check.py"), "--json"],
        check=False,
    )
    try:
        data = json.loads(result.stdout) if result.stdout else {}
    except json.JSONDecodeError:
        return {"passed": False, "error": "gac-hygiene-check JSON parse failed"}
    return {
        "passed": result.returncode == 0,
        "zero_byte": data.get("zero_byte_count", 0),
        "case_conflicts": data.get("case_conflict_count", 0),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SSOT 漂移守门员")
    parser.add_argument("--auto-fix", action="store_true", help="自动修复白名单字段")
    parser.add_argument("--emit", action="store_true", help="无论是否漂移都发事件")
    args = parser.parse_args(argv)

    if not SYSTEM_YAML.exists():
        print("❌ system.yaml not found", file=sys.stderr)
        return 2

    issues: list[dict] = []

    # 1. task 计数漂移
    real_counts = _count_tasks()
    system_completed = _load_system_value("completed_tasks")
    system_planned = _load_system_value("planned_tasks")
    system_active = _load_system_value("active_tasks")
    system_total = _load_system_value("total_tasks")

    task_drift = (
        int(system_completed or 0) != real_counts["done"]
        or int(system_planned or 0) != real_counts["planned"]
        or int(system_active or 0) != real_counts["active"]
        or int(system_total or 0) != real_counts["total"]
    )
    if task_drift:
        issues.append(
            {
                "type": "task_count_drift",
                "severity": "high",
                "system": {
                    "completed": system_completed,
                    "planned": system_planned,
                    "active": system_active,
                    "total": system_total,
                },
                "actual": real_counts,
            }
        )
        if args.auto_fix:
            sync_result = _sync_tasks(auto_fix=True)
            if sync_result.get("returncode") == 0:
                issues[-1]["fixed"] = True
                issues[-1]["fix_method"] = "omo state sync-tasks"
            else:
                issues[-1]["fixed"] = False
                issues[-1]["fix_error"] = sync_result.get("output", "")

    # 2. current_wave 不一致
    wave_check = _check_wave()
    if not wave_check["aligned"]:
        issues.append(
            {
                "type": "current_wave_mismatch",
                "severity": "medium",
                "system_wave": wave_check["system_wave"],
                "goals_wave": wave_check["goals_wave"],
            }
        )
        if args.auto_fix:
            fix_result = _fix_wave()
            if fix_result.get("fixed"):
                issues[-1]["fixed"] = True
                issues[-1]["fix_method"] = "sync goals/current.yaml to system.yaml"
            else:
                issues[-1]["fixed"] = False
                issues[-1]["fix_error"] = fix_result.get("error", "")

    # 3. 子模块指针漂移 (无法 auto-fix, 必须人工/后台 agent 提交后 bump)
    submodule_check = _check_submodules()
    if submodule_check.get("count", 0):
        issues.append(
            {
                "type": "submodule_pointer_drift",
                "severity": "high",
                "dirty": submodule_check["dirty"],
                "auto_fix": False,
                "note": "子仓库有未 bump 到根仓库的提交; 需先提交子仓库再更新根指针",
            }
        )

    # 4. direct-omo-io 红线检查 (无法 auto-fix, 必须修代码)
    dio_check = _check_direct_omo_io()
    if not dio_check.get("passed"):
        issues.append(
            {
                "type": "direct_omo_io_violation",
                "severity": "critical",
                "summary": dio_check.get("summary", ""),
                "auto_fix": False,
                "note": "脚本直接写入 .omo/; 必须改走 omo CLI / omo core / c2g ingress",
            }
        )

    # 5. BOS 期房与失效路由检查 (无法 auto-fix, 必须修代码/清理配置)
    bos_check = _check_bos_unimplemented()
    if not bos_check.get("passed"):
        issues.append(
            {
                "type": "unimplemented_bos_decay",
                "severity": "high",
                "broken": bos_check.get("broken", []),
                "auto_fix": False,
                "note": "bos-services.yaml 中定义了 [UNIMPLEMENTED] 路由，但未实现对应 CLI 接口/处理逻辑",
            }
        )

    # 6. CR-HYG-01/02 工作区卫生 (0字节 + 大小写 inode; 复用 gac-hygiene-check, DRY)
    hyg_check = _check_hygiene()
    if not hyg_check.get("passed"):
        issues.append(
            {
                "type": "workspace_hygiene",
                "severity": "medium",
                "zero_byte": hyg_check.get("zero_byte", 0),
                "case_conflicts": hyg_check.get("case_conflicts", 0),
                "auto_fix": False,
                "note": "0字节文件或大小写 inode 冲突 (CR-HYG-01/02); 见 bin/gac-hygiene-check.py",
            }
        )

    # 报告
    unresolved = [i for i in issues if not i.get("fixed")]
    fixed = [i for i in issues if i.get("fixed")]

    if fixed:
        print(f"✅ 自动修复 {len(fixed)} 项:")
        for i in fixed:
            print(f"   - {i['type']}: {i.get('fix_method', '')}")

    if unresolved:
        print(f"❌ 检测到 {len(unresolved)} 项未修复 SSOT 漂移:")
        for i in unresolved:
            print(f"   - {i['type']} ({i['severity']})")
            if i["type"] == "task_count_drift":
                print(f"     system: {i['system']}")
                print(f"     actual: {i['actual']}")
            elif i["type"] == "current_wave_mismatch":
                print(f"     system={i['system_wave']} goals={i['goals_wave']}")
            elif i["type"] == "submodule_pointer_drift":
                for d in i.get("dirty", []):
                    print(f"     + {d['path']} ({d['sha']})")
            elif i["type"] == "direct_omo_io_violation":
                print(f"     {i.get('summary', '')}")
            elif i["type"] == "unimplemented_bos_decay":
                for b in i.get("broken", []):
                    print(f"     + {b['uri']}: {b['reason']}")
            elif i["type"] == "workspace_hygiene":
                print(f"     0字节={i['zero_byte']} 大小写冲突={i['case_conflicts']}")
    else:
        print("✅ SSOT 一致性检查通过")

    if args.emit or issues:
        _emit_event(
            "ssot_guardian_run",
            {
                "checked_at": _utc_now(),
                "auto_fix": args.auto_fix,
                "issues": issues,
                "unresolved_count": len(unresolved),
            },
        )

    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
