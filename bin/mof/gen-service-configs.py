#!/usr/bin/env python3
"""gen-service-configs — 从 services.yaml 生成调度配置 (launchd plist).

理想态调度契约 (P73 + governance-ssot-edit skill): plist 由注册生成, 不手写.
稳定锚点 (interpreter=stable-python3 → shutil.which) 杜绝 uv 临时路径炸弹.

用法:
  python3 bin/mof/gen-service-configs.py              # dry-run 打印 plist
  python3 bin/mof/gen-service-configs.py --write      # 生成写盘
  python3 bin/mof/gen-service-configs.py --check      # drift 检测 (plist vs services.yaml)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import yaml

def _canonical_workspace() -> Path:
    """本工具写的是机器级配置(~/Library/LaunchAgents), 必须锚定规范检出。

    2026-08-08 事故: 原实现用 parents[2], 于是在哪个 worktree 里跑就把 plist
    里的路径写成那个 worktree 的。多个 agent 在各自 worktree 触发后, omlx 网关 /
    autopilot / agora / cockpit 七个 plist 的程序路径先后被改写成
    ws-mass-deletion-gate、ws-observability-impl…… 全部失效。
    worktree 是临时的, 机器级配置不能指向它。
    """
    env = os.environ.get("OMOSTATION_ROOT")
    if env and (Path(env) / "docs" / "project-registry.yaml").is_file():
        return Path(env)
    canonical = Path.home() / "Workspace"
    if (canonical / "docs" / "project-registry.yaml").is_file():
        return canonical
    return Path(__file__).resolve().parents[2]


WORKSPACE = _canonical_workspace()
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"


def _stable_python3() -> str:
    import os
    for path in os.environ.get("PATH", "").split(os.pathsep):
        if ".cache/uv" in path or "/.tmp" in path:
            continue
        p = shutil.which("python3", path=path)
        if p and not (".cache/uv" in p or "/.tmp" in p):
            return p
    return "/opt/homebrew/bin/python3"


INTERPRETERS = {"stable-python3": _stable_python3}


def load_services() -> list[dict]:
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    return (docs[-1] if docs else {}).get("services", []) or []


def _resolve_path(p: str) -> str:
    """~ 展开、绝对路径原样、其余相对 WORKSPACE。

    原实现无条件 `WORKSPACE / p`, 于是 "~/.local/bin/x" 变成
    "<workspace>/~/.local/bin/x" —— 带字面量 ~ 的死路径。
    """
    p = str(p)
    if p.startswith("~"):
        return str(Path(p).expanduser())
    if p.startswith("/"):
        return p
    return str(WORKSPACE / p)


def resolve_interpreter(spec: str) -> str:
    if spec in INTERPRETERS:
        interp = INTERPRETERS[spec]()
    elif spec.startswith("/") or spec.startswith("~"):
        interp = str(Path(spec).expanduser())
    else:
        # 未知别名原样落进 ProgramArguments[0] 会生成 "shell"、"uv" 这种
        # 不存在的程序名, launchd 静默起不来。宁可在生成期炸, 不要写坏 plist。
        resolved = shutil.which(spec)
        if not resolved:
            raise ValueError(
                f"未知 interpreter {spec!r} — 请用 {sorted(INTERPRETERS)} "
                f"或绝对路径 (services.yaml 里写 shell/uv 这类别名不受支持)"
            )
        interp = resolved
    # 校验禁 uv 临时路径 (治 P2 + uv run 时 shutil.which 返回 .tmp 的坑 — PR#77 不彻底)
    if ".cache/uv/builds" in interp or "/.tmp" in interp:
        raise ValueError(f"interpreter 含 uv 临时路径 (禁, uv GC 后失效): {interp}")
    return interp


def _plist_program_args(plist_xml: str) -> list[str]:
    """从生成的 plist XML 里取 ProgramArguments 的字符串项(用于写盘前自检)。"""
    import re

    m = re.search(r"<key>ProgramArguments</key>\s*<array>(.*?)</array>", plist_xml, re.S)
    if not m:
        return []
    return re.findall(r"<string>(.*?)</string>", m.group(1), re.S)


def gen_launchd_plist(svc: dict) -> str:
    label = svc["label"]
    interp = resolve_interpreter(svc["program"]["interpreter"])
    entry = _resolve_path(svc["program"]["entrypoint"])
    args = [interp, entry, *svc["program"].get("args", [])]
    prog_xml = "".join(f"        <string>{a}</string>\n" for a in args)
    watch = svc.get("watch_paths", [])
    watch_xml = "".join(f"        <string>{WORKSPACE / w}</string>\n" for w in watch)
    env = svc.get("environment", {})
    env_xml = ""
    if env:
        items = "".join(f"        <key>{k}</key>\n        <string>{v}</string>\n" for k, v in env.items())
        env_xml = f"    <key>EnvironmentVariables</key>\n    <dict>\n{items}    </dict>\n"
    res = svc.get("resilience", {})
    keepalive_xml = ""
    if res.get("keepalive") == "crashed":
        keepalive_xml = "    <key>KeepAlive</key>\n    <dict>\n        <key>Crashed</key>\n        <true/>\n    </dict>\n"
    throttle = res.get("throttle_interval")
    throttle_xml = f"    <key>ThrottleInterval</key>\n    <integer>{throttle}</integer>\n" if throttle else ""
    run_at_load_xml = "    <key>RunAtLoad</key>\n    <true/>\n" if svc.get("run_at_load") else ""
    out = svc.get("outputs", {})
    stdout_xml = f"    <key>StandardOutPath</key>\n    <string>{WORKSPACE / out['stdout']}</string>\n" if out.get("stdout") else ""
    stderr_xml = f"    <key>StandardErrorPath</key>\n    <string>{WORKSPACE / out['stderr']}</string>\n" if out.get("stderr") else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        "<plist version=\"1.0\">\n<dict>\n"
        f"    <key>Label</key>\n    <string>{label}</string>\n"
        "    <key>ProgramArguments</key>\n    <array>\n"
        f"{prog_xml}    </array>\n"
        + (f"    <key>WatchPaths</key>\n    <array>\n{watch_xml}    </array>\n" if watch else "")
        + env_xml + keepalive_xml + throttle_xml + run_at_load_xml + stdout_xml + stderr_xml
        + "</dict>\n</plist>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true", help="JSON 输出 (--check/--validate)")
    parser.add_argument("--validate", action="store_true", help="验注册自洽 (CI, 不依赖本机 plist)")
    args = parser.parse_args()
    if not REGISTRY.exists():
        print(f"❌ 注册不存在: {REGISTRY}", file=sys.stderr)
        return 1
    services = load_services()
    if args.validate:
        # 验注册自洽 (CI 可验, 不依赖本机 plist). 治 service-config-drift gate 在 CI 无本机 plist 的设计问题.
        violations: list[str] = []
        for svc in services:
            if not svc.get("enabled", True):
                continue
            try:
                resolve_interpreter(svc.get("program", {}).get("interpreter", ""))
            except ValueError as e:
                violations.append(f"{svc.get('id', '?')}: {e}")
            for f in ("id", "scheduler"):
                if not svc.get(f):
                    violations.append(f"service 缺必填 {f}")
            # GHA 调度验 schedule_ref 存在 (治 P4 元递归全覆盖 — 引导扇区 GHA 声明可证, CI 可验仓库内)
            if svc.get("scheduler") == "gha":
                sched_ref = svc.get("schedule_ref")
                if not sched_ref:
                    violations.append(f"{svc.get('id', '?')}: gha 调度缺 schedule_ref")
                elif not (WORKSPACE / sched_ref).is_file():
                    violations.append(f"{svc.get('id', '?')}: schedule_ref 不存在 {sched_ref}")
        report = {"ok": not violations, "violation_count": len(violations), "violations": violations}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    launchd_dir = Path.home() / "Library" / "LaunchAgents"
    drifts: list[str] = []
    bad_services: list[str] = []
    for svc in services:
        if not svc.get("enabled", True) or svc.get("scheduler") != "launchd":
            continue
        # generate: false —— 注册表只"记录"这个服务的生命周期(供 wsvc 观测),
        # plist 的源头在别处(如 ~/omlx-orchestration/launchd/)。不声明这一点,
        # 生成器会拿注册表里的简化描述去覆盖手写 plist —— 2026-08-08 就是这样
        # 把 omlx 网关等 7 个 plist 写成了死路径。
        if not svc.get("generate", True):
            continue
        try:
            plist = gen_launchd_plist(svc)
        except ValueError as exc:
            print(f"❌ {svc.get('label', svc.get('id', '?'))}: {exc}", file=sys.stderr)
            bad_services.append(str(exc))
            continue
        target = launchd_dir / f"{svc['label']}.plist"

        # 生成期最后一道: 程序路径不存在就不写。写进去的是"看着已登记、
        # 实际起不来"的 plist, 比不写更糟 —— 出事时没人会去核对路径。
        missing = [a for a in _plist_program_args(plist)
                   if a.startswith("/") and not Path(a).exists()]
        if missing:
            print(f"❌ {svc['label']}: 程序路径不存在 {missing} — 拒绝写入", file=sys.stderr)
            bad_services.append(f"{svc['label']}: {missing}")
            continue

        if args.write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(plist, encoding="utf-8")  # audit-exempt: non-atomic-write (plist 写 ~/Library/LaunchAgents, 非 .omo state plane)
            print(f"✅ 生成 {target}")
        elif args.check:
            existing = target.read_text(encoding="utf-8") if target.exists() else ""
            if existing.strip() != plist.strip():
                drifts.append(f"{svc['label']}: plist 与 services.yaml 不一致 (drift)")
        else:
            print(f"--- {svc['label']} ---")
            print(plist)
    if args.check:
        if args.json:
            report = {"ok": not drifts, "drift_count": len(drifts), "drifts": drifts}
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["ok"] else 1
        if drifts:
            print(f"❌ {len(drifts)} drift:")
            for d in drifts:
                print(f"  - {d}")
            return 1
        launchd_count = sum(1 for s in services if s.get("scheduler") == "launchd")
        print(f"✅ 0 drift ({launchd_count} launchd services)")
    if bad_services:
        print(f"\n❌ {len(bad_services)} 个服务未生成(路径/interpreter 有问题):", file=sys.stderr)
        for b in bad_services:
            print(f"  - {b}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
