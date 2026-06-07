#!/usr/bin/env python3
"""
织星 MOF — 工作流 CLI 工具 (mof-workflow) | v2.0
===================================================
企业级统一工作流管理: 列出/查看/校验/执行/关系/统计

用法:
    mof workflow list   [--domain <d>] [--layer <l>] [--status <s>] [--json]
    mof workflow show   <name> [--json]
    mof workflow validate [name] [--ci] [--json]
    mof workflow run    <name> [--dry-run]
    mof workflow relations [name]
    mof workflow stats  [--json]

Examples:
    mof workflow list --domain analysis
    mof workflow show minerva-deep-research --json | jq .
    mof workflow validate --ci
    mof workflow stats --json
"""

import sys
import os
import json
import yaml
from pathlib import Path
from collections import Counter

# ── 路径 ──
HOME = Path.home()
SSOT_DIR = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot"
M1_WF_DIR = SSOT_DIR / "mof" / "m1" / "workflow"
REGISTRY_FILE = SSOT_DIR / "registry" / "workflow-catalog.yaml"

# 引入统一输出
TOOLS_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOLS_DIR))
from _output import OutputFormatter, print_error


def _load_nodes():
    nodes = []
    if M1_WF_DIR.exists():
        for f in sorted(M1_WF_DIR.glob("WORKFLOW-*.yaml")):
            try:
                n = yaml.safe_load(open(f))
                if n and n.get("type") == "Workflow":
                    nodes.append(n)
            except Exception:
                pass
    return nodes


def _find(name_or_id):
    name_lower = name_or_id.lower()
    for n in _load_nodes():
        nid = n.get("id", "").lower()
        kebab = nid.replace("workflow-", "").replace("_", "-")
        nname = n.get("name", "").lower()
        if (name_lower == nid or name_lower == kebab or
            name_lower == nname or name_lower in nid):
            return n
    return None


def _load_catalog():
    if REGISTRY_FILE.exists():
        try:
            return yaml.safe_load(open(REGISTRY_FILE))
        except Exception:
            pass
    return {}


# ═══════════════════════════════════════════════════════════════
# 命令实现
# ═══════════════════════════════════════════════════════════════

def cmd_list(args):
    out = OutputFormatter(json_mode=args.json)
    nodes = _load_nodes()
    catalog = _load_catalog()

    filtered = []
    for n in nodes:
        if args.domain and n.get("domain") != args.domain:
            continue
        if args.layer and n.get("layer") != args.layer:
            continue
        if args.status and n.get("status") != args.status:
            continue
        filtered.append(n)

    if args.json:
        result = [{
            "id": n.get("id"), "name": n.get("name"),
            "subtype": n.get("subtype"), "domain": n.get("domain"),
            "layer": n.get("layer"), "bos_uri": n.get("bos_uri"),
            "description": n.get("description", ""),
            "steps_count": len(n.get("steps", [])),
            "status": n.get("status"),
        } for n in filtered]
        out.print_json({"workflows": result, "total": len(result)})
        return 0

    # 按域分组表格输出
    domain_order = ["memory", "omo", "analysis", "persona", "forge", "meta", "infra"]
    by_domain = {}
    for n in filtered:
        d = n.get("domain", "unknown")
        by_domain.setdefault(d, []).append(n)

    subtype_icons = {
        "PipelineWorkflow": "🔗", "AgentWorkflow": "🤖",
        "ScheduledWorkflow": "⏰", "MCPWorkflow": "🔌",
    }
    out.print_header(f"工作流清单 ({len(filtered)}/{len(nodes)})")

    for d in domain_order:
        if d not in by_domain:
            continue
        wfs = by_domain[d]
        domain_desc = catalog.get("domains", {}).get(d, {}).get("description", "")
        out.print_section(f"域: {d} — {domain_desc}")
        rows = []
        for w in sorted(wfs, key=lambda x: x.get("layer", "")):
            icon = subtype_icons.get(w.get("subtype", ""), "📋")
            rows.append([
                icon,
                w.get("layer", "?"),
                w.get("name", w.get("id", "?")),
                w.get("subtype", "?"),
                w.get("id", "?"),
            ])
        out.print_table(
            ["", "层", "名称", "类型", "ID"],
            rows,
        )

    # 统计
    layer_counter = Counter(n.get("layer", "?") for n in filtered)
    subtype_counter = Counter(n.get("subtype", "?") for n in filtered)
    out.print_section("统计摘要")
    out.print_key_value({
        "按层": str(dict(layer_counter)),
        "按类型": str(dict(subtype_counter)),
        "总步骤": str(sum(len(n.get("steps", [])) for n in filtered)),
    })
    return 0


