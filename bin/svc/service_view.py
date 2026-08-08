#!/usr/bin/env python3
"""service_view — workspace 服务统一视图引擎(SSOT join + 实时探活)。

设计要点:
  * **不新建 SSOT**。join 四张已有注册表:
      - .omo/_truth/registry/services.yaml        生命周期(调度/常驻)
      - protocols/port-registry.yaml              端口
      - projects/agora/etc/bos-services.yaml      BOS 能力路由(204 条)
      - .omo/_truth/registry/projects-capabilities.yaml  代码包
  * **状态不落库**,全部实时探活(launchctl / docker / TCP),永不失真。
  * 被 `omo svc` CLI 与 cockpit /api/services/status 共用。

用法(库):
    from service_view import collect
    view = collect()
"""

from __future__ import annotations

import glob
import os
import re
import socket
import subprocess
from typing import Any

WORKSPACE = os.path.expanduser("~/Workspace")
HOME = os.path.expanduser("~")

# ── 场景 profile:解决“每次启动找不全” ────────────────────────────────
PROFILES: dict[str, list[str]] = {
    "minimal": ["com.omlx.gateway", "com.omlx.autostart", "com.omlx.autopilot"],
    "dev": ["com.omlx.gateway", "com.omlx.autostart", "com.omlx.autopilot",
            "com.agora.sse", "com.l4.governance.watch", "cockpit-dashboard"],
    "data": ["docker:observability-db-1", "docker:searxng",
             "homebrew.mxcl.neo4j", "homebrew.mxcl.postgresql@18"],
}

# 常驻集(autopilot 要保证活着的)
RESIDENT = ["com.omlx.gateway", "com.omlx.autostart", "com.omlx.autopilot"]


def _sh(cmd: str, timeout: int = 20) -> str:
    try:
        return subprocess.run(cmd, shell=True, capture_output=True,
                              text=True, timeout=timeout, check=False).stdout
    except (subprocess.SubprocessError, OSError):
        return ""   # 探活失败视为不可用, 不中断整体采集


def _yaml_last_doc(path: str) -> Any:
    """读多文档 YAML(带 front-matter)的正文。"""
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            docs = [d for d in yaml.safe_load_all(fh) if d]
        return docs[-1] if docs else {}
    except (OSError, ValueError, ImportError):
        return {}   # 注册表缺失/损坏时降级为空, 不影响其它数据源


def port_open(port: int, host: str = "127.0.0.1", t: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=t):
            return True
    except OSError:
        return False


# ── 采集各形态 ───────────────────────────────────────────────────────
def collect_launchd() -> list[dict]:
    loaded = _sh("launchctl list")
    out = []
    for f in sorted(glob.glob(os.path.join(HOME, "Library/LaunchAgents/*.plist"))):
        label = os.path.basename(f)[:-6]

        def pb(key: str, _f: str = f) -> str:
            return _sh(f'/usr/libexec/PlistBuddy -c "Print :{key}" "{_f}" 2>/dev/null').strip()

        out.append({
            "id": label,
            "kind": "launchd",
            "running": bool(re.search(rf"\t{re.escape(label)}$", loaded, re.MULTILINE)),
            "run_at_load": pb("RunAtLoad") == "true",
            "interval": pb("StartInterval") or None,
            "keepalive": bool(pb("KeepAlive")),
            "program": os.path.basename(pb("ProgramArguments:0") or pb("Program") or ""),
            "resident": label in RESIDENT,
        })
    return out


def collect_docker() -> list[dict]:
    out = []
    raw = _sh('/opt/homebrew/bin/docker ps -a '
              '--format "{{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.State}}"', 30)
    for line in raw.strip().splitlines():
        p = line.split("\t")
        if len(p) < 4:
            continue
        ports = sorted({int(x) for x in re.findall(r":(\d+)->", p[2])})
        out.append({
            "id": f"docker:{p[0]}",
            "kind": "docker",
            "name": p[0],
            "image": p[1],
            "ports": ports,
            "running": p[3] == "running",
            "resident": False,
        })
    return out


def collect_listening() -> dict[int, str]:
    """端口 → 占用进程名。"""
    live: dict[int, str] = {}
    for line in _sh("lsof -nP -iTCP -sTCP:LISTEN").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 9:
            m = re.search(r":(\d+)$", parts[8])
            if m:
                live.setdefault(int(m.group(1)), parts[0])
    return live


# ── 读注册表 ─────────────────────────────────────────────────────────
def read_port_registry() -> dict[int, str]:
    d = _yaml_last_doc(os.path.join(WORKSPACE, "protocols/port-registry.yaml"))
    out: dict[int, str] = {}
    for p, v in (d.get("ports") or {}).items():
        try:
            out[int(p)] = v.get("name") if isinstance(v, dict) else str(v)
        except (TypeError, ValueError):
            continue   # 端口键非整数(注释行等), 跳过
    return out


