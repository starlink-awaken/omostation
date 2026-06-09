#!/usr/bin/env python3
"""ecos MCP Server — 织星生态统一对外入口 | v1.0"""
import sys
import os
import json
import subprocess
from pathlib import Path

ECOS_SRC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ECOS_SRC))

# F821: define missing variables
SCRIPTS = ECOS_SRC / "scripts"
H = Path.home()

# 复用 domain-manager 逻辑
from importlib.machinery import SourceFileLoader  # noqa: E402
DM_PATH = ECOS_SRC / "services" / "domain_manager.py"
dm = SourceFileLoader("dm", str(DM_PATH)).load_module()

TOOLS = [
    # ── 域发现 ──
    {"name":"domain_list","description":"列出所有已注册域·19域7类型","inputSchema":{"type":"object","properties":{"type":{"type":"string","enum":["document","config","engine","tool","workspace","storage","model"]}}}},
    {"name":"domain_stats","description":"全域统计概览","inputSchema":{"type":"object","properties":{}}},
    
    # ── BOS URI ──
    {"name":"domain_resolve","description":"BOS URI→物理路径解析。bos://vault/_state→STATE.md","inputSchema":{"type":"object","properties":{"uri":{"type":"string"}},"required":["uri"]}},
    {"name":"domain_read","description":"通过BOS URI读取资源内容·支持语义化快捷","inputSchema":{"type":"object","properties":{"uri":{"type":"string"},"max_lines":{"type":"integer","default":50}}}},
    {"name":"domain_search","description":"跨域搜索·grep全量CLAUDE.md+STATE.md+_knowledge","inputSchema":{"type":"object","properties":{"query":{"type":"string"},"domains":{"type":"array","items":{"type":"string"}},"max_results":{"type":"integer","default":10}},"required":["query"]}},
    
    # ── KEMS校验 ──
    {"name":"domain_validate","description":"校验域KEMS六面结构完整性","inputSchema":{"type":"object","properties":{"domain":{"type":"string","description":"域ID或别名"}},"required":["domain"]}},
    {"name":"domain_tree","description":"域目录树·KEMS着色","inputSchema":{"type":"object","properties":{"domain":{"type":"string"}},"required":["domain"]}},
    
    # ── 健康 ──
    {"name":"ecos_health","description":"全系统健康检查(9项)","inputSchema":{"type":"object","properties":{}}},
    {"name":"ecos_brief","description":"会话简报·当前状态快照","inputSchema":{"type":"object","properties":{}}},
    
    # ── BOS 路由 ──
    {"name":"bos_routes","description":"BOS路由表·所有域URI映射","inputSchema":{"type":"object","properties":{}}},

    # ── 工作流 (Phase 33) ──
    {"name":"workflow_list","description":"列出所有已注册工作流·按域/层/状态过滤·bos://ecos/workflow/*","inputSchema":{"type":"object","properties":{"domain":{"type":"string","enum":["memory","omo","analysis","persona","forge","meta","infra"]},"layer":{"type":"string","enum":["L0","L1","L2","I0","L3","L4"]},"status":{"type":"string","enum":["defined","active","deprecated","archived"]}}}},
    {"name":"workflow_show","description":"查看指定工作流完整定义·步骤/关系/SLA/跨层映射·bos://ecos/workflow/{name}","inputSchema":{"type":"object","properties":{"name":{"type":"string","description":"工作流名称或 WORKFLOW-ID"}},"required":["name"]}},
    {"name":"workflow_relations","description":"工作流关系图·上下游依赖/触发链·支持全局或指定工作流","inputSchema":{"type":"object","properties":{"name":{"type":"string","description":"可选·不传返回全局关系图"}}}},
]

def handle_domain_list(args):
    r = dm.load_registry()
    dt = args.get("type")
    result = []
    for d in r:
        if dt and d.get("domain_type")!=dt:
            continue
        result.append({"id":d["id"],"name":d.get("name",""),"type":d.get("domain_type","document"),"layer":d.get("layer","L4"),"bos_uri":f"bos://{d['id']}"})
    return {"domains":result,"total":len(result)}

def handle_domain_stats(args):
    r = dm.load_registry()
    from collections import Counter
    types = Counter(d.get("domain_type","document") for d in r)
    layers = Counter(d.get("layer","L4") for d in r)
    return {"total":len(r),"by_type":dict(types),"by_layer":dict(layers)}

def handle_domain_validate(args):
    domain = args.get("domain","")
    r = dm.load_registry()
    d = dm.find_domain(r, domain)
    if not d:
        return {"error":f"域未注册: {domain}"}
    p = dm.resolve_path(d)
    if not p.exists():
        return {"error":f"路径不存在: {p}"}
    results = dm.validate_domain(p, d.get("domain_type","document"), d.get("governance_tier",1))
    return {"domain":d.get("name",d["id"]),"path":str(p),"checks":[{"name":n,"pass":ok,"detail":dt} for n,ok,dt in results],"passed":sum(1 for _,ok,_ in results if ok),"failed":sum(1 for _,ok,_ in results if not ok)}

