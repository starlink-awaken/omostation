#!/usr/bin/env python3
# bin/gac-ingress-check.py — C2G 自愈式策略输入链预审工具
# Phase B (2026-07-03): eCOS v6 Architecture Integration
# 在 PO Pitch/任务落盘前检测: 端口冲突 / 服务重名 / 路径重叠 / KOS 图谱冲突

from __future__ import annotations

import sys
import sqlite3
import json
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

WORKSPACE = Path(__file__).resolve().parent.parent
PORT_REGISTRY = WORKSPACE / "protocols/port-registry.yaml"
PROJECT_REGISTRY = WORKSPACE / "docs/project-registry.yaml"
db_path = WORKSPACE / "kos/kos-index.sqlite"

# omlx 网关 (Tailscale MBP)
OMLX_GATEWAY = "http://100.96.126.35:4000"
ANALYSIS_MODEL = "mini-9b"


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def get_registered_ports() -> dict[int, str]:
    """从 port-registry.yaml 读取所有已注册端口"""
    data = load_yaml(PORT_REGISTRY)
    result: dict[int, str] = {}
    for section in ["system", "services", "tools", "mesh"]:
        for entry in data.get(section, []):
            if isinstance(entry, dict):
                port = entry.get("port")
                name = str(entry.get("name", entry.get("service", "unknown")))
                if port:
                    result[int(port)] = name
    return result


def get_registered_services() -> set[str]:
    """从 project-registry.yaml 读取所有已注册服务名"""
    data = load_yaml(PROJECT_REGISTRY)
    return set(data.get("projects", {}).keys())


def get_kos_entities() -> list[dict]:
    """从 KOS SQLite 读取所有实体（用于依赖分析）"""
    if not db_path.is_file():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT entity_id, label, entity_type FROM kos_entities LIMIT 500"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def extract_ports_from_text(text: str) -> list[int]:
    """从自由文本中提取可能的端口号"""
    patterns = [
        r"端口\s*[：:]\s*(\d{4,5})",
        r"port\s*[：:=]\s*(\d{4,5})",
        r":(\d{4,5})\b",
        r"\b(\d{4,5})\s*端口",
    ]
    ports = set()
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            p = int(m.group(1))
            if 1024 <= p <= 65535:
                ports.add(p)
    return sorted(ports)


def extract_service_names_from_text(text: str) -> list[str]:
    """从自由文本中提取可能的服务名"""
    patterns = [
        r"服务名\s*[：:]\s*([a-zA-Z0-9_-]+)",
        r"项目名\s*[：:]\s*([a-zA-Z0-9_-]+)",
        r"service[:\s]+([a-zA-Z0-9_-]+)",
        r"project[:\s]+([a-zA-Z0-9_-]+)",
    ]
    names: list[str] = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            names.append(m.group(1))
    return names


