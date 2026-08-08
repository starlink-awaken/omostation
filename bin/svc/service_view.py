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


# 个人域服务 —— 跑在这台机器上, 但不归 Workspace 管, 不要求登记 services.yaml。
# (判断依据: ProgramArguments 指向 Workspace 之外, 如 ~/Documents/@学习进化)
NON_WORKSPACE_SERVICES = {
    "com.learningevolution.concept-weave.monthly",
    "com.lifeos.pulse",
    "com.macpaw.CleanMyMac5.Updater",
    "com.user.cron-service",
    "homebrew.mxcl.neo4j",
    "homebrew.mxcl.postgresql@18",
}

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
            "watch_paths": [x.strip() for x in _sh(
                f'/usr/libexec/PlistBuddy -c "Print :WatchPaths" "{f}" 2>/dev/null'
            ).splitlines() if x.strip() and x.strip() not in ("Array {", "}")],
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


# ── BOS ↔ 服务 ↔ 端口 ↔ 能力 四方一致性 ──────────────────────────────
def sync_check() -> dict[str, Any]:
    """校验 BOS 能力注册与现实是否同步。

    检查项(均已排除误报,只报真问题):
      B1 internal    module_path 指向的模块文件是否存在
      B2 stdio/mcp_* command 里 --directory 的项目目录是否存在
      B3 http/proxy  是否声明端点(http_url/mcp_endpoint),端点端口是否已登记
      B4 kairon/gbrain 包是否在 projects-capabilities 登记(该表仅覆盖这两个项目)
      B6 URI 是否重复注册(路由不确定)
      S1 在跑的 launchd/docker 是否有 services.yaml 生命周期声明

    注:status=deprecated 是保留惯例(同 port-registry),只计数不报错。
    """
    bos = read_bos()
    caps = {c.get("id", "") for c in read_capabilities()}
    cap_pkgs = {c.split(".")[-1] for c in caps} | {c.split(".")[0] for c in caps}
    # id 与 label 都要收: services.yaml 用 id 命名(governance.watch),
    # 而 launchctl / plist 用 label(com.l4.governance.watch)。只比 id 会把
    # 已登记的服务误报成"无生命周期声明"。
    declared = set()
    for s in read_services_registry():
        for k in ("id", "label"):
            if s.get(k):
                declared.add(s[k])
    reg_ports = read_port_registry()
    projects_dir = os.path.join(WORKSPACE, "projects")
    project_names = [p for p in os.listdir(projects_dir)
                     if os.path.isdir(os.path.join(projects_dir, p))] \
        if os.path.isdir(projects_dir) else []

    issues: list[dict] = []
    deprecated_kept = 0

    for s in bos:
        uri = s.get("uri", "?")
        tr = s.get("transport", "?")

        if tr == "internal":
            mp = s.get("module_path", "")
            if mp:
                rel = mp.replace(".", "/") + ".py"
                found = False
                for p in project_names:
                    base = os.path.join(projects_dir, p)
                    if os.path.isfile(os.path.join(base, "src", rel)):
                        found = True
                        break
                    if glob.glob(os.path.join(base, "packages", "*", "src", rel)):
                        found = True
                        break
                if not found:
                    issues.append({"kind": "B1 internal 模块找不到", "uri": uri, "detail": mp})

        elif tr in ("stdio", "mcp_stdio", "mcp_proxy"):
            cmd = s.get("command") or []
            if isinstance(cmd, list) and "--directory" in cmd:
                i = cmd.index("--directory")
                if i + 1 < len(cmd) and not os.path.isdir(os.path.join(WORKSPACE, cmd[i + 1])):
                    issues.append({"kind": "B2 项目目录不存在", "uri": uri, "detail": cmd[i + 1]})

        if tr in ("http", "mcp_proxy"):
            ep = s.get("http_url") or s.get("mcp_endpoint") or s.get("endpoint") or ""
            if not ep:
                issues.append({"kind": "B3 未声明端点", "uri": uri,
                               "detail": "无 http_url/mcp_endpoint"})
            else:
                m = re.search(r":(\d{2,5})", str(ep))
                if m and int(m.group(1)) not in reg_ports:
                    issues.append({"kind": "B3 端点端口未登记", "uri": uri,
                                   "detail": f":{m.group(1)} 不在 port-registry"})

        pkg = s.get("package") or ""
        if any(pkg.startswith(x) for x in ("kairon", "gbrain")) \
                and pkg not in cap_pkgs and pkg.split("-")[0] not in cap_pkgs:
            issues.append({"kind": "B4 kairon/gbrain 包未登记", "uri": uri, "detail": pkg})

        if str(s.get("status", "")).lower() in ("deprecated", "inactive", "disabled"):
            deprecated_kept += 1

    # B6 URI 重复
    seen: dict[str, int] = {}
    for s in bos:
        u = s.get("uri", "")
        seen[u] = seen.get(u, 0) + 1
    for u, n in seen.items():
        if n > 1:
            issues.append({"kind": "B6 URI 重复注册", "uri": u, "detail": f"{n} 次"})

    # S1 在跑但无生命周期声明
    #
    # 只管 Workspace 自己的服务面。个人域的 LaunchAgent(程序在 ~/Documents 等
    # Workspace 之外)不该被要求登记进 Workspace 的 SSOT —— 否则这条检查会
    # 永远挂着几条改不掉的"问题", 久了就没人看了。
    for s in collect_launchd() + collect_docker():
        if s["id"] in NON_WORKSPACE_SERVICES:
            continue
        if s["running"] and not (s["id"] in declared or s.get("name") in declared):
            issues.append({"kind": "S1 在跑但无生命周期声明", "uri": s["id"],
                           "detail": f"{s['kind']} · 建议登记到 services.yaml"})

    by_kind: dict[str, int] = {}
    for i in issues:
        by_kind[i["kind"]] = by_kind.get(i["kind"], 0) + 1

    return {
        "total_bos": len(bos),
        "issues": issues,
        "by_kind": by_kind,
        "deprecated_kept": deprecated_kept,
        "ok": not issues,
    }