def handle_domain_tree(args):
    domain = args.get("domain","")
    r = dm.load_registry()
    d = dm.find_domain(r, domain)
    if not d:
        return {"error":f"域未注册: {domain}"}
    p = dm.resolve_path(d)
    if not p.exists():
        return {"error":f"路径不存在: {p}"}
    
    def tree(dir_path, depth=0):
        if depth>3:
            return []
        items = sorted([i for i in dir_path.iterdir() if not i.name.startswith(".") and not i.name.startswith("__")], key=lambda x:(not x.is_dir(),x.name))
        result = []
        for item in items:
            node = {"name":item.name,"type":"dir" if item.is_dir() else "file"}
            if item.is_dir() and depth<2:
                node["children"] = tree(item, depth+1)
            result.append(node)
        return result
    
    return {"domain":d.get("name",d["id"]),"tree":tree(p)}

def handle_ecos_health(args):
    r = subprocess.run(["python3",str(SCRIPTS/"ecos-health-check.py"),"--json"],capture_output=True,text=True,timeout=30)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"output":r.stdout[:500]}

def handle_ecos_brief(args):
    r = subprocess.run(["python3",str(SCRIPTS/"ecos-brief.py"),"--json"],capture_output=True,text=True,timeout=10)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"output":r.stdout[:500]}

def handle_bos_routes(args):
    rf = H/".ecos"/"bos"/"routes.json"
    if rf.exists():
        with open(rf) as f:
            return json.load(f)
    return {"error":"routes.json未生成·运行 ecos domain routes"}

# ── Workflow handlers (Phase 33) ──
import yaml  # noqa: E402
W = Path(__file__).resolve().parent.parent / "ssot"
M1_WF_DIR = W / "mof" / "m1" / "workflow"
WF_CATALOG = W / "registry" / "workflow-catalog.yaml"

def _load_workflow_nodes():
    nodes = []
    if M1_WF_DIR.exists():
        for f in sorted(M1_WF_DIR.glob("WORKFLOW-*.yaml")):
            try:
                node = yaml.safe_load(open(f))
                if node and node.get("type") == "Workflow":
                    nodes.append(node)
            except Exception:
                pass
    return nodes

def handle_workflow_list(args):
    nodes = _load_workflow_nodes()
    domain = args.get("domain")
    layer = args.get("layer")
    status = args.get("status")
    filtered = []
    for n in nodes:
        if domain and n.get("domain") != domain:
            continue
        if layer and n.get("layer") != layer:
            continue
        if status and n.get("status") != status:
            continue
        filtered.append({"id":n.get("id"),"name":n.get("name"),"subtype":n.get("subtype"),
                         "domain":n.get("domain"),"layer":n.get("layer"),
                         "bos_uri":n.get("bos_uri"),"description":n.get("description","")})
    return {"workflows":filtered,"total":len(filtered),"filtered_from_total":len(nodes)}

def handle_workflow_show(args):
    name = args.get("name","").lower()
    nodes = _load_workflow_nodes()
    for n in nodes:
        nid = n.get("id","").lower()
        nname = n.get("name","").lower()
        kebab = nid.replace("workflow-","").replace("_","-")
        if name == nid or name == nname or name in nid or name in kebab:
            return n
    return {"error":f"工作流未找到: {name}"}

def handle_workflow_relations(args):
    name = args.get("name")
    catalog = {}
    if WF_CATALOG.exists():
        try:
            catalog = yaml.safe_load(open(WF_CATALOG))
        except Exception:
            pass
    global_rels = catalog.get("global_relations",{})
    if name:
        nodes = _load_workflow_nodes()
        node = None
        for n in nodes:
            if name.lower() in n.get("id","").lower() or name.lower() in n.get("name","").lower():
                node = n
                break
        if not node:
            return {"error":f"工作流未找到: {name}"}
        nid = node.get("id")
        upstream = [t for t in global_rels.get("triggers",[]) if t.get("to")==nid]
        downstream = [t for t in global_rels.get("triggers",[]) if t.get("from")==nid]
        deps = [d for d in global_rels.get("dependencies",[]) if d.get("dependent")==nid]
        return {"workflow":nid,"upstream_triggers":upstream,"downstream_triggers":downstream,"dependencies":deps}
    return global_rels

# BOS tools (复用bos-mcp-server逻辑)
def handle_resolve(args):
    r = dm.load_registry()
    d,s = dm.parse_bos_uri(args["uri"], r)
    if not d:
        return {"error":f"无法解析: {args['uri']}"}
    p = dm.resolve_path(d)
    full = str(p/s if s else p)
    return {"uri":args["uri"],"physical_path":full,"exists":os.path.exists(full),"domain":d.get("name",d["id"]),"type":d.get("domain_type","?")}

def handle_read(args):
    r = dm.load_registry()
    d,s = dm.parse_bos_uri(args.get("uri",""), r)
    if not d:
        return {"error":"无法解析"}
    p = dm.resolve_path(d)
    full = p/s if s else p
    if not full.exists():
        return {"error":f"不存在: {full}"}
    if full.is_dir():
        items = sorted(os.listdir(full))
        return {"uri":args["uri"],"type":"directory","items":items[:50],"total":len(items)}
    content = full.read_text()
    lines = content.split("\n")
    ml = args.get("max_lines",50)
    return {"uri":args["uri"],"type":"file","size":len(content),"lines":len(lines),"content":"\n".join(lines[:ml]),"truncated":len(lines)>ml}