def cmd_show(args):
    out = OutputFormatter(json_mode=args.json)
    node = _find(args.name)
    if not node:
        print_error(f"工作流未找到: {args.name}", "使用 'mof workflow list' 查看所有工作流")
        return 1

    if args.json:
        out.print_json(node)
        return 0

    out.print_header(node.get("name", node.get("id")))

    # 基本信息
    out.print_key_value({
        "ID": node.get("id", "?"),
        "类型": node.get("subtype", "?"),
        "域": node.get("domain", "?") or "",
        "层": node.get("layer", "?") or "",
        "BOS URI": node.get("bos_uri", "?"),
        "状态": node.get("status", "?"),
        "版本": node.get("version", "?"),
        "维护方": node.get("maintained_by", "?"),
    }, "基本信息")

    out.print_info(f"描述: {node.get('description', '')}")

    # 跨层映射
    cl = node.get("cross_layer", {})
    if cl:
        out.print_section("跨层映射")
        if cl.get("realized_by"):
            for r in cl["realized_by"]:
                print(f"  实现方: \033[36m{r.get('project', '?')}/{r.get('package', r.get('package', ''))}\033[0m → {r.get('entrypoint', '?')}")
        if cl.get("invoked_by"):
            for i in cl["invoked_by"]:
                print(f"  调用方: [{i.get('layer', '?')}] {i.get('component', '?')} ({i.get('mechanism', '?')})")

    # 步骤
    steps = node.get("steps", [])
    if steps:
        out.print_section(f"步骤 ({len(steps)})")
        rows = []
        for s in steps:
            order = str(s.get("order", "?"))
            name = s.get("name", "?")
            action = s.get("action", "?")
            dep = ", ".join(s.get("depends_on", [])) if s.get("depends_on") else "—"
            parallel = "∥" if s.get("parallel") else ""
            desc = s.get("description", "")
            rows.append([order, f"{name} {parallel}", action, dep, desc])
        out.print_table(["#", "步骤", "动作", "依赖", "说明"], rows)

    # 执行配置
    ex = node.get("execution", {})
    if ex:
        out.print_section("执行配置")
        out.print_key_value({
            "模式": ex.get("mode", "?"),
            "最大重试": str(ex.get("max_retries", "?")),
            "超时": f"{ex.get('timeout', '?')}s",
            "失败策略": ex.get("on_failure", "?"),
            "L0审计": "是" if ex.get("audit_enabled") else "否",
        })

    # SLA
    sla = node.get("sla", {})
    if sla:
        out.print_section("SLA")
        out.print_key_value({
            "最大执行时间": f"{sla.get('max_execution_time', '?')}s",
            "期望完成率": f"{sla.get('expected_completion_rate', 0.95)}",
            "关键路径": "是" if sla.get("critical") else "否",
        })

    # 关系
    rels = node.get("relations", [])
    if rels:
        out.print_section(f"关系 ({len(rels)})")
        for r in rels:
            print(f"  {r.get('type', '?')}: {r.get('from', '?')} → {r.get('to', '?')}")
            if r.get("note"):
                print(f"    \033[2m{r.get('note')}\033[0m")

    # 标签
    tags = node.get("tags", [])
    if tags:
        print(f"\n\033[1m标签\033[0m: {', '.join(tags)}")

    out.print_divider()
    return 0


