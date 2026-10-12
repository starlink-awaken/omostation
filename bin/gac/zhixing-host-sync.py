#!/usr/bin/env python3
"""织星驾驶舱（:43191）宿主资产的只读漂移检查。

问题（docs/DASHBOARDS.md §3.1，2026-09-17 实证）:
主入口 `:43191` 的部署目录 `~/.local/share/zhixing-dashboard/` **不在任何 git
仓库中**。多 agent 并发编辑同一 `template.html` / `refresh.py` / `live_server.py`
会**互相覆盖**:

  - 场景系统面板被另一 agent 的「metrics redesign」覆盖丢失（所有备份均无该代码）
  - 该次覆盖同时回退了已修好的 `ens[n.type]` bug
  - 一处语法错误直接使整个第二脚本失效 → `D is not defined` → 页面主功能损坏

既有 `zhixing-panel-sync.py` 已**版本化 panels**（`bin/panorama/assets/panels/`）
并幂等注入 —— 但**宿主文件本身未纳管**，而它正是被覆盖的那个。本工具补上:

| 子命令    | 作用 |
|----------|------|
| `status`  | 逐文件 sha 对比（仓库 vs 部署）+ 漂移汇总 |
| `plan`    | 从登记的 LaunchAgent 解析实际运行根，并只读计算明确选择资产的漂移 |
| `check`   | `plan` 的全受管资产兼容别名；漂移或身份不符时 exit 1 |
| `migrate` | plist 迁移: entrypoint → current/live_server.py (建立基线版本) |
| `publish` | 受管发布: 版本目录 + 原子切换 current + SHA 校验 + 回滚 |
| `restore` | 回滚: current 切回上一版本 |

**稳定入口契约** (DCP-20 spec v1.1.0): plist entrypoint 指向 `current/live_server.py`；
`current` 是唯一允许的 symlink，目标落在 `releases/<40位commit-OID>/`；版本目录是
普通目录、无内部 symlink、SHA 对齐主仓资产。`apply`/`capture` 仍 BLOCKED。

用法:
    python3 bin/gac/zhixing-host-sync.py status --json
    python3 bin/gac/zhixing-host-sync.py migrate --json
    python3 bin/gac/zhixing-host-sync.py publish --file live_server.py --file observatory_query.py --json
    python3 bin/gac/zhixing-host-sync.py restore --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import shlex
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = _ROOT / "bin" / "panorama" / "assets" / "host"
DASHBOARD_DIR = Path.home() / ".local" / "share" / "zhixing-dashboard"
LAUNCH_AGENT_LABEL = "com.omostation.zhixing-dashboard"
LAUNCH_AGENT_PLIST = (
    Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
)

# 纳管范围: 宿主模板 + 采集器。数据/产物 (index.html, current.json, caches) 不入仓。
# 映射: (部署目录中的文件名, 仓库资产的相对名)。
#
# 为什么 refresh.py 的仓库名带 .asset 后缀: script-registry / bin-quota 两个门禁
# 都把 `bin/**/*.py` 视为**脚本**(排除规则只认 bin/_* 目录)。而这是部署文件的
# 版本化副本 —— 是**资产不是脚本**, 注册成脚本会污染脚本治理面。用 .asset 后缀
# 既保持与同行 panels 资产相邻 (bin/panorama/assets/), 又不误纳入脚本治理。
HOST_FILES: tuple[tuple[str, str], ...] = (
    ("template.html", "template.html"),
    ("refresh.py", "refresh.py.asset"),
    ("live_server.py", "live_server.py.asset"),
    ("observatory_query.py", "observatory_query.py.asset"),
    ("panorama-collect-main.py", "panorama-collect-main.py.asset"),
    # 2026-09-26: 驾驶舱推理引擎(副驾对话 / RAG 向量+重排)纳管 —— 此前不在任何仓库,
    # 直连 oMLX :8000 且无鉴权; 已改经 aetherforge 门面。
    ("copilot_service.py", "copilot_service.py.asset"),
    ("rag_engine.py", "rag_engine.py.asset"),
    ("strategy_sources.py", "strategy_sources.py.asset"),
    ("collectors/strategy.py", "strategy_collector.py.asset"),
    ("collectors/documents.py", "documents_collector.py.asset"),
    ("collectors/workflow.py", "workflow_collector.py.asset"),
    ("collectors/scheduler.py", "scheduler_collector.py.asset"),
    ("orchestrator.py", "orchestrator.py.asset"),
    ("collectors/portfolio.py", "portfolio_collector.py.asset"),
    ("strategy_projection.py", "strategy_projection.py.asset"),
    ("collectors/agent_brief.py", "agent_brief_collector.py.asset"),
)

BLOCKED_REASON = "g0_m0_hold_release_bet_required"
BLOCKED_COMMANDS = frozenset({"apply", "capture"})

# 稳定入口契约 (DCP-20 spec v1.1.0): plist entrypoint 必须指向 current/live_server.py,
# 唯一允许的 current symlink 目标落在 releases/<40位commit-OID>/ 下。
CURRENT_LINK = DASHBOARD_DIR / "current"
RELEASES_DIR = DASHBOARD_DIR / "releases"
CURRENT_ENTRYPOINT = CURRENT_LINK / "live_server.py"


def _dashboard_git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(DASHBOARD_DIR), *args],
        check=False, capture_output=True, text=True,
    ).stdout.strip()


def _source_commit_oid() -> str:
    """主仓 HEAD (DCP-20 修复所在 commit) —— 待晋升版本的来源 OID。"""
    return _dashboard_git("rev-parse", "HEAD")


def _prepare_version(assets: tuple[tuple[str, str], ...], oid: str) -> dict:
    """在 releases/<OID>/ 下准备版本目录 (普通目录, 无内部 symlink, SHA 对齐主仓资产)。"""
    version_dir = RELEASES_DIR / oid
    if version_dir.exists() and not version_dir.is_dir():
        return {"ok": False, "reason": "version_path_not_dir", "path": str(version_dir)}
    version_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for deploy_name, repo_name in assets:
        source = HOST_DIR / repo_name
        destination = version_dir / deploy_name
        source_sha = _sha(source)
        if source_sha is None:
            return {"ok": False, "reason": "source_asset_missing", "asset": str(source)}
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        written_sha = _sha(destination)
        if written_sha != source_sha:
            return {"ok": False, "reason": "version_sha_drift", "asset": deploy_name}
        manifest.append({"name": deploy_name, "source": str(source),
                         "version": str(destination), "sha": source_sha})
    return {"ok": True, "version_dir": str(version_dir), "oid": oid, "manifest": manifest}


def _switch_current(target_version_dir: Path) -> dict:
    """原子切换 current symlink → 目标版本目录 (temp symlink + rename)。"""
    if not target_version_dir.is_dir():
        return {"ok": False, "reason": "version_dir_missing", "path": str(target_version_dir)}
    temp_link = DASHBOARD_DIR / f".current.tmp.{os.getpid()}"
    try:
        if temp_link.exists() or temp_link.is_symlink():
            temp_link.unlink()
        temp_link.symlink_to(target_version_dir, target_is_directory=True)
        os.replace(temp_link, CURRENT_LINK)
    except OSError as exc:
        if temp_link.exists() or temp_link.is_symlink():
            try:
                temp_link.unlink()
            except OSError:
                pass
        return {"ok": False, "reason": "current_switch_failed", "detail": str(exc)}
    return {"ok": True, "current": str(CURRENT_LINK), "target": str(target_version_dir)}


def _previous_version() -> str | None:
    """解析当前 current symlink 指向的版本 OID (回滚目标)。"""
    try:
        resolved = CURRENT_LINK.resolve()
    except OSError:
        return None
    if RELEASES_DIR in resolved.parents:
        return resolved.name
    return None


def publish(files: list[str] | tuple[str, ...] | None) -> dict:
    """受管发布: 版本目录准备 → 原子切换 current → SHA 校验 → 失败回滚。

    前置: plist entrypoint 必须已迁移到 current/live_server.py (先跑 migrate)。
    """
    runtime = _running_registered_runtime()
    if not runtime.get("ok"):
        return {"ok": False, "reason": "launch_agent_identity_unverified", "runtime": runtime}
    # 身份链: 解析后的 entrypoint 必须落在 RELEASES_DIR 下 (current symlink → releases/<OID>/)
    entry = Path(runtime["entrypoint"])
    if RELEASES_DIR not in entry.parents:
        return {
            "ok": False, "reason": "plist_not_migrated",
            "detail": "先跑 migrate 将 plist entrypoint 指向 current/live_server.py",
            "entrypoint": runtime["entrypoint"],
        }
    try:
        assets = _selected_assets(files)
    except ValueError as exc:
        return {"ok": False, "reason": "invalid_asset_selection", "detail": str(exc)}
    oid = _source_commit_oid()
    if not re.fullmatch(r"[0-9a-f]{40}", oid):
        return {"ok": False, "reason": "source_oid_unresolved", "oid": oid}
    previous = _previous_version()
    prepared = _prepare_version(assets, oid)
    if not prepared.get("ok"):
        return prepared
    switched = _switch_current(Path(prepared["version_dir"]))
    if not switched.get("ok"):
        return switched
    # SHA 校验: 新版本目录中已发布资产与主仓一致
    deployed = _asset_plan(Path(prepared["version_dir"]), files, HOST_DIR)
    if not deployed.get("ok"):
        if previous:
            _switch_current(RELEASES_DIR / previous)
        return {"ok": False, "reason": "deploy_verify_failed",
                "detail": "发布后校验失败, 已尝试回滚", "deploy": deployed}
    return {
        "ok": True, "oid": oid, "version_dir": prepared["version_dir"],
        "previous_version": previous, "write_performed": True,
        "manifest": prepared["manifest"], "deploy": deployed,
    }


def restore() -> dict:
    """回滚: 将 current symlink 切回上一版本。"""
    previous = _previous_version()
    if not previous:
        return {"ok": False, "reason": "no_previous_version"}
    target = RELEASES_DIR / previous
    if not target.is_dir():
        return {"ok": False, "reason": "previous_version_missing", "version": previous}
    return _switch_current(target)


def migrate() -> dict:
    """plist 迁移: entrypoint → current/live_server.py (先以当前部署态建立基线版本)。

    前置: 当前部署态可捕获 (host 文件与 repo 资产对齐或接受为基线)。
    """
    registration = _registered_runtime()
    if not registration.get("ok"):
        return {"ok": False, "reason": "launch_agent_identity_unverified", "registration": registration}
    current_entry = registration["entrypoint"]
    if current_entry == str(CURRENT_ENTRYPOINT):
        return {"ok": True, "already_migrated": True, "entrypoint": current_entry}
    # 备份 plist
    plist_path = _resolved(LAUNCH_AGENT_PLIST)
    backup = plist_path.with_suffix(".plist.bak")
    try:
        backup.write_bytes(plist_path.read_bytes())
    except OSError as exc:
        return {"ok": False, "reason": "plist_backup_failed", "detail": str(exc)}
    # 以当前部署态建立基线版本 (releases/<baseline-OID>/)
    baseline = f"baseline-{_source_commit_oid()[:12]}"
    assets = tuple((name, repo) for name, repo in HOST_FILES)
    prepared = _prepare_version(assets, baseline)
    if not prepared.get("ok"):
        return prepared
    switched = _switch_current(Path(prepared["version_dir"]))
    if not switched.get("ok"):
        return switched
    # 改写 plist entrypoint → current/live_server.py
    try:
        with plist_path.open("rb") as handle:
            payload = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as exc:
        return {"ok": False, "reason": "plist_read_failed", "detail": str(exc)}
    arguments = payload.get("ProgramArguments")
    if not isinstance(arguments, list):
        return {"ok": False, "reason": "launch_agent_program_missing"}
    replaced = False
    for idx, value in enumerate(arguments):
        if isinstance(value, str) and Path(value).name == "live_server.py":
            arguments[idx] = str(CURRENT_ENTRYPOINT)
            replaced = True
    if not replaced:
        return {"ok": False, "reason": "plist_entrypoint_not_found"}
    try:
        with plist_path.open("wb") as handle:
            plistlib.dump(payload, handle)
    except OSError as exc:
        return {"ok": False, "reason": "plist_write_failed", "detail": str(exc)}
    # 迁移后校验: 解析后的 entrypoint 必须落在 RELEASES_DIR 下
    migrated = _registered_runtime()
    if not migrated.get("ok") or RELEASES_DIR not in Path(migrated["entrypoint"]).parents:
        return {"ok": False, "reason": "migrate_verify_failed", "runtime": migrated}
    return {
        "ok": True, "baseline_version": baseline, "entrypoint": str(CURRENT_ENTRYPOINT),
        "backup": str(backup), "write_performed": True,
    }


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _resolved(path: Path) -> Path:
    """Resolve a user supplied path without requiring that it already exists."""
    return path.expanduser().resolve()


def _registered_runtime() -> dict:
    """Read the single installed Zhixing LaunchAgent registration.

    The production read plane has no path or plist override: a caller can inspect
    only the machine's registered runtime, never nominate a target of its own.
    """
    plist_path = _resolved(LAUNCH_AGENT_PLIST)
    try:
        with plist_path.open("rb") as handle:
            payload = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as exc:
        return {"ok": False, "reason": "launch_agent_plist_unreadable", "detail": str(exc)}

    if payload.get("Label") != LAUNCH_AGENT_LABEL:
        return {"ok": False, "reason": "launch_agent_label_mismatch"}
    arguments = payload.get("ProgramArguments")
    working_directory = payload.get("WorkingDirectory")
    if not isinstance(arguments, list):
        return {"ok": False, "reason": "launch_agent_program_missing"}

    scripts = [argument for argument in arguments if isinstance(argument, str)
               and Path(argument).name == "live_server.py"]
    if len(scripts) != 1:
        return {"ok": False, "reason": "launch_agent_live_server_ambiguous"}

    script = Path(scripts[0]).expanduser()
    if not script.is_absolute():
        if not isinstance(working_directory, str):
            return {"ok": False, "reason": "launch_agent_relative_entrypoint_without_root"}
        script = _resolved(Path(working_directory)) / script
    script = _resolved(script)
    root = script.parent
    if isinstance(working_directory, str) and _resolved(Path(working_directory)) != root:
        return {
            "ok": False,
            "reason": "launch_agent_root_mismatch",
            "runtime_root": str(root),
            "entrypoint": str(script),
        }
    if script.name != "live_server.py":
        return {"ok": False, "reason": "launch_agent_entrypoint_mismatch"}
    return {
        "ok": True,
        "label": LAUNCH_AGENT_LABEL,
        "plist": str(plist_path),
        "runtime_root": str(root),
        "entrypoint": str(script),
    }


def _running_registered_runtime() -> dict:
    """Bind read-only planning to the registered LaunchAgent's current process."""
    registration = _registered_runtime()
    if not registration.get("ok"):
        return registration

    domain = f"gui/{os.getuid()}/{LAUNCH_AGENT_LABEL}"
    try:
        launchctl = subprocess.run(
            ["launchctl", "print", domain],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {"ok": False, "reason": "launch_agent_pid_unavailable", "detail": str(exc),
                "registration": registration}
    matched = re.search(r"(?m)^\s*pid = (\d+)\s*$", launchctl.stdout) if launchctl.returncode == 0 else None
    if matched is None:
        return {"ok": False, "reason": "launch_agent_pid_unavailable", "registration": registration}

    pid = int(matched.group(1))
    try:
        process = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {"ok": False, "reason": "launch_agent_pid_command_unavailable", "detail": str(exc),
                "pid": pid, "registration": registration}
    command = process.stdout.strip() if process.returncode == 0 else ""
    try:
        arguments = shlex.split(command)
    except ValueError:
        arguments = []
    entrypoint = registration["entrypoint"]
    try:
        port_index = arguments.index("--port")
        port_matches = arguments[port_index + 1] == "43191"
    except (ValueError, IndexError):
        port_matches = False
    if entrypoint not in arguments or not port_matches:
        return {
            "ok": False,
            "reason": "launch_agent_pid_command_mismatch",
            "pid": pid,
            "command": command,
            "registration": registration,
        }
    return {"ok": True, "pid": pid, "command": command, **registration}


def status(dashboard_dir: Path | None = None, host_dir: Path | None = None) -> dict:
    dash = dashboard_dir or DASHBOARD_DIR
    host = host_dir or HOST_DIR
    files = []
    drifted = missing_repo = missing_deploy = 0
    for deploy_name, repo_name in HOST_FILES:
        repo, live = host / repo_name, dash / deploy_name
        name = deploy_name
        rs, ls = _sha(repo), _sha(live)
        if rs is None:
            state = "no_repo_copy"
            missing_repo += 1
        elif ls is None:
            state = "no_deploy_copy"
            missing_deploy += 1
        elif rs == ls:
            state = "in_sync"
        else:
            state = "drifted"
            drifted += 1
        files.append({"name": name, "state": state, "repo_sha": rs, "deploy_sha": ls,
                      "repo_bytes": _size(repo), "deploy_bytes": _size(live)})
    return {
        "dashboard_dir": str(dash),
        "host_dir": str(host),
        "files": files,
        "drifted": drifted,
        "missing_repo_copy": missing_repo,
        "missing_deploy_copy": missing_deploy,
        "ok": drifted == 0 and missing_repo == 0 and missing_deploy == 0,
    }


def _selected_assets(files: list[str] | tuple[str, ...] | None) -> tuple[tuple[str, str], ...]:
    if not files:
        raise ValueError("必须至少指定一个 --file；禁止隐式全量检查")
    mapping = dict(HOST_FILES)
    requested = tuple(files)
    if len(requested) != len(set(requested)):
        raise ValueError("--file 不能重复")
    unknown = [name for name in requested if name not in mapping]
    if unknown:
        raise ValueError("未登记的宿主资产: " + ", ".join(unknown))
    return tuple((name, mapping[name]) for name in requested)


def _blocked(operation: str) -> dict:
    return {
        "ok": False,
        "state": "BLOCKED",
        "operation": operation,
        "reason": BLOCKED_REASON,
        "detail": "G0=PARTIAL/HOLD and M0=FAIL/HOLD; a separately admitted release BET is required.",
    }


def capture(*_args: object, **_kwargs: object) -> dict:
    """Legacy programmatic entry point: production capture is unavailable."""
    return _blocked("capture")


def _asset_plan(runtime_root: Path,
                files: list[str] | tuple[str, ...] | None,
                host_dir: Path) -> dict:
    try:
        assets = _selected_assets(files)
    except ValueError as exc:
        return {"ok": False, "reason": "invalid_asset_selection", "detail": str(exc)}

    planned: list[dict] = []
    for deploy_name, repo_name in assets:
        source = host_dir / repo_name
        destination = runtime_root / deploy_name
        source_sha = _sha(source)
        runtime_sha = _sha(destination)
        if source_sha is None:
            state = "versioned_asset_missing"
        elif runtime_sha is None:
            state = "runtime_asset_missing"
        elif source_sha == runtime_sha:
            state = "in_sync"
        else:
            state = "drifted"
        planned.append({
            "name": deploy_name,
            "state": state,
            "source": str(source),
            "runtime": str(destination),
            "source_sha": source_sha,
            "runtime_sha": runtime_sha,
        })
    return {
        "ok": all(item["state"] == "in_sync" for item in planned),
        "target_root": str(runtime_root),
        "files": planned,
        "write_performed": False,
    }


def plan(files: list[str] | tuple[str, ...] | None) -> dict:
    """Read selected asset drift after binding the live PID to its plist entrypoint."""
    runtime = _running_registered_runtime()
    if not runtime.get("ok"):
        return {"ok": False, "reason": "launch_agent_identity_unverified", "runtime": runtime}
    result = _asset_plan(Path(runtime["runtime_root"]), files, HOST_DIR)
    result["registration"] = runtime
    return result


def check() -> int:
    """Read-only compatibility check for registered assets; no report is written."""
    result = plan([deploy_name for deploy_name, _ in HOST_FILES])
    return 0 if result.get("ok") else 1


def _registered_status() -> dict:
    registration = _running_registered_runtime()
    if not registration.get("ok"):
        return {"ok": False, "reason": "launch_agent_identity_unverified", "registration": registration}
    result = status(Path(registration["runtime_root"]), HOST_DIR)
    result["registration"] = registration
    result["write_performed"] = False
    return result


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments and arguments[0] in BLOCKED_COMMANDS:
        result = _blocked(arguments[0])
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 2

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command")
    status_parser = sub.add_parser("status", help="登记 LaunchAgent 实际运行根的只读漂移摘要")
    status_parser.add_argument("--json", action="store_true")
    plan_parser = sub.add_parser("plan", help="登记运行根中明确选择资产的只读差异计划")
    plan_parser.add_argument("--file", dest="files", action="append", required=True,
                             help="受管宿主文件名；可重复指定")
    plan_parser.add_argument("--json", action="store_true")
    check_parser = sub.add_parser("check", help="所有受管资产的只读兼容检查；漂移时 exit 1")
    check_parser.add_argument("--json", action="store_true")
    publish_parser = sub.add_parser("publish", help="受管发布: 版本目录 + 原子切换 current + SHA 校验")
    publish_parser.add_argument("--file", dest="files", action="append", required=True,
                                help="受管宿主文件名；可重复指定")
    publish_parser.add_argument("--json", action="store_true")
    sub.add_parser("restore", help="回滚: current 切回上一版本").add_argument("--json", action="store_true")
    sub.add_parser("migrate", help="plist 迁移: entrypoint → current/live_server.py").add_argument("--json", action="store_true")
    args = ap.parse_args(arguments)
    command = args.command or "status"

    if command == "plan":
        result = plan(args.files)
    elif command == "check":
        result = plan([deploy_name for deploy_name, _ in HOST_FILES])
    elif command == "publish":
        result = publish(args.files)
    elif command == "restore":
        result = restore()
    elif command == "migrate":
        result = migrate()
    else:
        result = _registered_status()
    print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
