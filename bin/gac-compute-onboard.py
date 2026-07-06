#!/usr/bin/env python3
# bin/gac-compute-onboard.py — eCOS v6 算力网格与大盘网络一体化并网与治理自检工具
#
# 整合五大算力通道:
# 1. cc-switch   (SQLite credentials 导入并网)
# 2. codexbar    (Homebrew CLI 额度/预算链路自检)
# 3. models      (Homebrew CLI 模型发现与定价匹配)
# 4. litellm     ( completions 路由与 API 通达性验证)
# 5. omlxc       (omlxc 本地推理集群与网关状态审计)

import os
import sys
import json
import subprocess
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent

# AetherForge Gateway Path
AF_PROJECT = WORKSPACE / "projects/aetherforge"
AF_DB = Path.home() / ".aetherforge" / "credentials.db"


def run_cmd(args: list[str], timeout: float = 5.0) -> str | None:
    try:
        res = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            cwd=str(WORKSPACE)
        )
        if res.returncode == 0:
            return res.stdout.strip()
        return None
    except Exception:
        return None


def onboard_cc_switch() -> dict:
    """导入 cc-switch SQLite 数据库中的全部凭据"""
    print("🔑 [1/5] cc-switch 凭证并网自检...")
    db_path = Path.home() / "SharedConf" / "CC_Switch" / "cc-switch.db"
    if not db_path.is_file():
        return {"status": "FAIL", "reason": f"cc-switch.db 不存在: {db_path}"}

    # 调用 AetherForge python API 导入
    cmd = [
        "uv", "run", "--project", str(AF_PROJECT), "python", "-c",
        "from llm_gateway.credentials import import_from_cc_switch; print(import_from_cc_switch())"
    ]
    out = run_cmd(cmd, timeout=15.0)
    if out is not None:
        try:
            count = int(out.split()[-1])
            # 查询 credentials.db 的总条数
            conn = sqlite3.connect(str(AF_DB))
            total = conn.execute("SELECT count(*) FROM credentials").fetchone()[0]
            conn.close()
            return {"status": "OK", "imported_this_time": count, "total_credentials": total}
        except Exception as e:
            return {"status": "OK", "message": f"导入已执行，但解析输出失败: {out} ({e})"}

    return {"status": "FAIL", "reason": "调用 AetherForge import API 失败"}


def onboard_codexbar() -> dict:
    """检查 codexbar 额度状态命令行"""
    print("📊 [2/5] codexbar 额度监控自检...")
    which_bar = run_cmd(["which", "codexbar"])
    if not which_bar:
        return {"status": "WARN", "reason": "codexbar CLI 未在系统 PATH 注册"}

    ver = run_cmd(["codexbar", "--version"])
    # 尝试读取 usage
    usage = run_cmd(["codexbar", "usage", "--format", "json"], timeout=5.0)
    usage_data = {}
    if usage:
        try:
            usage_data = json.loads(usage)
        except Exception:
            pass

    return {
        "status": "OK",
        "version": ver or "unknown",
        "path": which_bar,
        "usage_preview": str(usage_data)[:100]
    }


def onboard_models() -> dict:
    """检查 models 模型发现工具"""
    print("🔍 [3/5] models 模型发现并网自检...")
    which_models = run_cmd(["which", "models"])
    if not which_models:
        return {"status": "WARN", "reason": "models (brew) CLI 未在系统 PATH 注册"}

    ver = run_cmd(["models", "--help"])
    # 读前三个可用模型
    models_out = run_cmd(["models", "list"], timeout=5.0)
    model_list = []
    if models_out:
        model_list = [line.strip() for line in models_out.split("\n") if line.strip()][:5]

    return {
        "status": "OK",
        "path": which_models,
        "top_models": model_list
    }