def cmd_validate(args):
    out = OutputFormatter(json_mode=args.json)
    name = args.name

    if name:
        node = _find(name)
        if not node:
            print_error(f"工作流未找到: {name}")
            return 1
        nodes = [node]
    else:
        nodes = _load_nodes()

    errors = []
    warnings = []

    for n in nodes:
        nid = n.get("id", "?")

        for field in ["id", "type", "subtype", "name", "description", "domain", "layer", "bos_uri"]:
            if not n.get(field):
                errors.append(f"{nid}: 缺少必填字段 {field}")

        valid_subtypes = ["PipelineWorkflow", "AgentWorkflow", "ScheduledWorkflow", "MCPWorkflow"]
        if n.get("subtype") not in valid_subtypes:
            errors.append(f"{nid}: 无效的 subtype '{n.get('subtype')}'")

        valid_domains = ["memory", "omo", "analysis", "persona", "forge", "meta", "infra"]
        if n.get("domain") not in valid_domains:
            errors.append(f"{nid}: 无效的 domain '{n.get('domain')}'")

        if not n.get("steps", []):
            warnings.append(f"{nid}: 无步骤定义")

        if not n.get("cross_layer", {}).get("realized_by"):
            warnings.append(f"{nid}: 未声明 cross_layer.realized_by")

        bos = n.get("bos_uri", "")
        if bos and not bos.startswith("bos://ecos/workflow/"):
            warnings.append(f"{nid}: BOS URI 格式非标准")

    if args.json:
        out.print_json({
            "total": len(nodes), "passed": len(nodes) - len(errors),
            "errors": errors, "warnings": warnings,
        })
        return 1 if errors else 0

    if not args.ci:
        out.print_header(f"工作流校验 ({len(nodes)} 个)")

    for w in warnings:
        out.print_warning(w)
    for e in errors:
        out.print_error(e)

    if errors:
        out.print_error(f"{len(errors)} 个错误, {len(warnings)} 个警告")
        return 1
    else:
        if not args.ci:
            out.print_success(f"全部 {len(nodes)} 个通过" + (f" ({len(warnings)} 个警告)" if warnings else ""))
        return 0


def cmd_run(args):
    out = OutputFormatter()
    node = _find(args.name)
    if not node:
        print_error(f"工作流未找到: {args.name}")
        return 1

    bos_uri = node.get("bos_uri", "")
    out.print_header(f"执行: {node.get('name')}")
    out.print_key_value({
        "BOS URI": bos_uri,
        "实现方": node.get("cross_layer", {}).get("realized_by", [{}])[0].get("project", "?"),
        "步骤数": str(len(node.get("steps", []))),
    }, "基本信息")

    if args.dry_run:
        out.print_progress("干运行模式 — 仅验证步骤")
        for s in node.get("steps", []):
            dep_ok = True
            if s.get("depends_on"):
                dep_ok = all(d in [st.get("name") for st in node.get("steps", [])] for d in s["depends_on"])
            icon = "\033[32m✓\033[0m" if dep_ok else "\033[33m!\033[0m"
            print(f"  {icon} {s.get('order')}. {s.get('name')} → {s.get('action')}")
        out.print_success(f"干运行完成 ({len(node.get('steps', []))} 步骤)")
        return 0

    # 尝试通过 BOS URI 实际执行
    import subprocess, json
    if bos_uri:
        out.print_progress(f"通过 BOS URI 路由执行: {bos_uri}")
        try:
            result = subprocess.run(
                ["python3", "-c", f"""
import sys; sys.path.insert(0, '{HOME}/Workspace/projects/agora/src')
from agora.mcp.bos_resolver import resolve_bos_uri, parse_bos_uri
import asyncio
info = parse_bos_uri('{bos_uri.replace("ecos/workflow/", "")}')
action = info.get('action', 'main')
try:
    result = asyncio.run(resolve_bos_uri('{bos_uri.replace("ecos/workflow/", "")}'))
    print(json.dumps(result))
except Exception as e:
    print(json.dumps({{'status': 'error', 'error': str(e)}}))
"""],
                capture_output=True, text=True, timeout=10,
            )
            out.print_success("执行完成")
            print(f"\n\033[2m{result.stdout[:500]}\033[0m")
            return 0
        except subprocess.TimeoutExpired:
            out.print_warning("执行超时 (10s)")
        except Exception as e:
            out.print_error(f"执行失败: {e}")
    else:
        out.print_warning("该工作流无 BOS URI，需通过 Agora Service Mesh 路由")
        out.print_info("提示: 使用 'agora pipeline <name> --goal \"...\"' 通过 Agora 执行")

    return 0


