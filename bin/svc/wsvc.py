#!/usr/bin/env python3
"""wsvc — workspace 服务控制面 CLI(与 cockpit /api/svc/* 同一引擎)。

  wsvc ls [--profile P]      全服务统一视图(launchd + docker + 计数)
  wsvc ports                 端口体检:未登记 / 僵尸 / 冲突
  wsvc up|down <服务id>       起停单个(launchd 或 docker:名字)
  wsvc profile <名> up|down   按场景批量(minimal / dev / data)
  wsvc doctor                巡检:常驻是否在 + 端口冲突 + 未登记

设计:状态全实时探活,不落库;起停仍交给 launchd/docker,本工具不做守护进程。
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import service_view as sv


def _c(s: str, col: str) -> str:
    codes = {"g": 32, "r": 31, "y": 33, "d": 90, "b": 1, "c": 36}
    return f"\033[{codes.get(col, 0)}m{s}\033[0m"


def cmd_ls(args) -> int:
    v = sv.collect()
    c = v["counts"]
    print(_c("● 全服务视图", "b"))
    for s in v["services"]:
        if args.profile and args.profile not in s.get("profiles", []):
            continue
        mark = _c("●", "g") if s["running"] else _c("○", "d")
        tags = []
        if s.get("resident"):
            tags.append(_c("常驻", "y"))
        if s.get("profiles"):
            tags.append(_c(",".join(s["profiles"]), "c"))
        if s.get("interval"):
            tags.append(_c(f"每{s['interval']}s", "d"))
        extra = f" ports={s['ports']}" if s.get("ports") else ""
        print(f"  {mark} {s['id']:<44} {s['kind']:<8} {' '.join(tags)}{_c(extra,'d')}")
    print()
    print(_c("● 统计", "b"))
    print(f"  launchd {c['launchd_running']}/{c['launchd']} 在跑 · "
          f"docker {c['docker_running']}/{c['docker']} 在跑")
    print(f"  BOS 能力 {c['bos_capabilities']} · 代码能力 {c['code_capabilities']} · "
          f"端口 登记{c['ports_registered']}/在跑{c['ports_live']}")
    print(_c(f"  profile: {' · '.join(v['profiles'])}   (wsvc profile <名> up)", "d"))
    return 0


def cmd_ports(args) -> int:
    v = sv.collect()
    p = v["ports"]
    print(_c("● 端口体检", "b"))
    print(f"  登记 {len(p['registered'])} · 实际在跑 {len(p['live'])}")
    if p["conflicts"]:
        print(_c(f"\n  ⚠️ 疑似冲突 {len(p['conflicts'])} 处(登记方 ≠ 实际占用方):", "r"))
        for x in p["conflicts"]:
            print(f"     :{x['port']:<6} 登记={x['registered']:<24} 实际={x['actual']}")
    if p["undocumented"]:
        print(_c(f"\n  ⚠️ 在跑但未登记 {len(p['undocumented'])} 个:", "y"))
        live = p["live"]
        for port in p["undocumented"][:20]:
            print(f"     :{port:<6} {live.get(str(port), '')}")
    print(_c(f"\n  ⚪ 登记但没跑: {len(p['stale'])} 个(正常:按需服务)", "d"))
    return 0


def cmd_action(args) -> int:
    ok, msg = sv.service_action(args.id, args.action)
    print((_c("✅", "g") if ok else _c("❌", "r")) + f" {args.action} {args.id}")
    if msg:
        print(_c(f"   {msg}", "d"))
    return 0 if ok else 1


def cmd_profile(args) -> int:
    res = sv.profile_action(args.name, args.action)
    okc = sum(1 for r in res if r["ok"])
    print(_c(f"● profile {args.name} {args.action}", "b"))
    for r in res:
        print(("  " + _c("✅", "g") if r["ok"] else "  " + _c("❌", "r")) + f" {r['id']}")
        if r.get("msg") and not r["ok"]:
            print(_c(f"      {r['msg']}", "d"))
    print(f"  {okc}/{len(res)} 成功")
    return 0 if okc == len(res) else 1


def cmd_doctor(args) -> int:
    v = sv.collect()
    issues = []
    byid = {s["id"]: s for s in v["services"]}
    for rid in v["resident"]:
        s = byid.get(rid)
        if not s or not s["running"]:
            issues.append(("常驻服务未运行", rid))
    for x in v["ports"]["conflicts"]:
        issues.append(("端口冲突", f":{x['port']} 登记={x['registered']} 实际={x['actual']}"))
    n_undoc = len(v["ports"]["undocumented"])
    if n_undoc:
        issues.append(("端口未登记", f"{n_undoc} 个(wsvc ports 看详情)"))
    print(_c("● 巡检", "b"))
    if not issues:
        print(_c("  ✅ 全绿:常驻服务在跑、端口无冲突", "g"))
        return 0
    for kind, detail in issues:
        print(f"  {_c('⚠️','y')} {kind}: {detail}")
    print(_c(f"\n  共 {len(issues)} 项待处理", "y"))
    return 1



def cmd_adopt(args) -> int:
    """把"在跑但未登记"的端口登记进 port-registry(只登记 workspace 相关的)。"""
    import yaml
    v = sv.collect()
    live = v["ports"]["live"]
    undoc = v["ports"]["undocumented"]
    # 只收 workspace 生态的进程, 不碰 WeChat/ClashX 等第三方
    OURS = ("python", "uv", "node", "bun", "com.docke", "lm\\x20stu", "lmlink")
    cand = [(p, live.get(str(p), "")) for p in undoc
            if any(live.get(str(p), "").lower().startswith(o) for o in OURS)]
    if not cand:
        print(_c("没有需要登记的 workspace 端口", "g")); return 0
    print(_c(f"● 待登记 {len(cand)} 个(仅 workspace 生态):", "b"))
    for p, owner in cand:
        print(f"  :{p:<6} {owner}")
    if not args.apply:
        print(_c("\n预览。确认后: wsvc adopt --apply", "d")); return 0
    f = os.path.expanduser("~/Workspace/protocols/port-registry.yaml")
    with open(f) as fh:
        docs = [d for d in yaml.safe_load_all(fh) if d]
    body = docs[-1]
    for p, owner in cand:
        body.setdefault("ports", {})[p] = {
            "name": f"auto-{owner.lower().replace('\\x20','-')[:20]}-{p}",
            "transport": "http", "status": "active",
            "note": f"wsvc adopt 自动登记(实际占用: {owner})",
        }
    import shutil
    import time
    shutil.copy2(f, f + ".bak-adopt-" + time.strftime("%H%M%S"))
    with open(f, "w") as fh:
        if len(docs) > 1:
            yaml.safe_dump(docs[0], fh, allow_unicode=True, sort_keys=False)
            fh.write("---\n")
        yaml.safe_dump(body, fh, allow_unicode=True, sort_keys=False)
    print(_c(f"✅ 已登记 {len(cand)} 个端口", "g"))
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(
        prog="wsvc", description="workspace 服务控制面(与 cockpit /api/svc/* 同源)")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("ls", help="全服务视图")
    p.add_argument("--profile", help="只看某场景")
    sub.add_parser("ports", help="端口体检")
    for act in ("up", "down"):
        p = sub.add_parser(act, help=f"{act} 单个服务")
        p.add_argument("id")
        p.set_defaults(action=act)
    p = sub.add_parser("profile", help="按场景批量起停")
    p.add_argument("name")
    p.add_argument("action", choices=["up", "down"])
    sub.add_parser("doctor", help="巡检")
    p=sub.add_parser("adopt", help="把在跑但未登记的 workspace 端口登记进 registry"); p.add_argument("--apply",action="store_true")
    args = ap.parse_args()

    fn = {"ls": cmd_ls, "ports": cmd_ports, "up": cmd_action, "down": cmd_action,
          "profile": cmd_profile, "doctor": cmd_doctor, "adopt": cmd_adopt}.get(args.cmd)
    if not fn:
        ap.print_help()
        return 0
    return fn(args)


if __name__ == "__main__":
    sys.exit(main())
