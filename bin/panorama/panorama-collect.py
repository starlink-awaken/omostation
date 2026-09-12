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
    code, out = run(["python3", "bin/gac/gate-health-check.py", "--json"])
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


def collect_docs() -> list[dict]:
    docs = []
    for d in DOC_ENTRIES:
        p = ROOT / d["path"]
        entry = dict(d)
        entry["exists"] = p.is_file()
        entry["size"] = p.stat().st_size if p.is_file() else 0
        docs.append(entry)
    return docs


def build_payload() -> dict:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "read-only-ssot-aggregation",
        "gates": collect_gates(),
        "bets": collect_bets(),
        "agents": collect_agents(),
        "runtime": collect_runtime(),
        "docs": collect_docs(),
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
</script>
</body></html>
"""

if __name__ == "__main__":
    sys.exit(main())