def cmd_relations(args):
    out = OutputFormatter(json_mode=args.json)
    catalog = _load_catalog()
    global_rels = catalog.get("global_relations", {})

    if args.name:
        node = _find(args.name)
        if not node:
            print_error(f"工作流未找到: {args.name}")
            return 1
        nid = node.get("id")

        upstream = [t for t in global_rels.get("triggers", []) if t.get("to") == nid]
        downstream = [t for t in global_rels.get("triggers", []) if t.get("from") == nid]
        deps = [d for d in global_rels.get("dependencies", []) if d.get("dependent") == nid]
        flows_in = []
        flows_out = []

        if args.json:
            out.print_json({
                "workflow": nid,
                "upstream_triggers": upstream,
                "downstream_triggers": downstream,
                "dependencies": deps,
            })
            return 0

        out.print_header(f"关系图: {node.get('name')}")

        if upstream:
            out.print_section("上游触发")
            for u in upstream:
                print(f"  ← \033[36m{u.get('from')}\033[0m \033[2m({u.get('note', '')})\033[0m")
        else:
            out.print_info("上游触发: (无)")

        if downstream:
            out.print_section("下游触发")
            for d in downstream:
                print(f"  → \033[36m{d.get('to')}\033[0m \033[2m({d.get('note', '')})\033[0m")
        else:
            out.print_info("下游触发: (无)")

        if deps:
            out.print_section("依赖")
            for d in deps:
                print(f"  \033[36m{nid}\033[0m 需要 \033[36m{d.get('depends_on')}\033[0m \033[2m({d.get('note', '')})\033[0m")

        out.print_divider()
        return 0

    # 全局关系
    if args.json:
        out.print_json(global_rels)
        return 0

    out.print_header("全局工作流关系图")

    triggers = global_rels.get("triggers", [])
    if triggers:
        out.print_section("触发链")
        rows = [[t.get("from", "?"), "→", t.get("to", "?"), t.get("note", "")] for t in triggers]
        out.print_table(["源", "", "目标", "说明"], rows)

    data_flows = global_rels.get("data_flows", [])
    if data_flows:
        out.print_section("数据流")
        for f in data_flows:
            print(f"  \033[36m{f.get('from')}\033[0m → \033[36m{f.get('to')}\033[0m")
            print(f"    \033[2m{f.get('note', '')}\033[0m")

    deps = global_rels.get("dependencies", [])
    if deps:
        out.print_section("依赖关系")
        for d in deps:
            print(f"  \033[36m{d.get('dependent')}\033[0m 依赖 \033[36m{d.get('depends_on')}\033[0m")
            if d.get("note"):
                print(f"    \033[2m{d.get('note')}\033[0m")

    out.print_divider()
    return 0


def cmd_stats(args):
    out = OutputFormatter(json_mode=args.json)
    nodes = _load_nodes()

    layer_counter = Counter(n.get("layer", "?") for n in nodes)
    domain_counter = Counter(n.get("domain", "?") for n in nodes)
    subtype_counter = Counter(n.get("subtype", "?") for n in nodes)

    total_steps = sum(len(n.get("steps", [])) for n in nodes)
    avg_steps = total_steps / len(nodes) if nodes else 0

    critical = [n.get("name") for n in nodes if n.get("sla", {}).get("critical")]

    if args.json:
        out.print_json({
            "total": len(nodes),
            "total_steps": total_steps,
            "avg_steps": round(avg_steps, 1),
            "by_layer": dict(sorted(layer_counter.items())),
            "by_domain": dict(sorted(domain_counter.items())),
            "by_subtype": dict(subtype_counter),
            "critical_paths": critical,
        })
        return 0

    out.print_header("工作流统计")
    out.print_key_value({
        "总数": str(len(nodes)),
        "总步骤": str(total_steps),
        "平均步骤": f"{avg_steps:.1f}",
    }, "核心指标")

    out.print_section("分布")
    out.print_key_value({
        "按层": str(dict(sorted(layer_counter.items()))),
        "按域": str(dict(sorted(domain_counter.items()))),
        "按类型": str(dict(subtype_counter)),
    })

    if critical:
        out.print_section("关键路径")
        for c in critical:
            print(f"  \033[31m●\033[0m {c}")

    catalog_stats = _load_catalog().get("stats", {})
    if catalog_stats.get("total", 0) != len(nodes):
        out.print_warning(f"注册表不一致: catalog={catalog_stats.get('total', 0)}, M1节点={len(nodes)}")

    out.print_divider()
    return 0


