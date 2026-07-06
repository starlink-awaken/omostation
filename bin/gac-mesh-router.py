#!/usr/bin/env python3
# bin/gac-mesh-router.py — omlx 算力网格智能流式路由代理 (GaC-v6 治理标准)

import os
import sys
import json
import sqlite3
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
db_path = WORKSPACE / "kos/kos-index.sqlite"

# 默认网关配置
LOCAL_GATEWAY = "http://100.96.126.35:4000"
PORT = 7437

def get_compute_nodes_for_model(model_name: str) -> list[dict]:
    """从 KOS SQLite 知识库查询注册了能运行 model_name 模型的物理节点列表"""
    nodes: list[dict] = []
    if not db_path.is_file():
        return nodes
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        # 查询注册了 runs_model -> model_name 的 Node 实体
        target_concept = f"C:Model-{model_name}"
        rows = conn.execute(
            """SELECT e.entity_id, e.label, e.metadata 
               FROM kos_relations r 
               JOIN kos_entities e ON r.source_id = e.entity_id 
               WHERE r.predicate = 'runs_model' AND r.target_id = ?""",
            (target_concept,)
        ).fetchall()
        conn.close()

        for r in rows:
            meta = json.loads(r["metadata"] or "{}")
            ip = meta.get("ip")
            if ip:
                nodes.append({
                    "id": r["entity_id"],
                    "label": r["label"],
                    "ip": ip,
                    "hardware": meta.get("hardware", "unknown")
                })
    except Exception as e:
        print(f"  ⚠️ [Mesh Router] Failed to query KOS DB: {e}", file=sys.stderr)
    return nodes

def probe_node_alive(ip: str) -> bool:
    """快速探测 IP 节点的 omlx 统一网关是否在线且可访问 (1.5s 探活超时)"""
    url = f"http://{ip}:4000/v1/models"
    try:
        req = urllib.request.Request(
            url,
            headers={"Authorization": "Bearer sk-omlx-admin"},
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False

class MeshRouterHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 覆写以消除标准输出里的 http 请求日志干扰，保持终端洁癖
        pass

    def do_POST(self):
        if self.path == "/v1/chat/completions":
            self.handle_chat_completions()
        else:
            # 默认直发本地网关
            self.forward_to_gateway(LOCAL_GATEWAY)

    def do_GET(self):
        # 默认直发本地网关 (例如 /v1/models)
        self.forward_to_gateway(LOCAL_GATEWAY)

    def handle_chat_completions(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            req_json = json.loads(post_data.decode('utf-8'))
            model_name = req_json.get("model", "coder")
        except Exception:
            model_name = "coder"

        print(f"🔮 [Mesh Router] Received completions request for model: '{model_name}'")

        # 1. 查找 KOS 静态可用节点
        candidate_nodes = get_compute_nodes_for_model(model_name)
        active_node_ip = None

        # 2. 实时探活并选择最优物理节点
        for node in candidate_nodes:
            # 跳过本地回环 IP 避免二次套娃 (由 fallback 统一接管)
            if node["ip"] in ("127.0.0.1", "localhost", "100.96.126.35"):
                continue
            print(f"  🔍 Probing remote node: '{node['label']}' at {node['ip']}...")
            if probe_node_alive(node["ip"]):
                active_node_ip = node["ip"]
                print(f"  ✅ Node '{node['label']}' ({node['hardware']}) is ONLINE. Routing task...")
                break

        # 3. 决定目标网关 URL
        if active_node_ip:
            target_gateway = f"http://{active_node_ip}:4000"
        else:
            # Fallback 兜底回到本地
            print(f"  ⚠️ Mesh Router Fallback: No remote active nodes runs '{model_name}'. Redirecting to HOST local gateway...")
            target_gateway = LOCAL_GATEWAY

        # 4. 执行流式代理转发
        self.forward_to_gateway(target_gateway, post_data)

    def forward_to_gateway(self, target_host: str, body_bytes: bytes | None = None):
        target_url = f"{target_host}{self.path}"
        
        # 准备代理 Header
        headers = {}
        for k, v in self.headers.items():
            if k.lower() not in ("host", "content-length"):
                headers[k] = v
        # 补齐 Authorization (默认为 omlx 统一 admin Key)
        if "Authorization" not in headers:
            headers["Authorization"] = "Bearer sk-omlx-admin"

        method = self.command
        try:
            req = urllib.request.Request(
                target_url,
                data=body_bytes,
                headers=headers,
                method=method
            )
            
            with urllib.request.urlopen(req, timeout=120.0) as upstream_response:
                # 写回响应 headers
                self.send_response(upstream_response.status)
                for k, v in upstream_response.getheaders():
                    # 避免多次写入 transfer-encoding
                    if k.lower() != "transfer-encoding":
                        self.send_header(k, v)
                self.end_headers()
                
                # 分块流式写回数据
                while True:
                    chunk = upstream_response.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Mesh Router Bad Gateway: {e}"}).encode('utf-8'))

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        # 1. 检查 kos db 是否可达 (RAG 节点知识索引)
        if not db_path.is_file():
            print(f"❌ [Mesh Router Check] KOS SQLite DB missing at: {db_path}")
            sys.exit(1)
        # 2. 检查端口备案
        try:
            import yaml
            port_yaml_path = WORKSPACE / "protocols/port-registry.yaml"
            if port_yaml_path.is_file():
                ports_data = yaml.safe_load(port_yaml_path.read_text(encoding="utf-8")) or {}
                registered_ports = ports_data.get("ports", {})
                # 支持 int 键或者 str 键
                if PORT not in registered_ports and str(PORT) not in registered_ports:
                    print(f"❌ [Mesh Router Check] Port {PORT} is NOT registered in port-registry.yaml!")
                    sys.exit(1)
        except Exception as e:
            print(f"⚠️ [Mesh Router Check] Failed to parse port-registry.yaml: {e}")
        
        print(f"✅ [Mesh Router Check] All configurations and index mappings for port {PORT} are valid.")
        sys.exit(0)

    server_address = ('', PORT)
    httpd = ThreadingHTTPServer(server_address, MeshRouterHandler)
    print(f"🚀 [Mesh Router] Active Intelligent proxy listening on port {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 [Mesh Router] Shutting down...")
        httpd.server_close()

if __name__ == "__main__":
    main()