def read_services_registry() -> list[dict]:
    d = _yaml_last_doc(os.path.join(WORKSPACE, ".omo/_truth/registry/services.yaml"))
    return d.get("services") or []


def read_bos() -> list[dict]:
    d = _yaml_last_doc(os.path.join(WORKSPACE, "projects/agora/etc/bos-services.yaml"))
    s = d.get("services") or []
    return s if isinstance(s, list) else [{"uri": k, **(v or {})} for k, v in s.items()]


def read_capabilities() -> list[dict]:
    d = _yaml_last_doc(os.path.join(WORKSPACE, ".omo/_truth/registry/projects-capabilities.yaml"))
    return d.get("capabilities") or []


# ── 统一视图 ─────────────────────────────────────────────────────────
def collect() -> dict[str, Any]:
    agents = collect_launchd()
    dockers = collect_docker()
    live = collect_listening()
    reg_ports = read_port_registry()
    declared = {s.get("id"): s for s in read_services_registry()}
    bos = read_bos()
    caps = read_capabilities()

    services = agents + dockers
    for s in services:
        s["declared"] = s["id"] in declared or s.get("name") in declared
        s["profiles"] = [p for p, ids in PROFILES.items() if s["id"] in ids]

    # 端口一致性
    undocumented = sorted(p for p in live if p not in reg_ports and 1024 < p < 65535)
    stale = sorted(p for p in reg_ports if p not in live)
    # 通用运行时:进程名无法反推服务身份(python/node/uv 都可能是任何服务), 不判冲突
    GENERIC = ("python", "node", "uv", "bun", "ruby", "java", "deno", "electron")
    # 已知别名:登记名 与 实际进程名 的合法对应
    ALIAS = {"chrome-cdp-debug": ("google", "chrome"), "ollama": ("ollama",)}
    conflicts = []
    for p, owner in live.items():
        exp = reg_ports.get(p)
        if not exp or not owner:
            continue
        ow = owner.lower()
        if any(ow.startswith(g) for g in GENERIC):
            continue                       # 通用运行时 → 无法判定, 跳过
        if any(a in ow for a in ALIAS.get(exp, ())):
            continue                       # 已知合法别名
        if exp.split("-")[0].lower() in ow:
            continue                       # 名字对得上
        conflicts.append({"port": p, "registered": exp, "actual": owner})

    return {
        "services": services,
        "counts": {
            "launchd": len(agents),
            "launchd_running": sum(1 for a in agents if a["running"]),
            "docker": len(dockers),
            "docker_running": sum(1 for d in dockers if d["running"]),
            "bos_capabilities": len(bos),
            "code_capabilities": len(caps),
            "ports_registered": len(reg_ports),
            "ports_live": len(live),
        },
        "ports": {
            "live": {str(k): v for k, v in sorted(live.items())},
            "registered": {str(k): v for k, v in sorted(reg_ports.items())},
            "undocumented": undocumented,
            "stale": stale,
            "conflicts": conflicts,
        },
        "profiles": PROFILES,
        "resident": RESIDENT,
    }


# ── 控制动作 ─────────────────────────────────────────────────────────
def service_action(sid: str, action: str) -> tuple[bool, str]:
    """起停服务。action: up | down"""
    uid = os.getuid()
    if sid.startswith("docker:"):
        name = sid.split(":", 1)[1]
        cmd = f'/opt/homebrew/bin/docker {"start" if action == "up" else "stop"} {name}'
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=90, check=False)
        return r.returncode == 0, (r.stdout or r.stderr).strip()[-200:]
    plist = os.path.join(HOME, "Library/LaunchAgents", f"{sid}.plist")
    if not os.path.exists(plist):
        return False, f"找不到 {plist}"
    if action == "up":
        cmd = f'launchctl bootstrap gui/{uid} "{plist}"'
    else:
        cmd = f"launchctl bootout gui/{uid}/{sid}"
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       timeout=60, check=False)
    ok = r.returncode == 0 or "already" in (r.stderr or "").lower()
    return ok, (r.stdout or r.stderr).strip()[-200:]


def profile_action(profile: str, action: str) -> list[dict]:
    ids = PROFILES.get(profile)
    if not ids:
        return [{"id": "-", "ok": False, "msg": f"未知 profile: {profile}"}]
    out = []
    for sid in ids:
        ok, msg = service_action(sid, action)
        out.append({"id": sid, "ok": ok, "msg": msg})
    return out
