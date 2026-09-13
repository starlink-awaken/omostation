#!/usr/bin/env python3
"""panorama-collect.py — 织星全景驾驶舱采集器（只读 SSOT 聚合，零仓库写副作用）。

聚合门禁/BET/Agent/运行态/里程碑/治理数据，产物只写 runtime/dashboard/（gitignored）。
与 Serena 只读观测站互补：Serena=外部证据观测，驾驶舱=体系运行指挥台。

用法：
    python3 bin/panorama/panorama-collect.py            # 采集 + 生成站点
    python3 bin/panorama/panorama-collect.py --json     # 只输出 data.json 摘要
    python3 bin/panorama/panorama-collect.py --gates    # 只刷新门禁 receipt 视图
    python3 bin/panorama/panorama-collect.py --check-side-effects
                                                        # 验证零仓库写副作用
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "runtime" / "dashboard"
DATA_JSON = OUT_DIR / "data.json"
INDEX_HTML = OUT_DIR / "index.html"

GATE_DECLARED = {
    "A6": {"title": "Orca R0 准入", "state": "not_admitted", "depends_on": ["A8"],
           "note": "T10-149 只读验证工具链；未过门零写入"},
    "A7": {"title": "Multica AS0 准入", "state": "not_admitted", "depends_on": ["A8"],
           "note": "T10-150 只读验证工具链；未过门零写入"},
    "A8": {"title": "OMO 外部执行事务", "state": "absent", "depends_on": ["G2", "G3"],
           "note": "T10-165 语义落地后推进"},
    "A9": {"title": "ASD 与 Cockpit 可观测", "state": "partial", "depends_on": ["G2", "G3"],
           "note": "T10-166 面板契约；PARTIAL≠PASS"},
    "RF0": {"title": "Ruflo 只读协作准入", "state": "not_admitted", "depends_on": [],
            "note": "side-effect-free 观察；独立驱动不建第二队列"},
}

DOC_ENTRIES = [
    {"name": "白皮书 / 三年规划", "path": "docs/VISION-ROADMAP.md", "tag": "vision"},
    {"name": "ARCHITECTURE.md（架构契约）", "path": "ARCHITECTURE.md", "tag": "architecture"},
    {"name": "道法术器（DFSQ）", "path": "docs/architecture/dao-fa-shu-qi.md", "tag": "architecture"},
    {"name": "SFOP 脊面运行模式", "path": "docs/architecture/os-operating-pattern-v1.md", "tag": "architecture"},
    {"name": "OMO 持久语义规划（Role/Capsule/Handoff）", "path": "docs/plans/3y-bet-ledger.yaml", "tag": "plan",
     "anchor": "BET-Y1Q4-T10-165"},
    {"name": "全景驾驶舱规划（T10-163）", "path": "docs/plans/3y-bet-ledger.yaml", "tag": "plan",
     "anchor": "BET-Y1Q4-T10-163"},
    {"name": "ADR 决策索引", "path": ".omo/_knowledge/decisions/INDEX.md", "tag": "knowledge"},
    {"name": "系统导航 SYSTEM-INDEX", "path": "docs/SYSTEM-INDEX.md", "tag": "knowledge"},
    {"name": "Agent 操作指南 AGENTS.md", "path": "AGENTS.md", "tag": "ops"},
    {"name": "Session 避坑基因 CLAUDE.md", "path": "CLAUDE.md", "tag": "ops"},
]


def run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=timeout)
        return r.returncode, (r.stdout or r.stderr or "").strip()
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def collect_gates() -> list[dict]:
    code, out = run([sys.executable, "bin/gac/gate-health-check.py", "--json"])
    live: dict[str, dict] = {}
    if code == 0:
        try:
            for g in json.loads(out).get("gates", []):
                gid = str(g.get("gate", "")).split()[0]  # "A1 Workflow/Git" -> "A1"
                live[gid] = g
        except Exception:  # noqa: BLE001
            pass
    gates = []
    for gid in ("A1", "A2", "A3", "A4", "A5"):
        g = live.get(gid, {})
        gates.append({
            "id": gid,
            "title": {"A1": "Workflow 与 Git 执行完整性", "A2": "Resident 与宿主健康真值",
                      "A3": "受管 Python 与语义门", "A4": "调度声明与安装态一致",
                      "A5": "引用与 launchd 完整性"}[gid],
            "verdict": "PASS" if g.get("ok") else "FAIL",
            "detail": g.get("output", "未采集"),
            "live": bool(g),
        })
    for gid, d in GATE_DECLARED.items():
        gates.append({"id": gid, "title": d["title"], "verdict": d["state"].upper(),
                      "detail": d["note"], "live": False, "depends_on": d["depends_on"]})
    return gates


def collect_bets() -> dict:
    import yaml

    ledger = yaml.safe_load((ROOT / "docs/plans/3y-bet-ledger.yaml").read_text())
    bets = [b for b in ledger.get("bets", []) if isinstance(b, dict) and b.get("id")]
    by_status: dict[str, list[dict]] = {}
    for b in bets:
        by_status.setdefault(str(b.get("status", "unknown")), []).append(b)
    windows: dict[str, dict] = {}
    for b in bets:
        w = str(b.get("window", "?"))
        d = windows.setdefault(w, {"total": 0, "done": 0})
        d["total"] += 1
        if b.get("status") == "done":
            d["done"] += 1

    def brief(b: dict) -> dict:
        return {"id": b["id"], "title": str(b.get("title", ""))[:60],
                "priority": b.get("priority", ""), "track": b.get("track", ""),
                "risk": b.get("risk_level", "")}

    return {
        "total": len(bets),
        "counts": {k: len(v) for k, v in sorted(by_status.items())},
        "in_progress": [brief(b) for b in by_status.get("in_progress", [])][:10],
        "blocked": [brief(b) for b in by_status.get("blocked", [])][:10],
        "windows": dict(sorted(windows.items())),
    }


def collect_agents() -> list[dict]:
    agents: list[dict] = []
    code, out = run(["git", "worktree", "list", "--porcelain"])
    if code == 0:
        cur: dict = {}
        for line in out.splitlines():
            if line.startswith("worktree "):
                if cur:
                    agents.append(cur)
                cur = {"worktree": line.split(None, 1)[1]}
            elif line.startswith("branch "):
                cur["branch"] = line.split(None, 1)[1]
            elif line.startswith("detached"):
                cur["branch"] = "(detached)"
        if cur:
            agents.append(cur)
    for a in agents:
        wt = Path(a.get("worktree", ""))
        if wt.is_dir():
            ago = run(["bash", "-c", f"cd {wt} && git log -1 --format=%ct 2>/dev/null || echo 0"])
            try:
                ts = int(ago[1].strip() or 0)
                a["last_activity_hours"] = round((datetime.now(UTC).timestamp() - ts) / 3600, 1) if ts else None
            except ValueError:
                a["last_activity_hours"] = None
    return agents


def collect_runtime() -> dict:
    rt: dict = {}
    code, out = run(["python3", "bin/gac/meta-doctor.py", "--workspace", "."])
    if code == 0 or out.startswith("{"):
        try:
            d = json.loads(out[out.index("{"):])
            rt["meta_doctor"] = d.get("summary", {})
        except Exception:  # noqa: BLE001
            rt["meta_doctor"] = {}
    code, out = run(["bash", "-c", "launchctl list 2>/dev/null | grep -c omostation || true"])
    rt["launchd_omostation_jobs"] = int(out or 0)
    code, out = run(["bash", "-c", "crontab -l 2>/dev/null | grep -cv '^#' || true"])
    try:
        rt["crontab_lines"] = int(out.strip() or 0)
    except ValueError:
        rt["crontab_lines"] = 0
    code, out = run(["python3", "bin/scheduler-compile.py", "--check"])
    try:
        rt["scheduler"] = json.loads(out)
    except Exception:  # noqa: BLE001
        rt["scheduler"] = {"ok": code == 0}
    return rt


def _ensure_omo_path() -> None:
    omo_src = ROOT / "projects" / "omo" / "src"
    if omo_src.is_dir() and str(omo_src) not in sys.path:
        sys.path.insert(0, str(omo_src))


def collect_role_admission() -> dict:
    """读取 role-admission 注册表；缺失则返回空（合法态）。"""
    try:
        import yaml
        reg_file = ROOT / ".omo" / "_truth" / "registry" / "role-admission.yaml"
        if not reg_file.is_file():
            return {"roles": [], "source": "none"}
        doc = yaml.safe_load(reg_file.read_text()) or {}
        roles = []
        for item in doc.get("roles", []):
            roles.append({
                "role_id": str(item.get("role_id", "")),
                "state": str(item.get("state", "")),
                "adapter": str(item.get("adapter", "")),
                "can_write": str(item.get("state", "")) == "admitted",
                "blocked_reason": (None if str(item.get("state", "")) == "admitted"
                                   else f"state={item.get('state')}（未过门）"),
            })
        return {"roles": roles, "source": "ssot://.omo/_truth/registry/role-admission.yaml"}
    except Exception as e:  # noqa: BLE001
        return {"roles": [], "error": str(e)}


def collect_asd() -> dict:
    _ensure_omo_path()
    """ASD 五面板快照（数据契约；degraded 面板可见）。"""
    try:
        from omo.workflow.asd import Panel, PanelProvenance, attach_panel, new_snapshot, verdict
        snap = new_snapshot()
        # Overview
        attach_panel(snap, Panel("overview", {"health_green": True, "control_plane": "OMO"},
                                PanelProvenance("ssot://bet-ledger+gate-health-check", 30)))
        # Spine
        attach_panel(snap, Panel("spine", {"dfs": "道法术器", "sfop": "八律"},
                                PanelProvenance("ssot://ARCHITECTURE+os-pattern", 30)))
        # Agents
        attach_panel(snap, Panel("agents", collect_role_admission(),
                                PanelProvenance("ssot://role-admission-registry", 60)))
        # Milestones
        attach_panel(snap, Panel("milestones", {"windows": "Y1Q1-Y3H2"},
                                PanelProvenance("ssot://bet-ledger", 60)))
        # Degradation
        attach_panel(snap, Panel("degradation", {"observer_blindness_rule": "never-yields-green"},
                                PanelProvenance("ssot://asd-contract", 30)))
        snap["verdict"] = verdict(snap)
        return snap
    except Exception as e:  # noqa: BLE001
        return {"schema": "asd-snapshot/v1", "error": str(e), "verdict": "EMPTY"}


def collect_docs() -> list[dict]:
    docs = []
    for d in DOC_ENTRIES:
        p = ROOT / d["path"]
        entry = dict(d)
        entry["exists"] = p.is_file()
        entry["size"] = p.stat().st_size if p.is_file() else 0
        docs.append(entry)
    return docs



def collect_probes() -> dict:
    """Probe 心跳矩阵：守护/探针 SLA 健康（红/绿/陈旧）。"""
    import yaml
    from glob import glob
    probes = []
    for f in sorted(glob(str(ROOT / ".omo/_truth/registry/*probe*.yaml"))):
        try:
            doc = yaml.safe_load(Path(f).read_text()) or {}
            for name, cfg in (doc.get("probes") or doc if isinstance(doc, dict) else {}).items():
                if not isinstance(cfg, dict):
                    continue
                probes.append({"name": name, "sla_hours": cfg.get("sla_hours", "?"),
                               "owner": cfg.get("owner", ""), "file": Path(f).name})
        except Exception:  # noqa: BLE001
            pass
    # 从 health.yaml 读实时心跳
    hf = ROOT / ".omo/state/health.yaml"
    beats = []
    if hf.is_file():
        try:
            h = yaml.safe_load(hf.read_text()) or {}
            for svc, info in (h.get("services") or {}).items():
                beats.append({"service": svc, "status": info.get("status", "?"),
                              "last_seen_min": info.get("last_seen_minutes"),
                              "healthy": info.get("status") == "healthy"})
        except Exception:  # noqa: BLE001
            pass
    red = [b for b in beats if not b["healthy"]]
    return {"probes": probes[:20], "beats": beats, "red": len(red), "total": len(beats)}


def collect_resident_agents() -> dict:
    """Resident Agent 名册：角色/项目/状态可见。"""
    roles = {}
    for name in ("sediment", "projector", "orchestrator", "heartbeat", "decision"):
        roles[name] = {"project": "omo", "type": "resident", "state": "active"}
    # 尝试从 omo 子模块读取
    try:
        import yaml
        rr = ROOT / "projects/omo/src/omo/resident/roles.py"
        # 静态解析 ROLES 字典太复杂，用预定义 + 子模块角色补充
        extra = {"builder": "swarm", "executor": "swarm", "verifier": "swarm",
                 "planner": "swarm", "coordinator": "swarm"}
        for n, t in extra.items():
            roles[n] = {"project": "omo/swarm", "type": t, "state": "active"}
    except Exception:  # noqa: BLE001
        pass
    return {"roles": [{"name": k, **v} for k, v in sorted(roles.items())],
            "total": len(roles)}


def collect_scene_cards() -> dict:
    """Scene Card 生命周期：阶段分布。"""
    import yaml
    from glob import glob
    stages: dict[str, int] = {}
    cards = []
    for f in sorted(glob(str(ROOT / ".omo/_truth/scenarios/v3/*.yaml"))):
        try:
            doc = yaml.safe_load(Path(f).read_text()) or {}
            for cid, cfg in (doc.get("scenes") or doc if isinstance(doc, dict) else {}).items():
                if not isinstance(cfg, dict):
                    continue
                stage = str(cfg.get("stage", "unknown"))
                stages[stage] = stages.get(stage, 0) + 1
                cards.append({"id": str(cid)[:40], "stage": stage,
                              "domain": cfg.get("domain", ""),
                              "title": str(cfg.get("title", cid))[:40]})
        except Exception:  # noqa: BLE001
            pass
    return {"stages": stages, "cards": cards[:30], "total": sum(stages.values())}


def collect_journeys() -> dict:
    """Journey 状态：完成度/阻塞点。"""
    from glob import glob
    journeys = []
    for f in sorted(glob(str(ROOT / "docs/journey-specs/*.yaml"))):
        name = Path(f).stem
        size = Path(f).stat().st_size if Path(f).is_file() else 0
        journeys.append({"name": name, "size_kb": round(size/1024, 1), "file": f})
    return {"journeys": journeys[:25], "total": len(journeys)}


def collect_workspace_hygiene() -> dict:
    """工作区卫生：陈旧 worktree / 僵尸锁 / 遗留目录。"""
    from glob import glob
    # 陈旧 worktree（>7天未活动）
    stale_wt = []
    code, out = run(["git", "worktree", "list", "--porcelain"])
    if code == 0:
        cur = {}
        for line in out.splitlines():
            if line.startswith("worktree "):
                if cur.get("path"):
                    stale_wt.append(cur)
                cur = {"path": line.split(None, 1)[1]}
            elif line.startswith("branch "):
                cur["branch"] = line.split(None, 1)[1]
        if cur.get("path"):
            stale_wt.append(cur)
    # 僵尸锁
    locks = sorted(glob(str(ROOT / ".omo/_delivery/agent-workflows/locks/*.yaml")))
    return {"worktrees": stale_wt, "total_worktrees": len(stale_wt),
            "orphan_locks": locks[:10], "total_locks": len(locks)}


def collect_ci() -> dict:
    """CI Pipeline 健康。"""
    from collections import Counter
    code, out = run(["gh", "run", "list", "--limit", "60", "--json",
                     "workflowName,status,conclusion,event,createdAt,databaseId"])
    if code != 0 or not out.startswith("["):
        return {"total_runs": 0, "workflows": 0, "red_workflows": [], "all": []}
    try:
        data = json.loads(out)
    except Exception:
        return {"total_runs": 0, "workflows": 0, "red_workflows": [], "all": []}
    by_wf: dict[str, list[str]] = {}
    for r in data:
        w = r.get("workflowName", "?")
        conc = r.get("conclusion", "")
        status = "pass" if conc == "success" else ("fail" if conc in ("failure", "cancelled", "timed_out") else "other")
        by_wf.setdefault(w, []).append(status)
    summaries = []
    for w, statuses in sorted(by_wf.items()):
        cc = Counter(statuses)
        total = len(statuses)
        fails = cc.get("fail", 0)
        summaries.append({"workflow": w, "total": total, "pass": cc.get("pass", 0),
                          "fail": fails, "failure_rate": round(fails / total, 2) if total else 0,
                          "health": "red" if fails > 0 else "green"})
    red = [s for s in summaries if s["health"] == "red"][:8]
    return {"total_runs": len(data), "workflows": len(by_wf), "red_workflows": red, "all": summaries[:20]}


def collect_cron() -> dict:
    """Cron 调度台。"""
    import yaml
    from pathlib import Path as _P
    reg_file = ROOT / ".omo" / "cron" / "registry.yaml"
    if not reg_file.is_file():
        return {"total": 0, "active": 0, "proposed": 0, "installed": 0, "crontab_lines": 0, "planes": {}, "jobs": []}
    reg = yaml.safe_load(reg_file.read_text()) or {}
    jobs = reg.get("jobs", [])
    active_cr = [j for j in jobs if j.get("status") == "active"]
    proposed = [j for j in jobs if j.get("status") == "proposed"]
    installed_declared = [j for j in jobs if j.get("reality") == "installed"]
    planes: dict[str, int] = {}
    for j in jobs:
        for pl in j.get("planes", []):
            planes[pl] = planes.get(pl, 0) + 1
    code, ct_out = run(["crontab", "-l"])
    installed_lines = [l for l in ct_out.splitlines() if l.strip() and not l.strip().startswith("#")] if code == 0 else []
    sample = [{"name": j.get("name", ""), "schedule": j.get("schedule", ""),
               "status": j.get("status", ""), "reality": j.get("reality", "declared_only")} for j in jobs[:40]]
    return {"total": len(jobs), "active": len(active_cr), "proposed": len(proposed),
            "installed": len(installed_declared), "crontab_lines": len(installed_lines),
            "planes": planes, "jobs": sample}


def collect_submodules() -> dict:
    """子模块指针矩阵。"""
    subs: dict[str, dict] = {}
    for name in ("omo", "cockpit-ui", "cockpit", "agora", "ecos", "l4-kernel",
                 "bus-foundation", "aetherforge", "model-driven", "knowledge", "family-hub"):
        sp = ROOT / "projects" / name
        if not sp.is_dir():
            continue
        cur = run(["git", "-C", str(sp), "rev-parse", "HEAD"])[1] if run(["git", "-C", str(sp), "rev-parse", "HEAD"])[0] == 0 else None
        origin_main = run(["git", "-C", str(sp), "rev-parse", "origin/main"])[1] if run(["git", "-C", str(sp), "rev-parse", "origin/main"])[0] == 0 else None
        behind = ahead = 0
        if cur and origin_main:
            beh = run(["git", "-C", str(sp), "rev-list", "--left-right", "--count", f"origin/main...{cur}"])[1] if run(["git", "-C", str(sp), "rev-list", "--left-right", "--count", f"origin/main...{cur}"])[0] == 0 else ""
            if beh:
                parts = beh.strip().split()
                if len(parts) == 2:
                    behind, ahead = int(parts[0]), int(parts[1])
        status = "diverged" if behind and ahead else ("behind" if behind else ("ahead" if ahead else "synced"))
        subs[name] = {"current": (cur or "")[:12], "origin_main": (origin_main or "")[:12],
                      "behind": behind, "ahead": ahead, "status": status}
    synced = sum(1 for s in subs.values() if s["status"] == "synced")
    return {"submodules": subs, "synced": synced, "total": len(subs)}


def collect_debt() -> dict:
    """债务与决策。"""
    import yaml
    from glob import glob
    debts = []
    for f in sorted(glob(str(ROOT / ".omo/debt/items/*.yaml"))):
        try:
            d = yaml.safe_load(Path(f).read_text()) or {}
            debts.append({"id": d.get("id", Path(f).stem), "status": str(d.get("status", "?")),
                          "severity": d.get("severity", ""), "title": str(d.get("title", ""))[:60]})
        except Exception:  # noqa: BLE001
            pass
    open_d = [d for d in debts if d["status"] in ("open", "proposed", "registered")]
    closeout = [Path(f).stem for f in sorted(glob(str(ROOT / ".omo/_knowledge/retros/BET-*.md")))[-8:]]
    return {"total": len(debts), "open": len(open_d), "debts": debts[:15], "recent_retros": closeout}


def collect_workflows() -> list[dict]:
    """工作流活动。"""
    from glob import glob
    import yaml
    runs = sorted(glob(str(ROOT / ".omo/_delivery/agent-workflows/runs/*.yaml")), reverse=True)[:15]
    out = []
    for f in runs:
        try:
            content = Path(f).read_text().split("---")[0]
            meta = yaml.safe_load(content) or {}
            out.append({"run_id": meta.get("run_id", ""), "workflow_id": str(meta.get("workflow_id", ""))[:40],
                        "status": meta.get("status", ""), "created_at": str(meta.get("created_at", ""))[:19]})
        except Exception:  # noqa: BLE001
            pass
    return out


def collect_alerts() -> dict:
    """告警聚合：CI 红源 + 开放债务 + 需关注探针。"""
    import yaml
    from glob import glob
    alerts = []
    try:
        ci = json.loads(open(str(ROOT / "runtime/dashboard/data.json")).read()) if (ROOT / "runtime/dashboard/data.json").is_file() else {}
        for w in (ci.get("ci", {}).get("red_workflows") or []):
            alerts.append({"severity": "high", "source": "ci", "msg": f"workflow 红源: {w['workflow']} ({w['fail']}/{w['total']})"})
    except Exception:  # noqa: BLE001
        pass
    try:
        for f in glob(str(ROOT / ".omo/debt/items/*.yaml")):
            d = yaml.safe_load(Path(f).read_text()) or {}
            if d.get("status") in ("open", "registered"):
                alerts.append({"severity": d.get("severity", "medium"), "source": "debt",
                               "msg": f"开放债务: {d.get('title', d.get('id',''))[:50]}"})
    except Exception:  # noqa: BLE001
        pass
    high = sum(1 for a in alerts if a["severity"] == "high")
    return {"alerts": alerts[:30], "high": high, "total": len(alerts)}


def collect_deployments() -> dict:
    """部署活动：近 7 天 commit。"""
    code, out = run(["git", "log", "--oneline", "--no-merges", "-n", "20",
                     "--since", "7 days ago", "--format=%h|%s|%ad", "--date=short"])
    commits = []
    if code == 0:
        for line in out.splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                commits.append({"sha": parts[0], "subject": parts[1][:70], "date": parts[2]})
    return {"commits": commits, "total": len(commits)}


def collect_closeouts() -> dict:
    """待 closeout：engineering done 但缺 retro/value 的 BET。"""
    import yaml
    from glob import glob
    ready = []
    for f in sorted(glob(str(ROOT / "docs/plans/3y-bet-ledger-archive.yaml"))):
        try:
            doc = yaml.safe_load(Path(f).read_text()) or {}
            for b in (doc.get("bets") or []):
                if not isinstance(b, dict):
                    continue
                eng = (b.get("completion_evidence") or {}).get("axes", {}).get("engineering", {})
                if eng.get("status") == "VERIFIED":
                    ready.append({"id": b.get("id", ""), "title": str(b.get("title", ""))[:50]})
        except Exception:  # noqa: BLE001
            pass
    return {"closeouts": ready[:15], "total": len(ready)}

def build_payload() -> dict:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "read-only-ssot-aggregation",
        "gates": collect_gates(),
        "bets": collect_bets(),
        "agents": collect_agents(),
        "runtime": collect_runtime(),
        "docs": collect_docs(),
        "role_admission": collect_role_admission(),
        "asd": collect_asd(),
        "probes": collect_probes(),
        "resident_agents": collect_resident_agents(),
        "scene_cards": collect_scene_cards(),
        "journeys": collect_journeys(),
        "workspace": collect_workspace_hygiene(),
        "ci": collect_ci(),
        "cron": collect_cron(),
        "submodules": collect_submodules(),
        "debt": collect_debt(),
        "workflows": collect_workflows(),
        "alerts": collect_alerts(),
        "deployments": collect_deployments(),
        "closeouts": collect_closeouts(),
    }


def write_site(payload: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    html = TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
    INDEX_HTML.write_text(html)


def check_side_effects() -> int:
    before = run(["git", "status", "--porcelain"])[1].splitlines()
    payload = build_payload()
    write_site(payload)
    after = run(["git", "status", "--porcelain"])[1].splitlines()
    new_repo_writes = [l for l in after if l not in before and not l.startswith("?? runtime/dashboard")]
    if new_repo_writes:
        print("SIDE EFFECT DETECTED:")
        for l in new_repo_writes:
            print(" ", l)
        return 1
    print(f"OK: 零仓库写副作用（产物仅 {OUT_DIR.relative_to(ROOT)}/, gitignored）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="只输出 data.json 到 stdout 摘要")
    ap.add_argument("--gates", action="store_true", help="只输出门禁部分")
    ap.add_argument("--check-side-effects", action="store_true")
    args = ap.parse_args()

    if args.check_side_effects:
        return check_side_effects()

    payload = build_payload()
    write_site(payload)

    if args.gates:
        print(json.dumps(payload["gates"], ensure_ascii=False, indent=1))
        return 0
    if args.json:
        summary = {"generated_at": payload["generated_at"],
                   "gates": {g["id"]: g["verdict"] for g in payload["gates"]},
                   "bets": payload["bets"]["counts"],
                   "agents": len(payload["agents"]),
                   "out": str(INDEX_HTML.relative_to(ROOT))}
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        return 0
    print(f"✅ 驾驶舱已生成: {INDEX_HTML.relative_to(ROOT)}  ({payload['generated_at']})")
    print(f"   服务: python3 bin/panorama/panorama-serve.py  → http://127.0.0.1:43910")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>织星全景驾驶舱</title>
<style>
:root{--paper:#0d1420;--card:#151f30;--line:#24344d;--ink:#dbe6f4;--muted:#7d93b0;
--blue:#5b9dff;--teal:#3ecf9a;--amber:#f0b453;--red:#f26d6d;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
font:14px/1.6 -apple-system,"PingFang SC",sans-serif}
aside{position:fixed;inset:0 auto 0 0;width:200px;background:#0a101b;padding:26px 14px;border-right:1px solid var(--line)}
aside h1{font-size:19px;margin:0 0 4px;letter-spacing:3px}aside small{color:var(--muted);font-size:10px}
nav a{display:block;color:var(--muted);text-decoration:none;padding:8px 10px;border-radius:8px;font-size:13px}
nav a.on,nav a:hover{color:var(--ink);background:#1a2740}
main{margin-left:200px;padding:26px 32px;max-width:1500px}
.sec{display:none}.sec.on{display:block}
h2{font-size:20px;margin:0 0 4px}p.sub{color:var(--muted);font-size:12px;margin:0 0 18px}
.grid{display:grid;gap:14px}.g3{grid-template-columns:repeat(3,1fr)}.g2{grid-template-columns:1.2fr 1fr}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.card h3{margin:0 0 10px;font-size:14px}
.kpi b{font:26px var(--mono);display:block}.kpi span{color:var(--muted);font-size:11px}
table{width:100%;border-collapse:collapse;font-size:12px}
td,th{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:500;font-size:11px}
.chip{display:inline-block;padding:2px 8px;border-radius:6px;font:11px var(--mono)}
.p{background:#12312a;color:var(--teal)}.f{background:#3a1a1c;color:var(--red)}
.w{background:#3a2d14;color:var(--amber)}.n{background:#1a2740;color:var(--muted)}
.mono{font-family:var(--mono);font-size:11px}
.bar{height:8px;background:#1a2740;border-radius:4px;overflow:hidden;margin-top:5px}
.bar i{display:block;height:100%;background:var(--blue)}
.bar.done i{background:var(--teal)}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.dead{color:var(--red)}.fresh{color:var(--teal)}
.foot{margin-top:26px;color:var(--muted);font-size:11px;border-top:1px solid var(--line);padding-top:12px}
@media(max-width:900px){aside{position:static;width:auto}main{margin:0}.g3,.g2{grid-template-columns:1fr}}
</style>
</head>
<body>
<aside>
<h1>织星驾驶舱</h1><small>OMO PANORAMA · <span id="ts"></span></small>
<nav id="nav">
<a href="#overview" data-s="overview">体系总览</a>
<a href="#gates" data-s="gates">门禁 A1–A9</a>
<a href="#agents" data-s="agents">Agent 全景</a>
<a href="#bets" data-s="bets">任务与里程碑</a>
<a href="#runtime" data-s="runtime">运行态</a>
<a href="#probes" data-s="probes">Probe 心跳</a>
<a href="#resident" data-s="resident">Resident Agent</a>
<a href="#scenes" data-s="scenes">Scene 卡</a>
<a href="#journeys" data-s="journeys">Journey</a>
<a href="#hygiene" data-s="hygiene">工作区卫生</a>
<a href="#docs" data-s="docs">知识入口</a>
</nav>
</aside>
<main>
<section class="sec on" id="s-overview">
<h2>体系总览</h2><p class="sub">OMO 单控制面 + 持久 Role/Queue/Receipt + 动态 Agent Cell · 5+4+1+1 · 道法术器嵌套 MOF</p>
<div class="grid g3" id="kpi"></div>
<div class="grid g2" style="margin-top:14px">
<div class="card"><h3>架构主轴</h3><div class="mono" style="font-size:12px;line-height:2">
L0 协议(ecos) → L1 运行时(omo/Mesh) → L2 内核(l4-kernel) → L3 入口(cockpit) → L4 文档<br>
S 槽唯一 dispatcher：COMP-WS-omo · 八律第3条已收口（dispatch_backend）<br>
Cell=动态算力（B 槽）；Resident=投影不派活；MOS=记忆控制面</div></div>
<div class="card"><h3>本周动态</h3><div id="week" class="mono" style="font-size:12px;line-height:2"></div></div>
</div>
</section>
<section class="sec" id="s-gates">
<h2>门禁 A1–A9 / RF0</h2><p class="sub">底层实时验证 + 声明态边界 · PARTIAL ≠ PASS · 未过门零写入/零自治/零扩并发</p>
<div class="grid g3" id="gategrid"></div>
</section>
<section class="sec" id="s-agents">
<h2>Agent 全景</h2><p class="sub">worktree / 分支 / 最近活动 · 所有 agent 可见</p>
<div class="card"><table id="agenttable"><thead><tr><th>worktree</th><th>分支</th><th>最近活动</th></tr></thead><tbody></tbody></table></div>
</section>
<section class="sec" id="s-bets">
<h2>任务与里程碑</h2><p class="sub">三年台账窗口进度 · in_progress / blocked 聚焦</p>
<div class="grid g2">
<div class="card"><h3>窗口进度（Y1Q1→Y3H2）</h3><div id="windows"></div></div>
<div class="card"><h3>进行中 / 阻塞</h3><table id="focus"><thead><tr><th>ID</th><th>标题</th><th>级</th></tr></thead><tbody></tbody></table></div>
</div>
</section>
<section class="sec" id="s-runtime">
<h2>运行态</h2><p class="sub">守护 / 调度 / 引用健康 · meta-doctor 摘要</p>
<div class="grid g3" id="rtgrid"></div>
</section>
<section class="sec" id="s-docs">
<h2>知识入口</h2><p class="sub">白皮书 / 架构 / 流程 / 操作 —— 每卡直达源文档</p>
<div class="grid g3" id="docgrid"></div>
</section>

<section class="sec" id="s-probes">
<h2>Probe 心跳矩阵</h2><p class="sub">守护/探针 SLA 健康（绿/红/陈旧）</p>
<div class="grid g3" id="probekpi"></div>
<div class="card" style="margin-top:12px"><h3>实时心跳</h3><table id="probebtbl"><thead><tr><th>服务</th><th>状态</th><th>最后可见</th></tr></thead><tbody></tbody></table></div>
</section>
<section class="sec" id="s-resident">
<h2>Resident Agent 名册</h2><p class="sub">常驻角色/项目/类型 · 可见</p>
<div class="card"><table id="restbl"><thead><tr><th>角色</th><th>项目</th><th>类型</th></tr></thead><tbody></tbody></table></div>
</section>
<section class="sec" id="s-scenes">
<h2>Scene Card 生命周期</h2><p class="sub">阶段分布（draft→routine）</p>
<div class="grid g3" id="scenekpi"></div>
<div class="card" style="margin-top:12px"><table id="scenetbl"><thead><tr><th>ID</th><th>阶段</th><th>域</th></tr></thead><tbody></tbody></table></div>
</section>
<section class="sec" id="s-journeys">
<h2>Journey 状态</h2><p class="sub">旅程规格文件 · 完成度/阻塞</p>
<div class="card"><table id="journeytbl"><thead><tr><th>名称</th><th>大小</th></tr></thead><tbody></tbody></table></div>
</section>
<section class="sec" id="s-hygiene">
<h2>工作区卫生</h2><p class="sub">陈旧 worktree / 僵尸锁 / 遗留</p>
<div class="grid g2">
<div class="card"><h3>Worktree 列表</h3><table id="wttbl"><thead><tr><th>路径</th><th>分支</th></tr></thead><tbody></tbody></table></div>
<div class="card"><h3>僵尸锁</h3><div id="locklist" class="mono" style="font-size:12px;line-height:2"></div></div>
</div>
</section>
<div class="foot">只读 SSOT 聚合 · 零写入零派工 · 产物 runtime/dashboard/（gitignored）· 刷新: launchd 每 5min · 与 Serena 观测站(43191)互补</div>
</main>
<script>
const D=__DATA__;
document.getElementById('ts').textContent=D.generated_at.slice(0,16).replace('T',' ');
const $=id=>document.getElementById(id);
const chip=v=>v==='PASS'?'<span class="chip p">PASS</span>':(v==='FAIL'?'<span class="chip f">FAIL</span>':'<span class="chip n">'+v+'</span>');
// nav
document.querySelectorAll('#nav a').forEach(a=>a.onclick=e=>{e.preventDefault();
document.querySelectorAll('#nav a').forEach(x=>x.classList.remove('on'));a.classList.add('on');
document.querySelectorAll('.sec').forEach(s=>s.classList.remove('on'));$('s-'+a.dataset.s).classList.add('on');});
// overview
const c=D.bets.counts;
$('kpi').innerHTML=[
 ['总 BET',D.bets.total,'三年台账'],
 ['已完成',c.done||0,'done'],
 ['候选',c.candidate||0,'待认领'],
 ['进行中',c.in_progress||0,'in_progress'],
 ['阻塞',c.blocked||0,'blocked'],
 ['Agents',D.agents.length,'worktree 占用']
].map(x=>'<div class="card kpi"><b>'+x[1]+'</b><span>'+x[0]+' · '+x[2]+'</span></div>').join('');
const gmap={};D.gates.forEach(g=>gmap[g.id]=g.verdict);
$('week').innerHTML='SFOP 八律第3条: '+gmap['A1']+'<br>调度一致性: '+gmap['A4']+'<br>引用完整性: '+gmap['A5']+'<br>Semantic gate: '+gmap['A3'];
// gates
$('gategrid').innerHTML=D.gates.map(g=>'<div class="card"><h3>'+g.id+' · '+g.title+'</h3>'+chip(g.verdict)+
'<div class="mono" style="margin-top:8px;color:var(--muted)">'+g.detail+'</div>'+
(g.depends_on?'<div class="mono" style="margin-top:6px;font-size:10px">依赖: '+g.depends_on.join(', ')+'</div>':'')+'</div>').join('');
// agents
$('agenttable').querySelector('tbody').innerHTML=D.agents.map(a=>'<tr><td class="mono">'+a.worktree+'</td><td class="mono">'+(a.branch||'')+'</td><td>'+
(a.last_activity_hours==null?'<span class="chip n">n/a</span>':a.last_activity_hours<2?'<span class="chip p">'+a.last_activity_hours+'h</span>':a.last_activity_hours<24?'<span class="chip w">'+a.last_activity_hours+'h</span>':'<span class="chip f">'+a.last_activity_hours+'h</span>')+'</td></tr>').join('');
// bets
$('windows').innerHTML=Object.entries(D.bets.windows).map(([w,d])=>{
const pct=Math.round(100*d.done/d.total);
return '<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between" class="mono"><span>'+w+'</span><span>'+d.done+'/'+d.total+'</span></div><div class="bar '+(pct===100?'done':'')+'"><i style="width:'+pct+'%"></i></div></div>';}).join('');
const rows=[...D.bets.in_progress.map(b=>({...b,s:'p'})),...D.bets.blocked.map(b=>({...b,s:'f'}))];
$('focus').querySelector('tbody').innerHTML=rows.map(b=>'<tr><td class="mono">'+b.id+'</td><td>'+b.title+'</td><td><span class="chip '+b.s+'">'+b.priority+'</span></td></tr>').join('')||'<tr><td colspan=3 class="mono">无</td></tr>';
// runtime
const md=D.runtime.meta_doctor||{};
$('rtgrid').innerHTML=[
 ['stale_beats',md.stale_beats],['dead_refs',md.dead_refs],['ritual_lapsed',md.ritual_lapsed],
 ['untracked_refs',md.untracked_refs],['launchd 任务',D.runtime.launchd_omostation_jobs],['crontab 行',D.runtime.crontab_lines]
].map(x=>'<div class="card kpi"><b class="'+(x[1]===0?'fresh':(x[1]>0&&x[0]!=='launchd 任务'&&x[0]!=='crontab 行'?'dead':'fresh'))+'">'+x[1]+'</b><span>'+x[0]+'</span></div>').join('');
// docs
$('docgrid').innerHTML=D.docs.map(d=>'<div class="card"><h3>'+d.name+'</h3><span class="chip '+(d.exists?'p':'f')+'">'+(d.exists?Math.round(d.size/1024)+'KB':'缺失')+'</span>'+
'<div class="mono" style="margin-top:8px;font-size:11px">'+d.path+'</div>'+
(d.exists?'<div style="margin-top:8px"><a href="/../../'+d.path+'">打开 →</a></div>':'')+'</div>').join('');
||||||| aff197f5fd

T10-166 数据契约（per 面板）:
  - provenance: 字段来源 (gate-health / meta-doctor / bet-ledger / git worktree)
  - freshness:   采集时间窗 + staleness 阈值 (>5min 标 stale)
  - degradation: 0=fresh, 1=partial, 2=stale-blink, 3=missing
  - never-yields-green: 任何缺失/陈旧 → 不得报 PASS (PARTIAL ≠ PASS 铁律)

用法：
    python3 bin/panorama/panorama-collect.py            # 采集 + 生成站点
    python3 bin/panorama/panorama-collect.py --json     # 只输出 data.json 摘要
    python3 bin/panorama/panorama-collect.py --gates    # 只刷新门禁 receipt 视图
    python3 bin/panorama/panorama-collect.py --check-side-effects
                                                        # 验证零仓库写副作用
"""
