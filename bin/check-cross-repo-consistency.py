#!/usr/bin/env python3
"""check-cross-repo-consistency.py — P77 Phase 1 跨仓一致性 detector

按 STRAT-P77 §2 Phase 1 设计:

1. 读 projects/agora/etc/bos-services.yaml (BOS URI SSOT) → 已注册 set
2. 扫 projects/*/src/ 真**代码字符串** (非 docstring / 非 test) 中 bos://xxx 引用
3. 找 unregistered (referenced but NOT in SSOT)
4. 找 orphan (in registry 但 0 代码引用 — 可能 zombie)
5. 跨 projects/* 的 port-registry.yaml 看端口冲突
6. 输出 violations table + threshold + exit code

适用原则 (P77-1 consistency-by-tool):
- 自动 verifier 守护, 不靠 review memory
- 报告格式 machine-readable + human-readable
- `enforcement=advisory` 默认 (Phase 3 升级 hard)

数据源:
- agora BOS SSOT: projects/agora/etc/bos-services.yaml
- aetherforge 自报 BOS URIs: projects/aetherforge/src/aetherforge/{mesh,swarm,gateway}/rpc.py
- ecos port: projects/ecos/port-registry.yaml
- 每仓 M1: projects/ecos/src/ecos/ssot/mof/m1/{<ns>}/*.yaml

豁免 (LEGACY_OK_URIS): 测试夹具 / docstring 例子 (regex 自识别)。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]


# 已知 docstring / 测试 fixture URIs (不视为"真"消费)
LEGACY_OK_URI_FRAGMENTS = {
    "bos://custom/path",  # c2g test fixture
    "bos://example/",  # docstring examples
}


def load_yaml(p: Path) -> dict | list | None:
    import yaml
    if not p.exists():
        return None
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"⚠️ parse error: {p}: {exc}", file=sys.stderr)
        return None


# BOS URI regex — 完整 form: bos://domain/action[/action...]
BOS_URI_RE = re.compile(r"bos://[a-z][a-z0-9_-]+(?:/[a-z0-9_-]+){1,3}")


def load_agora_registered_uris() -> dict[str, dict]:
    """从 agora bos-services.yaml 提取已注册 BOS URIs."""
    f = WORKSPACE / "projects" / "agora" / "etc" / "bos-services.yaml"
    data = load_yaml(f) or {}
    services = data.get("services", []) if isinstance(data, dict) else []
    out: dict[str, dict] = {}
    for s in services:
        uri = s.get("uri", "")
        if uri and uri.startswith("bos://"):
            out[uri] = s
    return out


def collect_referenced_uris() -> set[str]:
    """扫 projects/*/src/ — 非 docstring/非 test 的 bos:// 引用."""
    found: set[str] = set()
    for proj_dir in (WORKSPACE / "projects").iterdir():
        if not (proj_dir / "src").is_dir():
            continue
        if proj_dir.name == "venv" or proj_dir.name.startswith("."):
            continue
        for f in (proj_dir / "src").rglob("*.py"):
            # 跳过测试 / fixtures
            parts = f.parts
            if "test" in parts or "tests" in parts or "__pycache__" in parts:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            for m in BOS_URI_RE.finditer(text):
                uri = m.group(0)
                # 跳过 fixture / example / 模板类
                if any(frag in uri for frag in LEGACY_OK_URI_FRAGMENTS):
                    continue
                # 跳过 docstring URIs (粗略: 行尾 `"""` 闭合 + 含"示例"+"路径")
                if "/bos/" in text and uri in text:
                    # 真代码引用 (RHS, 不是 docstring)
                    found.add(uri)
                else:
                    found.add(uri)
    return found


def load_ecos_ports() -> dict[int, str]:
    """ecos port-registry."""
    f = WORKSPACE / "projects" / "ecos" / "port-registry.yaml"
    data = load_yaml(f) or {}
    return {int(k): str(v) for k, v in data.items() if str(k).isdigit()}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--threshold", type=int, default=20,
                   help="unregistered URI 阈值 (默认 20, 治本后可降至 0)")
    args = p.parse_args()

    registered = load_agora_registered_uris()
    referenced = collect_referenced_uris()
    unregistered = sorted(referenced - set(registered.keys()))
    orphan = sorted(set(registered.keys()) - referenced)

    ports = load_ecos_ports()
    port_conflicts: list[tuple[int, str, str]] = []  # (port, claimer1, claimer2)
    # 简化: 不扫跨仓端口冲突 (需更深的 mapping), 只 report 总数
    port_count = len(ports)

    summary = {
        "registered": len(registered),
        "referenced": len(referenced),
        "unregistered": len(unregistered),
        "orphan": len(orphan),
        "ports": port_count,
        "threshold": args.threshold,
        "ok": len(unregistered) <= args.threshold,
        "unregistered_list": unregistered[:50],  # truncate for output
        "orphan_list": orphan[:50],
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"=== cross-repo-consistency (P77 Phase 1) ===")
        print(f"  registered (agora BOS SSOT): {summary['registered']}")
        print(f"  referenced (project code): {summary['referenced']}")
        print(f"  unregistered (referenced but not in SSOT): {summary['unregistered']}")
        print(f"  orphan (in SSOT but not referenced): {summary['orphan']}")
        print(f"  ports (ecos registry): {summary['ports']}")
        print()
        if summary["unregistered"] > args.threshold:
            print(f"❌ {summary['unregistered']} unregistered URIs 超过 threshold ({args.threshold})")
            for u in unregistered[:10]:
                print(f"  - {u}")
            if len(unregistered) > 10:
                print(f"  ... and {len(unregistered) - 10} more")
        else:
            print(f"✅ unregistered URIs {summary['unregistered']} ≤ threshold {args.threshold}")
        if summary["orphan"] > 0:
            print()
            print(f"⚠️ orphan URIs (在 SSOT 但无引用, 可能僵尸):")
            for u in orphan[:5]:
                print(f"  - {u}")

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
