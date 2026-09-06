#!/usr/bin/env python3
"""Scene Graph — DAG-based scene orchestration with event-driven choreography."""

from __future__ import annotations
import argparse, json, subprocess, sys, uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = _ROOT / ".omo" / "_truth" / "scenarios" / "v3"
JOURNEY_ENGINE = _ROOT / "bin" / "ssot" / "journey-engine.py"
EVENT_LOG = _ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "scene-events.jsonl"

class SceneNode:
    def __init__(self, scene_id, node_type="scene"):
        self.scene_id, self.node_type = scene_id, node_type
        self.children: list[tuple[str,str]] = []
    def add_edge(self, target, condition=None): self.children.append((target, condition or "always"))

class SceneGraph:
    def __init__(self, graph_id, name=""):
        self.graph_id, self.name = graph_id, name
        self.nodes: dict[str, SceneNode] = {}; self.entry_point: str | None = None
    def add_node(self, scene_id, node_type="scene"):
        if scene_id not in self.nodes: self.nodes[scene_id] = SceneNode(scene_id, node_type)
        return self.nodes[scene_id]
    def add_edge(self, source, target, condition=None):
        self.add_node(source); self.add_node(target); self.nodes[source].add_edge(target, condition)
    def set_entry(self, scene_id): self.entry_point = scene_id; self.add_node(scene_id)
    def topological_sort(self) -> list[str]:
        indeg = {n:0 for n in self.nodes}
        for nd in self.nodes.values():
            for t,_ in nd.children: indeg[t] = indeg.get(t,0)+1
        q = sorted([n for n,d in indeg.items() if d==0]); res = []
        while q:
            cur = q.pop(0); res.append(cur)
            for t,_ in self.nodes[cur].children:
                indeg[t] -= 1
                if indeg[t]==0: q.append(t); q.sort()
        if len(res) != len(self.nodes): raise ValueError("Cycle detected")
        return res
    def detect_cycles(self) -> list[list[str]]:
        cycles, visited, path, ps = [], set(), [], set()
        def dfs(n):
            visited.add(n); path.append(n); ps.add(n)
            for t,_ in self.nodes.get(n, SceneNode(n)).children:
                if t in ps: cycles.append(path[path.index(t):]+[t])
                elif t not in visited: dfs(t)
            path.pop(); ps.discard(n)
        for n in self.nodes:
            if n not in visited: dfs(n)
        return cycles

def emit_scene_event(event_type, source_scene, payload, correlation_id=None) -> dict:
    evt = {"event_id":f"evt-{uuid.uuid4().hex[:12]}","event_type":event_type,"source_scene":source_scene,
           "timestamp":datetime.now(UTC).isoformat(),"correlation_id":correlation_id or f"corr-{uuid.uuid4().hex[:12]}","payload":payload}
    EVENT_LOG.parent.mkdir(parents=True,exist_ok=True)
    with open(EVENT_LOG,"a",encoding="utf-8") as f: f.write(json.dumps(evt,ensure_ascii=False)+"\n")
    return evt

def build_graph_from_scenes() -> SceneGraph:
    import yaml
    g = SceneGraph("auto-generated","Auto-generated from scene topology"); scenes = []
    if SCENES_DIR.is_dir():
        for p in sorted(SCENES_DIR.glob("*.yaml")):
            try:
                with open(p,encoding="utf-8") as f: docs=list(yaml.safe_load_all(f))
                body = docs[-1] if len(docs)>1 else docs[0]
                if isinstance(body,dict): scenes.append(body)
            except: continue
    for s in scenes:
        sid = s.get("scene_id","")
        if sid: g.add_node(sid)
    for s in scenes:
        sid = s.get("scene_id","")
        for d in s.get("topology",{}).get("downstream",[]):
            t = d.get("scene",""); tr = d.get("trigger_on","always")
            if t and t in g.nodes: g.add_edge(sid,t,tr)
    all_targets = set()
    for s in scenes:
        for d in s.get("topology",{}).get("downstream",[]):
            if d.get("scene"): all_targets.add(d["scene"])
    roots = [s.get("scene_id","") for s in scenes if s.get("scene_id") and s.get("scene_id") not in all_targets]
    if roots: g.set_entry(roots[0])
    elif scenes: g.set_entry(scenes[0].get("scene_id",""))
    return g