def handle_search(args):
    r = dm.load_registry()
    query = args.get("query","")
    domains = set(args.get("domains",[])) if args.get("domains") else None
    max_r = args.get("max_results",10)
    results = []
    for d in r:
        did = d["id"]
        if domains and did not in domains:
            continue
        p = dm.resolve_path(d)
        if not p.exists():
            continue
        for sd in ["CLAUDE.md","_control/STATE.md","_knowledge"]:
            sp = p/sd
            if not sp.exists():
                continue
            try:
                cmd = ["grep","-rn","--include=*.md","--include=*.yaml","-l",query,str(sp)]
                rr = subprocess.run(cmd,capture_output=True,text=True,timeout=10)
                for line in rr.stdout.strip().split("\n"):
                    if line and len(results)<max_r:
                        try:
                            rel = str(Path(line).relative_to(p))
                        except Exception:
                            rel = line
                        results.append({"uri":f"bos://{did}/{rel}","domain":did,"file":rel})
            except Exception:
                pass
    return {"results":results,"total":len(results)}

HANDLERS = {
    "domain_list": handle_domain_list, "domain_stats": handle_domain_stats,
    "domain_resolve": handle_resolve, "domain_read": handle_read, "domain_search": handle_search,
    "domain_validate": handle_domain_validate, "domain_tree": handle_domain_tree,
    "ecos_health": handle_ecos_health, "ecos_brief": handle_ecos_brief,
    "bos_routes": handle_bos_routes,
    "workflow_list": handle_workflow_list, "workflow_show": handle_workflow_show, "workflow_relations": handle_workflow_relations,
}

def main():
    for line in sys.stdin:
        try:
            req = json.loads(line)
        except Exception:
            continue
        method = req.get("method","")
        rid = req.get("id")
        if method == "tools/list":
            resp = {"jsonrpc":"2.0","id":rid,"result":{"tools":TOOLS}}
        elif method == "tools/call":
            params = req.get("params",{})
            name = params.get("name","")
            args = params.get("arguments",{})
            handler = HANDLERS.get(name)
            result = handler(args) if handler else {"error":f"Unknown: {name}"}
            resp = {"jsonrpc":"2.0","id":rid,"result":{"content":[{"type":"text","text":json.dumps(result,indent=2,ensure_ascii=False)}]}}
        else:
            resp = {"jsonrpc":"2.0","id":rid,"error":{"code":-32601,"message":"Method not found"}}
        sys.stdout.write(json.dumps(resp)+"\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()


def handle_search(args):
    r = dm.load_registry()
    query = args.get("query", "")
    domains = set(args.get("domains", [])) if args.get("domains") else None
    max_r = args.get("max_results", 10)
    results = []
    for d in r:
        did = d["id"]
        if domains and did not in domains:
            continue
        p = dm.resolve_path(d)
        if not p.exists():
            continue
        for sd in ["CLAUDE.md", "_control/STATE.md", "_knowledge"]:
            sp = p / sd
            if not sp.exists():
                continue
            try:
                cmd = [
                    "grep",
                    "-rn",
                    "--include=*.md",
                    "--include=*.yaml",
                    "-l",
                    query,
                    str(sp),
                ]
                rr = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                for line in rr.stdout.strip().split("\n"):
                    if line and len(results) < max_r:
                        try:
                            rel = str(Path(line).relative_to(p))
                        except Exception:
                            rel = line
                        results.append(
                            {"uri": f"bos://{did}/{rel}", "domain": did, "file": rel}
                        )
            except Exception:
                pass
    return {"results": results, "total": len(results)}


HANDLERS = {
    "domain_list": handle_domain_list,
    "domain_stats": handle_domain_stats,
    "domain_resolve": handle_resolve,
    "domain_read": handle_read,
    "domain_search": handle_search,
    "domain_validate": handle_domain_validate,
    "domain_tree": handle_domain_tree,
    "ecos_health": handle_ecos_health,
    "ecos_brief": handle_ecos_brief,
    "bos_routes": handle_bos_routes,
    "workflow_list": handle_workflow_list,
    "workflow_show": handle_workflow_show,
    "workflow_relations": handle_workflow_relations,
}


def main():
    for line in sys.stdin:
        try:
            req = json.loads(line)
        except Exception:
            continue
        method = req.get("method", "")
        rid = req.get("id")
        if method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name", "")
            args = params.get("arguments", {})
            handler = HANDLERS.get(name)
            result = handler(args) if handler else {"error": f"Unknown: {name}"}
            resp = {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2, ensure_ascii=False),
                        }
                    ]
                },
            }
        else:
            resp = {
                "jsonrpc": "2.0",
                "id": rid,
                "error": {"code": -32601, "message": "Method not found"},
            }
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
