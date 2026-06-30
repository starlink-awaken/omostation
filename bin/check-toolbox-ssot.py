#!/usr/bin/env python3
"""
check-toolbox-ssot.py — Validate ToolBox docs against live SSOT

ToolBox 域文档的 SSOT 契约:
  - 所有易变数字 (工具数/端口/节点数/PID/commit hash) 必须来自命令
  - 所有架构版本必须用 "5+4+1+1" 不用 "5+3+1"/"7 层"
  - eCOS 版本必须用 "v6" 不用 "v5"
  - 所有 git commit hash 必须来自 git log 实时

SSOT 真值来源 (运行时探测):
  - 工具数: kairon/packages/forge/tools-registry.json
  - 项目数: docs/project-registry.yaml `projects:` 段
  - M1 domain 节点数: find DOMAIN-*.yaml | wc -l
  - M1 bosroute 节点数: find BOSROUTE-*.yaml | wc -l
  - 服务数: agora/etc/bos-services.yaml
  - 路由数: ~/.ecos/bos/routes.json
  - 端口: protocols/port-registry.yaml
  - PID: launchctl list | grep com.ecos.bos-registry-daemon
  - commit hash: git log --oneline | head -1

用法:
  python3 bin/check-toolbox-ssot.py            # 检查所有 ToolBox docs
  python3 bin/check-toolbox-ssot.py --json     # 机器可读
  python3 bin/check-toolbox-ssot.py --file X   # 单文件
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

WORKSPACE = Path(__file__).resolve().parent.parent
TOOLBOX = WORKSPACE.parent / "ToolBox"  # 假设 bin/ 在 workspace 根, ToolBox 平级
# Fallback: 如果 ToolBox 与 workspace 都在 ~/ 下
if not TOOLBOX.exists():
    TOOLBOX = Path.home() / "ToolBox"


def run(cmd: str, cwd: Path = None) -> str:
    """Run a shell command and return stdout."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=cwd or WORKSPACE, timeout=10
        )
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        return ""


def get_ssot_values() -> dict:
    """Collect all SSOT values from the workspace."""
    values = {}

    # 1. 工具数
    try:
        data = json.loads((WORKSPACE / "projects/kairon/packages/forge/tools-registry.json").read_text())
        values["tools_count"] = len(data.get("tools", []))
    except Exception:
        values["tools_count"] = None

    # 2. 项目数
    try:
        if HAS_YAML:
            data = yaml.safe_load((WORKSPACE / "docs/project-registry.yaml").read_text())
            values["projects_count"] = len(data.get("projects", {}))
    except Exception:
        values["projects_count"] = None

    # 3. M1 domain 节点数
    m1_domain = WORKSPACE / "projects/ecos/src/ecos/ssot/mof/m1/domain"
    if m1_domain.exists():
        values["m1_domain_count"] = len(list(m1_domain.glob("DOMAIN-*.yaml")))

    # 4. M1 bosroute 节点数
    m1_bosroute = WORKSPACE / "projects/ecos/src/ecos/ssot/mof/m1/bosroute"
    if m1_bosroute.exists():
        values["m1_bosroute_count"] = len(list(m1_bosroute.glob("BOSROUTE-*.yaml")))

    # 4b. M1 mechanism 节点数 (新发现)
    m1_mechanism = WORKSPACE / "projects/ecos/src/ecos/ssot/mof/m1/mechanism"
    if m1_mechanism.exists():
        values["m1_mechanism_count"] = len(list(m1_mechanism.glob("MECH-*.yaml")))

    # 4c. M1 全节点数 (所有 37 类型)
    m1_root = WORKSPACE / "projects/ecos/src/ecos/ssot/mof/m1"
    if m1_root.exists():
        values["m1_total_count"] = len(list(m1_root.glob("*/*.yaml")))

    # 5. 服务数 (agora bos-services)
    try:
        text = (WORKSPACE / "projects/agora/etc/bos-services.yaml").read_text()
        values["services_count"] = len(re.findall(r"^\s*-\s+uri:", text, re.MULTILINE))
    except Exception:
        values["services_count"] = None

    # 6. 路由数
    try:
        data = json.loads((Path.home() / ".ecos/bos/routes.json").read_text())
        values["routes_count"] = len(data.get("routes", {}))
    except Exception:
        values["routes_count"] = None

    # 7. 端口 (workspace SSOT, 只算 ports 段的有效端口)
    try:
        text = (WORKSPACE / "protocols" / "port-registry.yaml").read_text()
        in_ports = False
        ports = []
        for line in text.splitlines():
            if line.startswith("ports:"):
                in_ports = True
                continue
            if in_ports and line and not line[0].isspace():
                in_ports = False
            if in_ports and not line.strip().startswith("#"):
                m = re.match(r"^\s+(\d{4,5}):", line)
                if m:
                    ports.append(m.group(1))
        values["ports_count"] = len(set(ports))
    except Exception:
        values["ports_count"] = None

    # 8. PID
    out = run("launchctl list | grep com.ecos.bos-registry-daemon | awk '{print $1}'")
    values["launchd_pid"] = out if out else None

    # 9. 最近 commits (ecos + agora)
    for repo, name in [("projects/ecos", "ecos"), ("projects/agora", "agora")]:
        out = run("git log -1 --format='%H %s'", cwd=WORKSPACE / repo)
        values[f"{name}_last_commit"] = out

    return values


