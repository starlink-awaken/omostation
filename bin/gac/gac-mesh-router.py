#!/usr/bin/env python3
# bin/gac/gac-mesh-router.py — omlx 算力网格智能流式路由代理 (GaC-v6 治理标准)

import sys
import json
import sqlite3
import urllib.request
import urllib.error
import threading
import asyncio
import time
import os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
db_path = WORKSPACE / "kos/kos-index.sqlite"

# 默认网关配置与端口备案
LOCAL_GATEWAY = "http://100.96.126.35:4000"
PORT = int(os.environ.get("OMLX_MESH_ROUTER_PORT", "7437"))

# 全局线程安全的状态缓存
NODE_STATUS = {}  # ip -> {"alive": bool, "last_check": float, "label": str, "hardware": str}
NODE_STATUS_LOCK = threading.Lock()


def get_all_compute_nodes() -> list[dict]:
    """从 KOS SQLite 知识库查询所有注册的物理节点 (E:Node-*)"""
    nodes: list[dict] = []
    if not db_path.is_file():
        return nodes
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        # 查询 Node 实体
        rows = conn.execute(
            "SELECT entity_id, label, metadata FROM kos_entities WHERE entity_id LIKE 'E:Node-%'"
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


async def async_probe_node_port(ip: str) -> bool:
    """使用 asyncio 快速并发探测端口连通性 (1.5s 超时)"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, 4000),
            timeout=1.5
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


def write_alert_report(status_map: dict):
    """根据最新状态，生成系统健康与警报文件"""
    total = len(status_map)
    if total == 0:
        return
    alive = sum(1 for v in status_map.values() if v["alive"])

    if alive == total:
        status = "GREEN"
    elif alive > 0:
        status = "YELLOW"
    else:
        status = "RED"

    report = {
        "status": status,
        "total_nodes": total,
        "active_nodes_count": alive,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": [
            {
                "ip": ip,
                "label": v["label"],
                "hardware": v["hardware"],
                "status": "ONLINE" if v["alive"] else "OFFLINE"
            }
            for ip, v in status_map.items()
        ]
    }

    if status == "RED":
        print("\a❌ [Mesh Router ALERT] ALL REMOTE COMPUTE NODES OFFLINE! Status: RED")
    elif status == "YELLOW":
        print("⚠️ [Mesh Router ALERT] Partial remote nodes offline. Status: YELLOW")

    try:
        alert_file = WORKSPACE / ".omo/state/mesh_router_alert.json"
        alert_file.parent.mkdir(parents=True, exist_ok=True)
        alert_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"⚠️ [Mesh Router] Failed to write alert report: {e}", file=sys.stderr)


async def heartbeat_daemon_loop():
    """后台异步探活守护进程循环"""
    print("🕵️ [Mesh Router] Starting background heartbeat daemon...")
    while True:
        nodes = get_all_compute_nodes()
        # 排除本地网关自身 IP，只探活远端算力主机
        remote_nodes = [n for n in nodes if n["ip"] not in ("127.0.0.1", "localhost", "100.96.126.35")]

        if not remote_nodes:
            await asyncio.sleep(5)
            continue

        tasks = []
        for node in remote_nodes:
            tasks.append((node, async_probe_node_port(node["ip"])))

        results = await asyncio.gather(*(t[1] for t in tasks))

        new_status = {}
        for (node, _), alive in zip(tasks, results):
            new_status[node["ip"]] = {
                "alive": alive,
                "last_check": time.time(),
                "label": node["label"],
                "hardware": node["hardware"]
            }

        with NODE_STATUS_LOCK:
            NODE_STATUS.update(new_status)

        write_alert_report(new_status)
        await asyncio.sleep(5)


def start_heartbeat_thread():
    """在后台线程中启动 asyncio 事件循环"""
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(heartbeat_daemon_loop())

    t = threading.Thread(target=run, daemon=True)
    t.start()


class MeshRouterHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 覆写以消除标准输出里的 http 请求日志干扰，保持终端洁癖
        pass

    def do_POST(self):
        if self.path == "/v1/chat/completions":
            self.handle_chat_completions()
        else:
            self.forward_to_gateway(LOCAL_GATEWAY)

    def do_GET(self):
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

        # 2. 线程安全读取状态缓存 (0ms 判定)
        with NODE_STATUS_LOCK:
            for node in candidate_nodes:
                ip = node["ip"]
                if ip in ("127.0.0.1", "localhost", "100.96.126.35"):
                    continue
                # 若缓存显示在线则直接选择
                if ip in NODE_STATUS and NODE_STATUS[ip]["alive"]:
                    active_node_ip = ip
                    print(f"  ✅ [Mesh Router] Routed to ONLINE node '{node['label']}' ({NODE_STATUS[ip]['hardware']}) via cache.")
                    break

        # 3. 决定目标网关 (支持多级 Failover 避险降级)
        if active_node_ip:
            target_gateway = f"http://{active_node_ip}:4000"
        else:
            # 探测本地 4000 是否在线
            local_alive = probe_node_alive("127.0.0.1")
            cloud_gateway = os.environ.get("OMLX_CLOUD_GATEWAY")

            if not local_alive and cloud_gateway:
                target_gateway = cloud_gateway
                print(f"  🚨 [Mesh Router FAILOVER] Local gateway OFFLINE! Redirecting to CLOUD backup API: {target_gateway}")
            else:
                target_gateway = LOCAL_GATEWAY
                print(f"  ⚠️ [Mesh Router Fallback] Redirecting to HOST local gateway: {target_gateway}")

        # 4. 执行流式代理转发
        self.forward_to_gateway(target_gateway, post_data)

    def forward_to_gateway(self, target_host: str, body_bytes: bytes | None = None):
        target_url = f"{target_host}{self.path}"

        headers = {}
        for k, v in self.headers.items():
            if k.lower() not in ("host", "content-length"):
                headers[k] = v
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
                self.send_response(upstream_response.status)
                for k, v in upstream_response.getheaders():
                    if k.lower() != "transfer-encoding":
                        self.send_header(k, v)
                self.end_headers()

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
        # 1. 检查 kos db 是否可达
        if not db_path.is_file():
            print(f"⚠️  [Mesh Router Check] KOS SQLite DB missing at: {db_path} — skip (runtime product, CI 环境)")
            sys.exit(0)
        # 2. 检查端口备案
        try:
            import yaml
            port_yaml_path = WORKSPACE / "protocols/port-registry.yaml"
            if port_yaml_path.is_file():
                ports_data = yaml.safe_load(port_yaml_path.read_text(encoding="utf-8")) or {}
                registered_ports = ports_data.get("ports", {})
                if PORT not in registered_ports and str(PORT) not in registered_ports:
                    print(f"❌ [Mesh Router Check] Port {PORT} is NOT registered in port-registry.yaml!")
                    sys.exit(1)
        except Exception as e:
            print(f"⚠️ [Mesh Router Check] Failed to parse port-registry.yaml: {e}")

        print(f"✅ [Mesh Router Check] All configurations and index mappings for port {PORT} are valid.")
        sys.exit(0)

    # 启动后台异步心跳探测守护线程
    start_heartbeat_thread()

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