# ── 可观测性:健康三态 / 资源 / 日志 ──────────────────────────────────
def _launchd_detail(label: str) -> dict[str, Any]:
    """从 launchctl print 取 PID / 上次退出码 / 重启次数(存在性之外的真信息)。"""
    out = _sh(f"launchctl print gui/{os.getuid()}/{label} 2>/dev/null", 8)
    d: dict[str, Any] = {"pid": None, "last_exit": None, "runs": None}
    m = re.search(r"^\s*pid\s*=\s*(\d+)", out, re.MULTILINE)
    if m:
        d["pid"] = int(m.group(1))
    m = re.search(r"last exit code\s*=\s*(-?\d+)", out)
    if m:
        d["last_exit"] = int(m.group(1))
    m = re.search(r"runs\s*=\s*(\d+)", out)
    if m:
        d["runs"] = int(m.group(1))
    return d


def _proc_stats(pid: int | None) -> dict[str, Any]:
    """PID → CPU% / 内存GB。"""
    if not pid:
        return {"cpu": None, "mem_gb": None}
    out = _sh(f"ps -p {pid} -o %cpu=,rss= 2>/dev/null", 5).strip()
    if not out:
        return {"cpu": None, "mem_gb": None}
    parts = out.split()
    try:
        return {"cpu": float(parts[0]), "mem_gb": round(int(parts[1]) / 1048576, 2)}
    except (ValueError, IndexError):
        return {"cpu": None, "mem_gb": None}


def _log_paths(label: str) -> dict[str, str]:
    """服务日志路径(plist 的 StandardOut/ErrorPath)。"""
    p = os.path.join(HOME, "Library/LaunchAgents", f"{label}.plist")
    if not os.path.isfile(p):
        return {}
    out = {}
    for key, name in (("StandardOutPath", "stdout"), ("StandardErrorPath", "stderr")):
        v = _sh(f'/usr/libexec/PlistBuddy -c "Print :{key}" "{p}" 2>/dev/null', 5).strip()
        if v:
            out[name] = v
    return out


def probe_health(svc: dict) -> dict[str, Any]:
    """健康三态 —— 这是本轮核心:区分"进程在"与"服务可用"。

    healthy   已加载/运行,且(若声明端口)端口可连
    degraded  进程在但端口不通 / 上次异常退出 —— **看着在跑其实坏了**
    down      没运行
    """
    if not svc.get("running"):
        return {"health": "down", "reason": "未运行"}

    ports = svc.get("ports") or []
    if ports:
        bad = [p for p in ports if not port_open(p)]
        if bad:
            return {"health": "degraded", "reason": f"端口不通 {bad}"}

    if svc.get("kind") == "launchd":
        d = svc.get("detail") or {}
        exit_code = d.get("last_exit")
        # 退出码语义: 0 正常; 1-127 应用错误; >=128 被信号杀(SIGTERM=143, 重启常见)
        if isinstance(exit_code, int) and 0 < exit_code < 128:
            return {"health": "degraded", "reason": f"上次异常退出 code={exit_code}"}
        # watchpaths 型服务空闲时无进程是正常的, 不算病
        if d.get("pid") is None and svc.get("keepalive") and not svc.get("watch_paths"):
            return {"health": "degraded", "reason": "声明常驻但无进程"}
        # 监视路径失效 → watch 永远不触发(真问题, 今天实际发现)
        for wp in (svc.get("watch_paths") or []):
            if not os.path.exists(wp):
                return {"health": "degraded", "reason": f"监视路径不存在: {wp}"}

    return {"health": "healthy", "reason": ""}


def enrich(services: list[dict]) -> list[dict]:
    """给服务补上健康/资源/日志(collect 之后调用)。"""
    for s in services:
        if s["kind"] == "launchd":
            s["detail"] = _launchd_detail(s["id"])
            s["logs"] = _log_paths(s["id"])
            s.update(_proc_stats(s["detail"].get("pid")))
        elif s["kind"] == "docker":
            s["detail"] = {}
            s["logs"] = {"docker": f"docker logs {s.get('name', '')}"}
            s["cpu"] = None
            s["mem_gb"] = None
        s.update(probe_health(s))
    return services


def collect_full() -> dict[str, Any]:
    """collect() + 可观测性增强(健康三态/资源/日志)。"""
    v = collect()
    v["services"] = enrich(v["services"])
    hc: dict[str, int] = {}
    for s in v["services"]:
        hc[s["health"]] = hc.get(s["health"], 0) + 1
    v["health_counts"] = hc
    v["degraded"] = [
        {"id": s["id"], "kind": s["kind"], "reason": s["reason"]}
        for s in v["services"] if s["health"] == "degraded"
    ]
    return v