def cmd_graph(args):
    """工作流依赖图 — 支持 dot/mermaid/ascii 格式输出"""
    out = OutputFormatter(json_mode=args.json)
    catalog = _load_catalog()
    global_rels = catalog.get("global_relations", {})

    if args.json:
        out.print_json(global_rels)
        return 0

    fmt = args.format

    if fmt == "dot":
        lines = ["digraph BOS_Workflows {", '  rankdir=TB;', '  node [shape=box, style=filled, fillcolor=lightyellow];']
        nodes = set()
        edges = []
        for t in global_rels.get("triggers", []):
            src = t["from"].replace("-", "_").replace(":", "_")
            dst = t["to"].replace("-", "_").replace(":", "_")
            nodes.add(src); nodes.add(dst)
            edges.append(f'  "{src}" -> "{dst}" [label="triggers", fontsize=9];')
        for n in sorted(nodes):
            lines.append(f'  "{n}";')
        lines.extend(edges)
        lines.append("}")
        print("\n".join(lines))
        print("\n# Render: dot -Tpng graph.dot -o graph.png")

    elif fmt == "mermaid":
        lines = ["graph TD"]
        for t in global_rels.get("triggers", []):
            src = t["from"].replace("-", "_").replace("WORKFLOW_", "").replace("MECH_", "")
            dst = t["to"].replace("-", "_").replace("WORKFLOW_", "").replace("MECH_", "")
            lines.append(f"  {src} -->|triggers| {dst}")
        for d in global_rels.get("dependencies", []):
            dep = d["dependent"].replace("-", "_").replace("WORKFLOW_", "")
            ond = d["depends_on"].replace("-", "_").replace("WORKFLOW_", "")
            lines.append(f"  {dep} -.->|depends| {ond}")
        print("\n".join(lines))
        print("\n# Render: https://mermaid.live")

    else:  # ascii
        out.print_header("工作流依赖图 (ASCII)")
        triggers = global_rels.get("triggers", [])
        for t in triggers:
            src = t["from"].replace("WORKFLOW-", "").replace("MECH-", "")[:30]
            dst = t["to"].replace("WORKFLOW-", "").replace("MECH-", "")[:30]
            print(f"  \033[36m{src}\033[0m")
            print(f"    │ triggers")
            print(f"    ▼")
            print(f"  \033[36m{dst}\033[0m")
            if t.get("note"):
                print(f"    \033[2m{t['note'][:60]}\033[0m")
        deps = global_rels.get("dependencies", [])
        if deps:
            out.print_section("依赖关系")
            for d in deps:
                dep = d["dependent"].replace("WORKFLOW-", "")[:30]
                ond = d["depends_on"].replace("WORKFLOW-", "")[:30]
                print(f"  \033[36m{dep}\033[0m 需要 \033[36m{ond}\033[0m")

    return 0


def cmd_check_refs(args):
    """交叉引用校验 — 验证 workflow-catalog.yaml 中所有引用有效性"""
    out = OutputFormatter(json_mode=args.json)
    catalog = _load_catalog()
    nodes = _load_nodes()
    node_ids = {n.get("id", "") for n in nodes}
    global_rels = catalog.get("global_relations", {})

    errors = []
    warnings = []

    for t in global_rels.get("triggers", []):
        for field in ["from", "to"]:
            ref = t.get(field, "")
            if ref.startswith("WORKFLOW-") and ref not in node_ids:
                errors.append(f"Trigger {field}: '{ref}' 无对应 M1 节点")

    for d in global_rels.get("dependencies", []):
        for field in ["dependent", "depends_on"]:
            ref = d.get(field, "")
            if ref.startswith("WORKFLOW-") and ref not in node_ids:
                errors.append(f"Dependency {field}: '{ref}' 无对应 M1 节点")

    if args.json:
        out.print_json({"errors": errors, "warnings": warnings, "total_nodes": len(nodes)})
        return 1 if errors else 0

    out.print_header(f"交叉引用校验 ({len(nodes)} 节点)")

    if errors:
        for e in errors:
            out.print_error(e)
    if warnings:
        for w in warnings:
            out.print_warning(w)

    if not errors and not warnings:
        out.print_success("全部校验通过 — 所有引用指向存在的 M1 节点")
        return 0
    else:
        out.print_error(f"{len(errors)} 个错误, {len(warnings)} 个警告")
        return 1 if errors else 0


