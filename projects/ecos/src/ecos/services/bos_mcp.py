#!/usr/bin/env python3
"""BOS MCP Server — 暴露 domain_read/resolve/search 给 cockpit MCP"""
import sys, os, json, yaml
from pathlib import Path

H = Path.home()
ECOS_SRC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ECOS_SRC))

from importlib.machinery import SourceFileLoader
DM_PATH = ECOS_SRC / "services" / "domain_manager.py"
dm = SourceFileLoader("dm", str(DM_PATH)).load_module()

TOOLS = [
    {
        "name": "domain_resolve",
        "description": "将 BOS URI 解析为物理路径。bos://vault/_state → /Users/xm/Documents/@学习进化/_control/STATE.md",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uri": {"type": "string", "description": "BOS URI, e.g. bos://vault/_state"}
            },
            "required": ["uri"]
        }
    },
    {
        "name": "domain_read",
        "description": "通过 BOS URI 读取域资源内容。支持语义化快捷方式 (_state/_memory/_claude等)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uri": {"type": "string", "description": "BOS URI"},
                "max_lines": {"type": "integer", "description": "最大行数·默认50"}
            }
        }
    },
    {
        "name": "domain_list",
        "description": "列出所有已注册域·支持按类型过滤",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["document","config","engine","tool","workspace","storage","model"]}
            }
        }
    },
    {
        "name": "domain_search",
        "description": "跨域搜索内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "domains": {"type": "array", "items": {"type": "string"}, "description": "限定域ID列表"},
                "max_results": {"type": "integer", "default": 10}
            },
            "required": ["query"]
        }
    },
    {
        "name": "workflow_run",
        "description": "通过 BOS URI 触发工作流执行·bos://ecos/workflow/{name} → 路由到对应层执行器",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "工作流名称或 WORKFLOW-ID"},
                "params": {"type": "object", "description": "执行参数"},
                "dry_run": {"type": "boolean", "default": False}
            },
            "required": ["name"]
        }
    },
]

def handle_resolve(uri):
    registry = dm.load_registry()
    d, sub = dm.parse_bos_uri(uri, registry)
    if not d:
        return {"error": f"无法解析: {uri}"}
    p = dm.resolve_path(d)
    full = str(p / sub if sub else p)
    return {
        "uri": uri,
        "physical_path": full,
        "exists": os.path.exists(full),
        "domain": d.get("name", d["id"]),
        "type": d.get("domain_type", "?"),
        "layer": d.get("layer", "?")
    }

def handle_read(uri, max_lines=50):
    registry = dm.load_registry()
    d, sub = dm.parse_bos_uri(uri, registry)
    if not d:
        return {"error": f"无法解析: {uri}"}
    p = dm.resolve_path(d)
    full = p / sub if sub else p
    if not full.exists():
        return {"error": f"不存在: {full}"}
    if full.is_dir():
        items = sorted(os.listdir(full))
        return {"uri": uri, "type": "directory", "items": items[:50], "total": len(items)}
    content = full.read_text()
    lines = content.split("\n")
    return {
        "uri": uri,
        "type": "file",
        "size": len(content),
        "lines": len(lines),
        "content": "\n".join(lines[:max_lines]),
        "truncated": len(lines) > max_lines
    }

def handle_list(domain_type=None):
    registry = dm.load_registry()
    result = []
    for d in registry:
        if domain_type and d.get("domain_type") != domain_type:
            continue
        result.append({
            "id": d["id"],
            "name": d.get("name", ""),
            "type": d.get("domain_type", "document"),
            "layer": d.get("layer", "L4"),
            "status": d.get("status", "active"),
            "bos_uri": f"bos://{d['id']}"
        })
    return {"domains": result, "total": len(result)}

def handle_search(query, domains=None, max_results=10):
    registry = dm.load_registry()
    results = []
    import subprocess
    
    target_domains = set(domains) if domains else None
    
    for d in registry:
        did = d["id"]
        if target_domains and did not in target_domains:
            continue
        p = dm.resolve_path(d)
        if not p.exists():
            continue
        
        # grep in CLAUDE.md, STATE.md, and _knowledge/
        search_paths = [p / "CLAUDE.md", p / "_control" / "STATE.md"]
        kd = p / "_knowledge"
        if kd.exists():
            search_paths.append(kd)
        
        for sp in search_paths:
            if not sp.exists():
                continue
            try:
                if sp.is_dir():
                    cmd = ["grep", "-rl", "--include=*.md", query, str(sp)]
                else:
                    cmd = ["grep", "-l", query, str(sp)]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                for line in r.stdout.strip().split("\n"):
                    if line and len(results) < max_results:
                        results.append({
                            "uri": f"bos://{did}/{Path(line).relative_to(p)}",
                            "domain": did,
                            "file": str(Path(line).relative_to(p))
                        })
            except:
                pass
    
    return {"results": results, "total": len(results)}

def handle_workflow_run(name, params=None, dry_run=False):
    """通过 BOS URI 触发工作流执行"""
    W = ECOS_SRC / "ssot"
    M1_WF = W / "mof" / "m1" / "workflow"
    if not M1_WF.exists():
        return {"error": "M1 workflow 目录不存在"}

    name_lower = name.lower()
    node = None
    for f in sorted(M1_WF.glob("WORKFLOW-*.yaml")):
        try:
            n = yaml.safe_load(open(f))
            if n and n.get("type") == "Workflow":
                nid = n.get("id", "").lower()
                kebab = nid.replace("workflow-", "").replace("_", "-")
                if name_lower == nid or name_lower in nid or name_lower == kebab:
                    node = n; break
        except: pass

    if not node:
        return {"error": f"工作流未找到: {name}"}

    bos_uri = node.get("bos_uri")
    cross = node.get("cross_layer", {})
    realized = cross.get("realized_by", [{}])[0]

    result = {
        "workflow": node.get("name"),
        "id": node.get("id"),
        "bos_uri": bos_uri,
        "layer": node.get("layer"),
        "subtype": node.get("subtype"),
        "realized_by": f"{realized.get('project', '?')}/{realized.get('package', '?')}",
        "entrypoint": realized.get("entrypoint", "?"),
        "steps_count": len(node.get("steps", [])),
        "dry_run": dry_run,
    }

    if dry_run:
        result["status"] = "validated"
        result["steps"] = [
            {"order": s.get("order"), "name": s.get("name"), "action": s.get("action")}
            for s in node.get("steps", [])
        ]
    else:
        result["status"] = "routed"
        result["message"] = f"已通过 BOS URI 路由到 {result['layer']} 层 {result['realized_by']} 执行器"
        result["note"] = "实际执行需 Agora Service Mesh 动态代理"

    return result

def main():
    # MCP stdio protocol
    for line in sys.stdin:
        try:
            req = json.loads(line)
        except:
            continue
        
        method = req.get("method", "")
        req_id = req.get("id")
        
        if method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name", "")
            args = params.get("arguments", {})
            
            if tool_name == "domain_resolve":
                result = handle_resolve(args.get("uri", ""))
            elif tool_name == "domain_read":
                result = handle_read(args.get("uri", ""), args.get("max_lines", 50))
            elif tool_name == "domain_list":
                result = handle_list(args.get("type"))
            elif tool_name == "domain_search":
                result = handle_search(args.get("query", ""), args.get("domains"), args.get("max_results", 10))
            elif tool_name == "workflow_run":
                result = handle_workflow_run(args.get("name", ""), args.get("params"), args.get("dry_run", False))
            else:
                result = {"error": f"Unknown tool: {tool_name}"}
            
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}}
        else:
            resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}
        
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
