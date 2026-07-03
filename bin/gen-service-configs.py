#!/usr/bin/env python3
"""gen-service-configs — 从 services.yaml 生成调度配置 (launchd plist).

理想态调度契约 (P73 + governance-ssot-edit skill): plist 由注册生成, 不手写.
稳定锚点 (interpreter=stable-python3 → shutil.which) 杜绝 uv 临时路径炸弹.

用法:
  python3 bin/gen-service-configs.py              # dry-run 打印 plist
  python3 bin/gen-service-configs.py --write      # 生成写盘
  python3 bin/gen-service-configs.py --check      # drift 检测 (plist vs services.yaml)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parent.parent
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"


def _stable_python3() -> str:
    return shutil.which("python3") or "/opt/homebrew/bin/python3"


INTERPRETERS = {"stable-python3": _stable_python3}


def load_services() -> list[dict]:
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    return (docs[-1] if docs else {}).get("services", []) or []


def resolve_interpreter(spec: str) -> str:
    interp = INTERPRETERS[spec]() if spec in INTERPRETERS else spec
    # 校验禁 uv 临时路径 (治 P2 + uv run 时 shutil.which 返回 .tmp 的坑 — PR#77 不彻底)
    if ".cache/uv/builds" in interp or "/.tmp" in interp:
        raise ValueError(f"interpreter 含 uv 临时路径 (禁, uv GC 后失效): {interp}")
    return interp


def gen_launchd_plist(svc: dict) -> str:
    label = svc["label"]
    interp = resolve_interpreter(svc["program"]["interpreter"])
    entry = str(WORKSPACE / svc["program"]["entrypoint"])
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
        report = {"ok": not violations, "violation_count": len(violations), "violations": violations}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    launchd_dir = Path.home() / "Library" / "LaunchAgents"
    drifts: list[str] = []
    for svc in services:
        if not svc.get("enabled", True) or svc.get("scheduler") != "launchd":
            continue
        plist = gen_launchd_plist(svc)
        target = launchd_dir / f"{svc['label']}.plist"
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