# ═══════════════════════════════════════════════════════════════
# Argparse 入口
# ═══════════════════════════════════════════════════════════════

def build_parser():
    import argparse

    p = argparse.ArgumentParser(
        prog="mof-workflow",
        description="织星 MOF — 全局工作流统一管理",
        epilog="""Examples:
  mof workflow list --domain analysis
  mof workflow show minerva-deep-research
  mof workflow show minerva-deep-research --json | jq .
  mof workflow validate --ci
  mof workflow stats --json
  mof workflow relations minerva-deep-research
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = p.add_subparsers(dest="subcommand", help="子命令")

    # list
    l = sub.add_parser("list", help="列出所有工作流")
    l.add_argument("--domain", choices=["memory", "omo", "analysis", "persona", "forge", "meta", "infra"],
                   help="按 BOS 域过滤")
    l.add_argument("--layer", choices=["L0", "L1", "L2", "I0", "L3", "L4"], help="按架构层过滤")
    l.add_argument("--status", choices=["defined", "active", "deprecated", "archived"], help="按状态过滤")
    l.add_argument("--json", action="store_true", help="JSON 输出")

    # show
    s = sub.add_parser("show", help="查看工作流详情")
    s.add_argument("name", help="工作流名称或 WORKFLOW-ID")
    s.add_argument("--json", action="store_true", help="JSON 输出")

    # validate
    v = sub.add_parser("validate", help="校验工作流")
    v.add_argument("name", nargs="?", help="工作流名称（可选，不传则全量校验）")
    v.add_argument("--ci", action="store_true", help="CI 模式 (exit code)")
    v.add_argument("--json", action="store_true", help="JSON 输出")

    # run
    r = sub.add_parser("run", help="执行工作流")
    r.add_argument("name", help="工作流名称")
    r.add_argument("--dry-run", action="store_true", help="干运行（仅校验不执行）")
    r.add_argument("--params", help="执行参数 JSON")

    # relations
    rel = sub.add_parser("relations", help="工作流关系图")
    rel.add_argument("name", nargs="?", help="工作流名称（可选，不传返回全局）")
    rel.add_argument("--json", action="store_true", help="JSON 输出")

    # stats
    st = sub.add_parser("stats", help="统计摘要")
    st.add_argument("--json", action="store_true", help="JSON 输出")

    # graph
    g = sub.add_parser("graph", help="工作流依赖图")
    g.add_argument("--format", choices=["dot", "mermaid", "ascii"], default="ascii", help="输出格式")
    g.add_argument("--json", action="store_true", help="JSON 输出")

    # check-refs
    cr = sub.add_parser("check-refs", help="交叉引用校验")
    cr.add_argument("--json", action="store_true", help="JSON 输出")

    return p


def main():
    parser = build_parser()

    # 保持向后兼容: 支持不被 argparse 识别的 args 作为 name 传入
    try:
        args = parser.parse_args()
    except SystemExit:
        return 1

    if not args.subcommand:
        parser.print_help()
        return 0

    # 路由
    commands = {
        "list": cmd_list,
        "show": cmd_show,
        "validate": cmd_validate,
        "run": cmd_run,
        "relations": cmd_relations,
        "stats": cmd_stats,
        "graph": cmd_graph,
        "check-refs": cmd_check_refs,
    }

    handler = commands.get(args.subcommand)
    if handler:
        try:
            return handler(args)
        except Exception as e:
            print_error(f"执行失败: {e}", "使用 --help 获取帮助")
            return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