def llm_dependency_analysis(pitch_text: str, kos_summary: str) -> str:
    """调用本地 LLM 分析 Pitch 中的潜在依赖冲突"""
    try:
        prompt = f"""你是 eCOS 架构治理专家。分析以下 Pitch 文档，结合现有系统拓扑，识别潜在的架构风险：

**现有系统关键实体摘要**：
{kos_summary[:800]}

**待审查的 Pitch 内容**：
{pitch_text[:1000]}

请用 JSON 格式输出分析结果，包含以下字段：
{{
  "risk_level": "low/medium/high",
  "risks": ["风险描述1", "风险描述2"],
  "suggestions": ["建议1", "建议2"]
}}

只输出 JSON，不要其他文字。"""

        payload = json.dumps({
            "model": ANALYSIS_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{OMLX_GATEWAY}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            # 尝试提取 JSON
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                return json_match.group(0)
            return content
    except Exception as e:
        return json.dumps({"risk_level": "unknown", "risks": [f"LLM 分析不可用: {e}"], "suggestions": []})


def run_check(pitch_text: str, verbose: bool = True) -> dict[str, Any]:
    """执行完整的 Ingress 预审检查"""
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    # === 检查 1: 端口冲突检测 ===
    registered_ports = get_registered_ports()
    found_ports = extract_ports_from_text(pitch_text)
    for p in found_ports:
        if p in registered_ports:
            issues.append({
                "type": "PORT_CONFLICT",
                "severity": "CRITICAL",
                "detail": f"端口 {p} 已被 '{registered_ports[p]}' 占用 (port-registry.yaml)",
            })

    # === 检查 2: 服务名冲突检测 ===
    registered_services = get_registered_services()
    found_services = extract_service_names_from_text(pitch_text)
    for svc in found_services:
        if svc.lower() in {s.lower() for s in registered_services}:
            warnings.append({
                "type": "SERVICE_NAME_COLLISION",
                "severity": "WARNING",
                "detail": f"服务名 '{svc}' 与已有项目重名 (project-registry.yaml)，请确认是否为迭代而非新建",
            })

    # === 检查 3: KOS LLM 语义冲突分析 ===
    kos_entities = get_kos_entities()
    kos_summary = "\n".join(
        f"- [{e['entity_type']}] {e['label']}" for e in kos_entities[:30]
    )
    llm_result_raw = llm_dependency_analysis(pitch_text, kos_summary)
    llm_result: dict[str, Any] = {}
    try:
        llm_result = json.loads(llm_result_raw)
    except Exception:
        llm_result = {"risk_level": "unknown", "risks": [llm_result_raw[:200]], "suggestions": []}

    # 汇总结果
    result: dict[str, Any] = {
        "pass": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "llm_analysis": llm_result,
        "scanned_ports": found_ports,
        "scanned_services": found_services,
    }

    if verbose:
        _print_report(result)

    return result


def _print_report(result: dict[str, Any]) -> None:
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  📋 C2G Ingress Pre-Check Report (eCOS v6 Self-Correct)  ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    if result["scanned_ports"]:
        print(f"🔍 检测到端口声明: {result['scanned_ports']}")
    if result["scanned_services"]:
        print(f"🔍 检测到服务名声明: {result['scanned_services']}")

    if result["issues"]:
        print("\n❌ CRITICAL 阻断问题:")
        for issue in result["issues"]:
            print(f"  [{issue['severity']}] {issue['type']}: {issue['detail']}")

    if result["warnings"]:
        print("\n⚠️  WARNING 告警:")
        for w in result["warnings"]:
            print(f"  [{w['severity']}] {w['type']}: {w['detail']}")

    llm = result.get("llm_analysis", {})
    risk = llm.get("risk_level", "unknown")
    risk_icon = {"low": "✅", "medium": "⚠️", "high": "❌"}.get(risk, "❓")
    print(f"\n🤖 LLM 语义架构分析 (mini-9b): {risk_icon} {risk.upper()}")
    for r in llm.get("risks", []):
        print(f"  • 风险: {r}")
    for s in llm.get("suggestions", []):
        print(f"  → 建议: {s}")

    overall = "✅ PASS — 无阻断性冲突，可继续落盘" if result["pass"] else "❌ BLOCKED — 存在致命冲突，任务禁止落盘"
    print(f"\n{'─' * 60}")
    print(f"  结论: {overall}")
    print(f"{'─' * 60}\n")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="C2G Ingress pre-check tool")
    parser.add_argument("--pitch", "-p", help="Pitch 文本内容（直接传字符串）")
    parser.add_argument("--file", "-f", help="Pitch 文本文件路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式报告")
    parser.add_argument("--no-verbose", action="store_true", help="静默模式，不打印报告")
    args = parser.parse_args()

    pitch_text = ""
    if args.file:
        pitch_text = Path(args.file).read_text(encoding="utf-8")
    elif args.pitch:
        pitch_text = args.pitch
    elif not sys.stdin.isatty():
        pitch_text = sys.stdin.read()
    else:
        # 自检模式（无参数运行时做一次 smoke test）
        pitch_text = "新建服务 mesh-router，监听端口 7435，服务名 mesh-router，依赖 KOS 图谱进行路由决策。"

    result = run_check(pitch_text, verbose=not args.no_verbose)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