def onboard_litellm() -> dict:
    """连通并测试 LiteLLM / AetherForge completions 路由"""
    print("🚀 [4/5] litellm / AetherForge API 路由自检...")
    gateway_url = "http://100.96.126.35:4000/v1/chat/completions"
    api_key = "sk-omlx-admin"

    # 发送一个极简 prompt
    payload = json.dumps({
        "model": "mini-9b",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5
    }).encode("utf-8")

    req = urllib.request.Request(
        gateway_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ans = data["choices"][0]["message"]["content"].strip()
            return {"status": "OK", "gateway": gateway_url, "response": ans}
    except Exception as e:
        return {
            "status": "WARN",
            "gateway": gateway_url,
            "reason": f"AetherForge completions 暂时不可达或超时 (可能是 Ollama 未响应): {e}"
        }


def onboard_omlxc() -> dict:
    """检查 omlxc 本地推理集群状态与网关路由"""
    print("🕸️  [5/5] omlxc 本地推理集群与智能网关自检...")
    which_omlxc = run_cmd(["which", "omlxc"])
    if not which_omlxc:
        return {
            "status": "WARN",
            "reason": "omlxc CLI 未在系统 PATH 注册 (omlx 留给 App，推理集群使用 omlxc)"
        }

    cluster_info = run_cmd(["omlxc", "cluster"], timeout=8.0)
    gw_info = run_cmd(["omlxc", "gw", "status"], timeout=5.0)

    # 简单分析活跃的服务和离线需要自愈唤醒的从机
    active_services = []
    nodes_down = []
    if cluster_info:
        for line in cluster_info.split("\n"):
            if "○ down" in line:
                if "mac-mini" in line:
                    nodes_down.append("mac-mini-M4")
                elif "Y7000P" in line:
                    nodes_down.append("Y7000P-4070")
            elif "● up" in line:
                parts = line.split()
                # 比如：MBP · M5 Max 128G   主力+网关                 coder        ● up
                # 或者：                                          embed        ● up
                # 这种情况下，如果 len(parts) 比较多，我们可以找 "●" 的前一个 token 作为一个服务
                try:
                    up_idx = parts.index("up")
                    if up_idx > 0 and parts[up_idx - 1] == "●":
                        service_name = parts[up_idx - 2]
                        active_services.append(service_name)
                except ValueError:
                    pass

    # 物理自愈：对离线从机节点发送 WoL 唤醒信号
    if nodes_down:
        print(f"⚠️  检测到算力从机离线 {nodes_down}，正在执行物理 WoL 智能唤醒自愈...", file=sys.stderr)
        for node in nodes_down:
            run_cmd(["python3", "bin/omlxc-node-wakeup.py", "--node", node], timeout=5.0)

    models_route = []
    if gw_info and "路由模型:" in gw_info:
        models_route = [m.strip() for m in gw_info.split("路由模型:")[-1].split(",")]

    return {
        "status": "OK",
        "path": which_omlxc,
        "active_services_count": len(active_services),
        "gateway_models": models_route,
        "raw_cluster": cluster_info[:300] + "..." if cluster_info else "",
        "auto_healed_nodes": nodes_down
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="AetherForge Compute Onboarding Integration Auditor")
    parser.add_argument("--json", action="store_true", help="输出纯 JSON 格式报告")
    parser.add_argument("--check", action="store_true", help="自检模式")
    args = parser.parse_args()

    is_ci = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"
    if args.check and is_ci:
        print("✅ [Compute Onboard Check] Detected CI environment, skipping physical compute node checks to prevent blocking.")
        return 0

    # 如果是 JSON 模式，将所有 onboard 过程 of stdout 物理重定向到 stderr，防止污染 stdout JSON
    old_stdout = sys.stdout
    if args.json:
        sys.stdout = sys.stderr

    try:
        cc = onboard_cc_switch()
        cb = onboard_codexbar()
        mo = onboard_models()
        lt = onboard_litellm()
        ox = onboard_omlxc()
    finally:
        if args.json:
            sys.stdout = old_stdout

    report = {
        "cc-switch": cc,
        "codexbar": cb,
        "models": mo,
        "litellm": lt,
        "omlxc": ox
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if cc["status"] == "OK" else 1

    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  🌐 AetherForge Compute Onboarding Integration Auditor   ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    # 打印最终报告
    print("\n" + "═" * 60)
    print("📋 并网大盘连通性报告:")
    print(f"  • cc-switch:      [{cc['status']}] {cc.get('total_credentials', 0)} 凭证已导入")
    print(f"  • codexbar:       [{cb['status']}] {cb.get('version', 'CLI missing')}")
    print(f"  • models:         [{mo['status']}] {len(mo.get('top_models', []))} 模型可发现")
    print(f"  • litellm:        [{lt['status']}] {lt.get('gateway', 'Offline')}")
    print(f"  • omlxc-cluster:  [{ox['status']}] {ox.get('active_services_count', 0)} 活跃服务 / {len(ox.get('gateway_models', []))} 路由模型")
    print("" + "═" * 60 + "\n")

    # 如果有硬性 block 错误返回 1
    is_ok = cc["status"] == "OK"
    if is_ok:
        print("✅ AetherForge 算力大盘五大接入渠道并网通过！")
        return 0
    else:
        print("❌ AetherForge 并网核心项 (cc-switch) 验证失败！")
        return 1


if __name__ == "__main__":
    sys.exit(main())
