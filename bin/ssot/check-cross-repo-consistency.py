#!/usr/bin/env python3
"""check-cross-repo-consistency.py — P77 Phase 1 跨仓一致性 detector

按 STRAT-P77 §2 Phase 1 设计:

1. 读 projects/agora/etc/bos-services.yaml (BOS URI SSOT) → 已注册 set
2. 扫 projects/*/src/ 真**代码字符串** (非 docstring / 非 test) 中 bos://xxx 引用
3. 找 unregistered (referenced but NOT in SSOT)
4. 找 orphan (in registry 但 0 代码字面量引用; 仅非 active 的列为清理候选, active 的可执行性由 evidence-smoke 验)
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
引用口径 (2026-09-28): 只计「整个字符串字面量就是一个 URI」(可带 ?query), 注释 / docstring /
help 文案里的示例不算; agora 解析器 _LEGACY_BOS_URI_ALIASES 中目标已登记的旧名视为已覆盖。
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import tokenize
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


# 已知 docstring / 测试 fixture URIs (不视为"真"消费)
LEGACY_OK_URI_FRAGMENTS = {
    "bos://custom/path",  # c2g test fixture
    "bos://example/",  # docstring examples
    "bos://bad/foo/bar",  # omo BOS schema validation test (故意 invalid domain, P77-3 验收)
}


PENDING_REGISTRATIONS = WORKSPACE / ".omo" / "_truth" / "registry" / "bos-pending-registrations.yaml"


def load_pending_uris() -> set[str]:
    """已知待登记积压 (bos-pending-registrations.yaml): 单列计数, 不阻断; 门禁只拦新增未登记。"""
    data = load_yaml(PENDING_REGISTRATIONS)
    items = data.get("pending_registrations", []) if isinstance(data, dict) else []
    return {str(i["uri"]) for i in items if isinstance(i, dict) and i.get("uri")}


def load_yaml(p: Path) -> dict | list | None:
    import yaml

    if not p.exists():
        return None
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"⚠️ parse error: {p}: {exc}", file=sys.stderr)
        return None


# BOS URI regex — 严格 form: bos://domain/action[/action...] 后面不能跟 [a-z0-9_/-]
# 防止 bos://memory/kos 匹配 bos://memory/kos/search 的子串
# 允许可选 trailing / 表示 prefix pattern (e.g. "bos://memory/kos/" = "all under memory/kos")
BOS_URI_RE = re.compile(r"bos://[a-z][a-z0-9_-]+(?:/[a-z0-9_-]+){1,3}/?(?![a-z0-9_/-])")


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


def _literal_uris(text: str) -> set[str]:
    """源码中「整个字符串字面量就是一个 bos:// URI」的引用 (tokenize: 注释天然跳过)。

    此前对全文跑正则, 注释 / docstring / argparse help 里的示例 (bos://domain/package/action、
    "e.g. bos://mail/draft") 都被当成真实消费, 登记积压里 7 条是这类假阳性。
    """
    out: set[str] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type != tokenize.STRING:
                continue
            try:
                value = ast.literal_eval(tok.string)
            except (ValueError, SyntaxError):
                continue  # f-string 等非常量字面量
            if isinstance(value, str):
                candidate = value.strip().split("?", 1)[0]
                if BOS_URI_RE.fullmatch(candidate):
                    out.add(candidate)
    except (tokenize.TokenError, SyntaxError):
        pass
    return out


def load_agora_aliases() -> dict[str, str]:
    """agora 解析器的旧名 → 规范名别名表 (静态解析, 不 import agora)。"""
    api = WORKSPACE / "projects" / "agora" / "src" / "agora" / "mcp" / "resolver" / "api.py"
    if not api.exists():
        return {}
    for node in ast.walk(ast.parse(api.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_LEGACY_BOS_URI_ALIASES" for t in node.targets
        ):
            if isinstance(node.value, ast.Dict):
                return {
                    k.value: v.value
                    for k, v in zip(node.value.keys, node.value.values, strict=True)
                    if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)
                }
    return {}


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
            for uri in _literal_uris(text):
                # 跳过 fixture / example / 模板类
                if any(frag in uri for frag in LEGACY_OK_URI_FRAGMENTS):
                    continue
                # 真代码引用 (URI 出现即计)
                found.add(uri)
    return found


def load_ecos_ports() -> dict[int, object]:
    """ecos port-registry.

    Returns either a dict entry (structured) or a string (legacy flat format).
    """
    f = WORKSPACE / "projects" / "ecos" / "port-registry.yaml"
    data = load_yaml(f) or {}
    ports = data.get("ports", {}) if isinstance(data, dict) else {}
    out: dict[int, object] = {}
    for k, v in ports.items():
        if not str(k).isdigit():
            continue
        if isinstance(v, dict):
            out[int(k)] = v
        else:
            out[int(k)] = _strip_yaml_comment(str(v))
    return out


def load_protocols_ports() -> dict[int, object]:
    """protocols port-registry (SSOT 协议层).

    Returns either a dict entry (structured) or a string (legacy flat format).
    """
    f = WORKSPACE / "protocols" / "port-registry.yaml"
    data = load_yaml(f) or {}
    ports = data.get("ports", {}) if isinstance(data, dict) else {}
    out: dict[int, object] = {}
    for k, v in ports.items():
        if not str(k).isdigit():
            continue
        if isinstance(v, dict):
            out[int(k)] = v
        else:
            out[int(k)] = _strip_yaml_comment(str(v))
    return out


def _strip_yaml_comment(value: str) -> str:
    """YAML parser 不会 strip inline comment ('value # comment'), detector 必须手动处理."""
    if "  #" in value:  # 2 spaces before # = comment separator
        return value.split("  #", 1)[0].strip()
    if "\t#" in value:
        return value.split("\t#", 1)[0].strip()
    return value.strip()


def find_port_conflicts() -> list[dict]:
    """跨仓端口冲突扫描: 1) duplicate (两个 registry 都注册, 同号同名) 2) conflict (同号不同名)."""
    ecos = load_ecos_ports()
    proto = load_protocols_ports()
    conflicts = []
    all_ports = set(ecos.keys()) | set(proto.keys())
    for p in sorted(all_ports):
        e = ecos.get(p)
        pr = proto.get(p)
        if e and pr:
            e_name = _port_name(e)
            pr_name = _port_name(pr)
            e_transport = e.get("transport", "") if isinstance(e, dict) else ""
            pr_transport = pr.get("transport", "") if isinstance(pr, dict) else ""
            if e_name == pr_name and (not e_transport or e_transport == pr_transport):
                # P79: 实际是 duplicate (note/description 可不同) — 不算真冲突
                pass
            else:
                conflicts.append({"port": p, "type": "conflict", "ecos": e, "protocols": pr})
    return conflicts


def _port_name(entry) -> str:
    """P78 结构化后格式为 dict; 平面格式为 string. 提取 name 比较."""
    if isinstance(entry, dict):
        return entry.get("name", "")
    return _strip_yaml_comment(str(entry))


def is_covered_by_prefix(uri: str, registered: dict[str, dict]) -> bool:
    """检查 uri 是否被某个 prefix-pattern 覆盖 (e.g. 'bos://memory/kos/search' 被 'bos://memory/kos/' 覆盖)."""
    for reg_uri in registered:
        if reg_uri.endswith("/") and uri.startswith(reg_uri):
            return True
    return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument(
        "--threshold",
        type=int,
        default=0,
        help="unregistered URI 阈值 (默认 0, 治本后 strict-mode; 调大可放行)",
    )
    args = p.parse_args()

    registered = load_agora_registered_uris()
    referenced = collect_referenced_uris()
    aliases = load_agora_aliases()  # 旧名 → 规范名; 规范名已登记则旧名视为已覆盖
    # unregistered = 真缺注册
    # 1. 排除 prefix-pattern 形式 (URI 末尾以 / 结尾, 表示 routing 前缀, 不是真服务)
    #    e.g. "bos://analysis/code/" 用作 startswith() 前缀匹配, 不需具体服务
    # 2. 排除被某个注册 prefix pattern 覆盖的 (reverse direction)
    strict_unregistered = sorted(
        u
        for u in (referenced - set(registered.keys()))
        if not u.endswith("/") and not is_covered_by_prefix(u, registered) and aliases.get(u) not in registered
    )
    unregistered = strict_unregistered
    # 已登记在 bos-pending-registrations.yaml 的是已知积压 (baseline), 新增的才阻断
    pending = load_pending_uris()
    unregistered_pending = [u for u in unregistered if u in pending]
    unregistered_new = [u for u in unregistered if u not in pending]
    # 旧名被引用 → 其规范目标也算被引用
    referenced_canonical = referenced | {aliases[u] for u in referenced if u in aliases}
    # orphan = 未被代码字面量引用。BOS 以 agent 运行时发现 (list_services → 按 URI 调用) 为主要消费方式,
    # 未引用不是僵尸判据 —— active 服务的可执行性由 bin/gac/evidence-smoke.py 验证 (2026-09-28: 294/294 可解析)。
    # 这里只把非 active (deprecated / unimplemented) 且无引用的列为清理候选。
    orphan = sorted(set(registered.keys()) - referenced_canonical)
    cleanup_candidates = [u for u in orphan if str(registered[u].get("status") or "active") != "active"]

    ports = load_ecos_ports()
    protocols_ports = load_protocols_ports()
    port_conflicts = find_port_conflicts()
    # P79: 既然 find_port_conflicts 已按 name+transport 一致性区分, type=conflict 必为真冲突
    real_port_conflicts = [c for c in port_conflicts if c["type"] == "conflict"]
    # 端口总计数 = ecos unique + protocols unique (去重)
    all_unique_ports = set(ports.keys()) | set(protocols_ports.keys())
    port_count = len(all_unique_ports)

    summary = {
        "registered": len(registered),
        "referenced": len(referenced),
        "unregistered": len(unregistered),
        "orphan": len(orphan),
        "ports": port_count,
        "port_count_ecos": len(ports),
        "port_count_protocols": len(protocols_ports),
        "port_conflicts": len(real_port_conflicts),  # 只算真冲突 (同号不同名)
        "port_duplicates": len([c for c in port_conflicts if c["type"] == "duplicate"]),
        "port_conflicts_list": port_conflicts,
        "threshold": args.threshold,
        "unregistered_new": len(unregistered_new),
        "unregistered_pending": len(unregistered_pending),
        # ok = 新增未登记 ≤ threshold AND 真 port conflicts=0 (已知积压见 unregistered_pending)
        "ok": len(unregistered_new) <= args.threshold and len(real_port_conflicts) == 0,
        "unregistered_list": unregistered[:50],  # truncate for output
        "unregistered_new_list": unregistered_new[:50],
        "orphan_list": orphan[:50],
        "orphan_cleanup_candidates": cleanup_candidates,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("=== cross-repo-consistency (P77 Phase 4) ===")
        print(f"  registered (agora BOS SSOT): {summary['registered']}")
        print(f"  referenced (project code): {summary['referenced']}")
        print(f"  unregistered (referenced but not in SSOT): {summary['unregistered']}")
        print(
            f"  orphan (未被代码字面量引用; BOS 主要经运行时发现消费, 非僵尸判据, 可执行性见 evidence-smoke): "
            f"{summary['orphan']}"
        )
        print(
            f"  ports (union ecos+protocols): {summary['ports']} "
            f"(ecos={summary['port_count_ecos']}, protocols={summary['port_count_protocols']})"
        )
        if summary["port_conflicts"] > 0:
            print(f"  port conflicts (duplicate+conflict): {summary['port_conflicts']}")
            for c in summary["port_conflicts_list"][:5]:
                print(f"    port={c['port']} type={c['type']} ecos={c['ecos']!r} protocols={c['protocols']!r}")
        print()
        print(
            f"  └─ 其中已知待登记积压 (bos-pending-registrations.yaml): {summary['unregistered_pending']}, "
            f"新增: {summary['unregistered_new']}"
        )
        if summary["unregistered_new"] > args.threshold:
            print(f"❌ {summary['unregistered_new']} 个新增 unregistered URI 超过 threshold ({args.threshold}):")
            for u in summary["unregistered_new_list"]:
                print(f"    {u}  → 登记到 projects/agora/etc/bos-services.yaml 或 bos-pending-registrations.yaml")
        else:
            print(f"✅ 新增 unregistered URIs {summary['unregistered_new']} ≤ threshold {args.threshold}")
        if summary["port_conflicts"] > 0:
            real_conflicts = [c for c in summary["port_conflicts_list"] if c["type"] == "conflict"]
            if real_conflicts:
                print()
                print(f"❌ {len(real_conflicts)} port conflicts (同号不同名, 修真修真):")
                for c in real_conflicts[:5]:
                    print(f"  - port={c['port']}: ecos='{c['ecos']}' vs protocols='{c['protocols']}'")
        if cleanup_candidates:
            print()
            print("⚠️ 清理候选 (非 active 且无代码引用, 确认零消费者后可删):")
            for u in cleanup_candidates[:20]:
                print(f"  - {u} [{registered[u].get('status')}]")

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