def execute_graph(graph, initial_signal, dry_run=False) -> dict:
    """Execute all reachable scenes from entry point via DFS."""
    run_id = f"graph-{uuid.uuid4().hex[:12]}"; corr = f"corr-{uuid.uuid4().hex[:12]}"; results = {}
    visited = set(); sig = dict(initial_signal)

    def _exec_node(node_id):
        if node_id in visited or node_id not in graph.nodes: return
        visited.add(node_id)
        if dry_run:
            result = {"status":"succeeded","dry_run":True,"confidence":0.85,"scene_id":node_id}
        else:
            try:
                proc = subprocess.run([sys.executable,str(JOURNEY_ENGINE),"execute",node_id,"--signal",json.dumps(sig)],
                    capture_output=True,text=True,cwd=str(_ROOT),timeout=300)
                result = json.loads(proc.stdout.strip()) if proc.stdout.strip() else {"status":"error","error":proc.stderr}
            except Exception as e: result = {"status":"error","error":str(e)}
        results[node_id] = result
        emit_scene_event("scene.completed",node_id,{"result":result,"graph_id":graph.graph_id,"run_id":run_id},corr)
        # Follow edges (DFS)
        node = graph.nodes.get(node_id)
        if node:
            for target, condition in node.children:
                if condition == "always":
                    _exec_node(target)
                else:
                    try:
                        ns = {"result":result,"confidence":result.get("confidence",0)}
                        if "==" in condition:
                            l,r = condition.split("==",1)
                            if _resolve(l.strip(),ns) == _resolve_lit(r.strip()): _exec_node(target)
                    except: pass

    entry = graph.entry_point
    if not entry: raise ValueError("No entry point")
    _exec_node(entry)
    return {"run_id":run_id,"correlation_id":corr,"graph_id":graph.graph_id,"scenes_executed":len(results),"results":results}

def _resolve(p,d):
    c=d
    for x in p.strip().split("."): c=c.get(x) if isinstance(c,dict) else getattr(c,x,None) if hasattr(c,x) else None
    return c
def _resolve_lit(v):
    v=v.strip()
    if (v.startswith("'")and v.endswith("'"))or(v.startswith('"')and v.endswith('"')):return v[1:-1]
    try:return int(v)
    except ValueError:
        try:return float(v)
        except:return v

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    bp = sub.add_parser("build"); bp.add_argument("--output",type=Path)
    ep = sub.add_parser("execute"); ep.add_argument("--signal",type=json.loads,default={}); ep.add_argument("--dry-run",action="store_true")
    vp = sub.add_parser("validate")
    args = parser.parse_args(argv); cmd = args.command or "validate"
    if cmd == "build":
        g = build_graph_from_scenes(); d = {"graph_id":g.graph_id,"name":g.name,"entry_point":g.entry_point,
            "nodes":{n:{"scene_id":nd.scene_id,"type":nd.node_type,"edges":[{"target":t,"condition":c} for t,c in nd.children]} for n,nd in g.nodes.items()},
            "topological_order":g.topological_sort()}
        if args.output:
            with open(args.output,"w") as f: json.dump(d,f,ensure_ascii=False,indent=2)
        print(json.dumps(d,ensure_ascii=False,indent=2)); return 0
    if cmd == "execute":
        r = execute_graph(build_graph_from_scenes(),args.signal,dry_run=args.dry_run)
        print(json.dumps(r,ensure_ascii=False,indent=2)); return 0
    if cmd == "validate":
        g = build_graph_from_scenes(); cy = g.detect_cycles()
        print(json.dumps({"graph_id":g.graph_id,"nodes":len(g.nodes),"entry_point":g.entry_point,
            "topological_order":g.topological_sort(),"cycles_detected":len(cy),"cycles":cy,"valid":len(cy)==0},ensure_ascii=False,indent=2))
        return 0 if len(cy)==0 else 1
    parser.print_help(); return 1

if __name__ == "__main__": raise SystemExit(main())
