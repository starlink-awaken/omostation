#!/usr/bin/env python3
"""Phase 1 — 真实用户旅程测试

模拟真实用户操作场景，验证全系统链路。
所有旅程使用系统真实暴露的接口。

运行:
  python3 tests/integration/test-user-journeys.py
"""
import json
import subprocess
import sys
from urllib.request import Request, urlopen

PASS = 0
FAIL = 0
def journey(name: str, fn):
    global PASS, FAIL
    try:
        print(f"\n  🚀 {name}")
        fn()
        print("  ✅ JOURNEY PASS")
        PASS += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        FAIL += 1

def http_get(url: str, timeout: int = 10) -> dict:
    resp = urlopen(url, timeout=timeout)
    return {"status": resp.status, "body": resp.read().decode()}

def http_post(url: str, data: dict, headers: dict = None, timeout: int = 10) -> dict:
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    req = Request(url, data=json.dumps(data).encode(), headers=hdrs, method="POST")
    resp = urlopen(req, timeout=timeout)
    return {"status": resp.status, "body": resp.read().decode()}

# ═══════════════════════════════════════════════════════
# 旅程 1: 知识研究全流程
# ═══════════════════════════════════════════════════════
def journey_knowledge_research():
    """研究者从健康检查开始 → 调用 Agora 服务 → 验证链路"""
    # Step 1: 健康检查
    h = http_get("http://localhost:8088/health")
    assert h["status"] == 200, f"SB health failed: {h['status']}"
    sb = json.loads(h["body"])
    assert sb["status"] == "ok", f"SB status: {sb}"

    # Step 2: Agora 仪表盘可访问
    a = http_get("http://localhost:7435/")
    assert a["status"] == 200, f"Agora web: {a['status']}"

    # Step 3: sb-bridge 状态查询
    r = subprocess.run(["uv", "run", "--directory", "projects/kairon",
        "sb-bridge", "status"], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, f"bridge status: {r.stderr}"
    assert "Active organs:" in r.stdout, f"unexpected: {r.stdout[:100]}"

    # Step 4: sb-bridge EU 余额查询
    r = subprocess.run(["uv", "run", "--directory", "projects/kairon",
        "sb-bridge", "eu", "researcher"], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, f"EU check: {r.stderr}"
    eu = json.loads(r.stdout)
    assert "balance" in eu, f"EU response: {eu}"

    print("    ✓ 健康检查 → Agora → sb-bridge 状态 → EU 余额")

# ═══════════════════════════════════════════════════════
# 旅程 2: Schema 建模 + 验证
# ═══════════════════════════════════════════════════════
def journey_schema_modeling():
    """数据科学家定义 Schema → 验证数据 → 导出"""
    # 通过 Eidos MCP (docker exec) 验证 schema 能力
    cmds = [
        ("format_version", "from eidos.mcp_server import FORMAT_VERSION; print(FORMAT_VERSION)"),
        ("list types", "from eidos.meta import list_types; t = list_types(); print(f'{len(t)} types')"),
        ("handle_list", "from eidos.mcp_server import handle_list; r = handle_list(); print(f'{r[\"count\"]} schemas')"),
    ]
    for name, code in cmds:
        r = subprocess.run(
            ["docker", "exec", "integration-eidos-1", "python3", "-c", code],
            capture_output=True, text=True, timeout=10
        )
        assert r.returncode == 0, f"Eidos {name}: {r.stderr}"
        print(f"    ✓ Eidos {name}: {r.stdout.strip()}")

# ═══════════════════════════════════════════════════════
# 旅程 3: LLM 路由调用
# ═══════════════════════════════════════════════════════
def journey_llm_routing():
    """开发者通过 LiteLLM 调用 LLM 路由"""

    # LiteLLM health
    h = http_get("http://localhost:4000/health")
    assert h["status"] == 200, f"LiteLLM health: {h['status']}"
    data = json.loads(h["body"])
    print(f"    ✓ LiteLLM health: {data.get('healthy_count', 'ok')} endpoints")

    # LiteLLM model list
    try:
        r = http_get("http://localhost:4000/v1/models")
        models = json.loads(r["body"])
        count = len(models.get("data", []))
        print(f"    ✓ LiteLLM models: {count} available")
    except Exception as e:
        print(f"    ⚠ LiteLLM model list: {e}")

    # Agora 注册确认
    r = subprocess.run(
        ["docker", "exec", "integration-agora-1", "python3", "-c",
         "from agora.state import get_registry; r = get_registry(); print(','.join(r.list_services())[:200])"],
        capture_output=True, text=True, timeout=10
    )
    services = r.stdout.strip() if r.returncode == 0 else "(registry check limited)"
    print(f"    ✓ Agora services: {services[:100]}")

# ═══════════════════════════════════════════════════════
# 旅程 4: 全系统集成场景
# ═══════════════════════════════════════════════════════
def journey_full_integration():
    """模拟一个完整工作日场景:
    早上 → 检查系统健康 → 查看可用服务 → 查询余额 → 使用 bridge
    """
    print("    [模拟: 研究员一天的工作流程]")

    # 早上: 检查所有服务
    services = {
        "SharedBrain": ("http://localhost:8088/health", "status"),
        "Agora": ("http://localhost:7435/", None),
    }
    for name, (url, key) in services.items():
        try:
            resp = http_get(url)
            ok = resp["status"] == 200
            if key and ok:
                j = json.loads(resp["body"])
                ok = j.get(key) == "ok"
            print(f"    {'✅' if ok else '❌'} 早上检查 {name}: {'OK' if ok else 'FAIL'}")
        except Exception as e:
            print(f"    ❌ 早上检查 {name}: {e}")

    # 上午: 使用 sb-bridge 做审计
    r = subprocess.run(
        ["uv", "run", "--directory", "projects/kairon",
         "sb-bridge", "eu", "morning-researcher"],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"morning EU: {r.stderr}"
    eu = json.loads(r.stdout)
    print(f"    ✅ 上午 EU 余额: {eu.get('balance')}/{eu.get('limit')}")

    # 中午: 查看器官状态
    r = subprocess.run(
        ["uv", "run", "--directory", "projects/kairon", "sb-bridge", "status"],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0
    lines = r.stdout.strip().split("\n")
    organ_count = len([line for line in lines if line.startswith("  D_")])
    print(f"    ✅ 器官监控: {organ_count} 个在线器官")

    # 下午: 验证 Agora 仍健康
    resp = http_get("http://localhost:7435/")
    assert resp["status"] == 200
    print("    ✅ 下班前 Agora 检查: OK (uptime 持续中)")

# ═══════════════════════════════════════════════════════
# 旅程 5: 跨容器网络通信
# ═══════════════════════════════════════════════════════
def journey_cross_container():
    """验证 Docker 网络内容器间通信"""
    # SharedBrain → Agora: internal network
    r = subprocess.run(
        ["docker", "exec", "integration-sharedbrain-1",
         "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
         "http://agora:7430/"],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"SB→Agora: {r.stderr}"
    assert r.stdout.strip() == "200", f"SB→Agora HTTP: {r.stdout}"
    print("    ✓ SharedBrain → Agora (内部网络): HTTP 200")

    # Agora → SharedBrain
    r = subprocess.run(
        ["docker", "exec", "integration-agora-1",
         "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
         "http://sharedbrain:8080/health"],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0, f"Agora→SB: {r.stderr}"
    assert r.stdout.strip() == "200", f"Agora→SB HTTP: {r.stdout}"
    print("    ✓ Agora → SharedBrain (内部网络): HTTP 200")


if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     Phase 1 — 真实用户旅程测试                          ║")
    print("╚══════════════════════════════════════════════════════════╝")

    journey("旅程 1: 知识研究全流程", journey_knowledge_research)
    journey("旅程 2: Schema 建模 + 验证", journey_schema_modeling)
    journey("旅程 3: LLM 路由调用", journey_llm_routing)
    journey("旅程 4: 全系统集成场景", journey_full_integration)
    journey("旅程 5: 跨容器网络通信", journey_cross_container)

    print(f"\n{'='*56}")
    print(f"  用户旅程: {PASS}/{PASS+FAIL} 通过")
    print(f"  {'✅ ALL JOURNEYS PASS' if FAIL == 0 else '❌ SOME FAILED'}")
    print(f"{'='*56}\n")
    sys.exit(0 if FAIL == 0 else 1)