def check_stale_patterns() -> list[tuple[str, int, str, str]]:
    """Check for stale patterns in all ToolBox docs."""
    findings = []
    stale = [
        (r"eCOS\s*v5\b(?!\d)", "eCOS v5", "应改为 eCOS v6"),
        (r"\b5\+3\+1\b", "5+3+1", "应改为 5+4+1+1"),
        (r"\b5\+4\+1\b(?!\+)", "5+4+1", "应改为 5+4+1+1"),
        (r"\b7\s*层架构\b", "7 层架构", "应改为 5+4+1+1 架构"),
    ]
    for md in TOOLBOX.glob("*.md"):
        if not md.is_file():
            continue
        try:
            content = md.read_text()
        except Exception:
            continue
        for pattern, label, reason in stale:
            for i, line in enumerate(content.splitlines(), 1):
                if re.search(pattern, line):
                    if any(kw in line for kw in ["归档", "archived", "historical", "历史", "→", "->"]):
                        continue
                    findings.append((md.name, i, label, reason))
    return findings


def check_hardcoded_numbers(ssot: dict) -> list[tuple[str, int, str, str]]:
    """Check for hardcoded numbers that should be SSOT-referenced."""
    findings = []
    if not ssot:
        return findings

    # 数字 → SSOT 来源 + 提示
    rules = []
    if ssot.get("tools_count"):
        rules.append((rf"\b{ssot['tools_count']}\s*(?:工具|个工具)\b", f"{ssot['tools_count']} 工具", "应改为 '$(forge status | grep -c ...)' 或删除硬编码"))
    if ssot.get("projects_count"):
        rules.append((rf"\b{ssot['projects_count']}\s*项目\b", f"{ssot['projects_count']} 项目", "应改为引用 '$(python3 -c ...)' 或 'doc-ssot-.../project-layer-index.md'"))
    if ssot.get("m1_domain_count"):
        rules.append((rf"\b{ssot['m1_domain_count']}\s*节点\b", f"{ssot['m1_domain_count']} 节点", "应改为 '$(find .../DOMAIN-*.yaml | wc -l)' 引用"))
    if ssot.get("routes_count"):
        rules.append((rf"\b{ssot['routes_count']}\s*(?:routes)\b", f"{ssot['routes_count']} routes", "应引用 'cat ~/.ecos/bos/routes.json | jq length'"))

    for md in TOOLBOX.glob("*.md"):
        if not md.is_file():
            continue
        try:
            content = md.read_text()
        except Exception:
            continue
        for pattern, label, reason in rules:
            for i, line in enumerate(content.splitlines(), 1):
                if re.search(pattern, line):
                    # Skip if line is in SSOT-SNAPSHOT.md and is an example/illustration
                    if md.name == "SSOT-SNAPSHOT.md":
                        continue
                    # Skip if line contains backticks (already a command reference)
                    if "`" in line:
                        continue
                    # Skip if line is an example "X → Y" transition
                    if "→" in line or "->" in line:
                        continue
                    findings.append((md.name, i, label, reason))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--file", help="Single file to check")
    ap.add_argument("--no-fail", action="store_true", help="Don't fail on findings (advisory)")
    args = ap.parse_args()

    ssot = get_ssot_values()
    findings = []
    findings.extend(check_stale_patterns())
    findings.extend(check_hardcoded_numbers(ssot))

    if args.json:
        print(json.dumps({"ssot": ssot, "findings": findings}, indent=2, ensure_ascii=False))
    else:
        print("📊 ToolBox docs SSOT 校验")
        print()
        print("SSOT 真值 (运行时探测):")
        for k, v in ssot.items():
            label = k.replace("_", " ").title()
            print(f"   {label:25s} = {v}")
        print()
        if not findings:
            print("✅ 所有 ToolBox 文档符合 SSOT 契约")
            return 0
        print(f"❌ 发现 {len(findings)} 处 SSOT 违规:")
        for fname, line, label, reason in findings:
            print(f"   {fname}:{line}  [{label}]  {reason}")

    return 1 if findings and not args.no_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
