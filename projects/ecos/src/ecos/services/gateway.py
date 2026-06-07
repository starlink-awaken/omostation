#!/usr/bin/env python3
"""ecos Gateway — HTTP REST + MCP 统一服务 | Agora 后端 | v1.0"""
import sys, os, json, subprocess
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

H = Path.home()
SCRIPTS = H / ".ecos" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from importlib.machinery import SourceFileLoader
dm = SourceFileLoader("dm", str(SCRIPTS / "domain-manager.py")).load_module()

# ── BOS 核心 ──

def bos_resolve(uri: str):
    """bos://vault/_state → {uri, physical_path, exists, domain, type}"""
    r = dm.load_registry()
    d, s = dm.parse_bos_uri(uri, r)
    if not d: return {"error": f"无法解析: {uri}"}
    p = dm.resolve_path(d)
    full = str(p / s if s else p)
    return {"uri": uri, "physical_path": full, "exists": os.path.exists(full),
            "domain": d.get("name", d["id"]), "type": d.get("domain_type", "?"),
            "layer": d.get("layer", "?")}

def bos_read(uri: str, max_lines=50):
    """读取BOS资源"""
    r = dm.load_registry()
    d, s = dm.parse_bos_uri(uri, r)
    if not d: return {"error": f"无法解析: {uri}"}
    p = dm.resolve_path(d)
    full = p / s if s else p
    if not full.exists(): return {"error": f"不存在: {full}"}
    if full.is_dir():
        items = sorted(os.listdir(full))
        return {"uri": uri, "type": "directory", "items": items[:50], "total": len(items)}
    content = full.read_text()
    lines = content.split("\n")
    return {"uri": uri, "type": "file", "size": len(content), "lines": len(lines),
            "content": "\n".join(lines[:max_lines]), "truncated": len(lines) > max_lines}

def bos_health():
    """全局健康"""
    r = subprocess.run(["python3", str(SCRIPTS/"ecos-health-check.py"), "--json"],
                       capture_output=True, text=True, timeout=30)
    try: return json.loads(r.stdout)
    except: return {"output": r.stdout[:500]}

def bos_domains(dtype=None):
    """域列表"""
    r = dm.load_registry()
    result = []
    for d in r:
        if dtype and d.get("domain_type") != dtype: continue
        result.append({"id": d["id"], "name": d.get("name", ""),
                       "type": d.get("domain_type", "document"),
                       "bos_uri": f"bos://{d['id']}"})
    return {"domains": result, "total": len(result)}

def bos_search(query, domains=None, max_r=10):
    """跨域搜索"""
    r = dm.load_registry()
    results = []
    target = set(domains) if domains else None
    for d in r:
        did = d["id"]
        if target and did not in target: continue
        p = dm.resolve_path(d)
        if not p.exists(): continue
        for sd in ["CLAUDE.md", "_control/STATE.md", "_knowledge"]:
            sp = p / sd
            if not sp.exists(): continue
            try:
                cmd = ["grep", "-rn", "--include=*.md", "--include=*.yaml", "-l", query, str(sp)]
                rr = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                for line in rr.stdout.strip().split("\n"):
                    if line and len(results) < max_r:
                        try: rel = str(Path(line).relative_to(p))
                        except: rel = line
                        results.append({"uri": f"bos://{did}/{rel}", "domain": did, "file": rel})
            except: pass
    return {"results": results, "total": len(results)}

# ── HTTP REST Handler ──

class BosHTTPHandler(BaseHTTPRequestHandler):
    def _send(self, data, status=200):
        body = json.dumps(data, indent=2, ensure_ascii=False)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode())
    
    def do_GET(self):
        path = urlparse(self.path).path
        qs = parse_qs(urlparse(self.path).query)
        
        # /api/v1/bos/{resource}
        if path.startswith("/api/v1/bos/"):
            resource = path.replace("/api/v1/bos/", "")
            
            if resource == "_system/health":
                return self._send(bos_health())
            if resource == "_system/domains":
                return self._send(bos_domains(qs.get("type", [None])[0]))
            if resource.startswith("_search"):
                q = qs.get("q", [""])[0]
                d = qs.get("domains", [None])[0]
                d = d.split(",") if d else None
                return self._send(bos_search(q, d))
            
            # BOS resource read
            uri = f"bos://{resource}" if not resource.startswith("bos://") else resource
            ml = int(qs.get("max_lines", [50])[0])
            result = bos_read(uri, ml)
            return self._send(result, 404 if "error" in result else 200)
        
        # /health
        if path == "/health":
            return self._send({"status": "ok", "service": "ecos-gateway"})
        
        self._send({"error": "not found"}, 404)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def log_message(self, format, *args):
        pass  # 静默日志

# ── 主入口 ──

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "http"
    
    if mode == "http":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
        server = HTTPServer(("127.0.0.1", port), BosHTTPHandler)
        print(f"ecos-gateway HTTP → http://127.0.0.1:{port}/api/v1/bos/")
        print(f"  示例: curl http://127.0.0.1:{port}/api/v1/bos/vault/_state")
        server.serve_forever()
    
    elif mode == "mcp":
        # MCP stdio mode (兼容 Agora 代理)
        from importlib.machinery import SourceFileLoader
        mcp = SourceFileLoader("mcp", str(SCRIPTS / "ecos-mcp-server.py")).load_module()
        mcp.main()
    
    elif mode == "test":
        # 快速测试
        print("=== Health ===")
        print(json.dumps(bos_health(), indent=2, ensure_ascii=False)[:200])
        print("\n=== Resolve ===")
        print(json.dumps(bos_resolve("bos://vault/_state"), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
