#!/usr/bin/env python3
"""
织星 MOF — 工作流 CLI 工具 (mof-workflow)
==========================================
统一工作流管理: 列出/查看/校验/执行/关系/统计

用法:
    mof workflow list [--domain <domain>] [--layer <layer>] [--status <status>]
    mof workflow show <name>
    mof workflow validate [name] [--ci]
    mof workflow run <name> [--dry-run] [--params <json>]
    mof workflow relations [name] [--all]
    mof workflow stats
"""

import sys
import os
import json
import yaml
from pathlib import Path
from datetime import datetime, timezone

# 路径常量
HOME = Path.home()
SSOT_DIR = HOME / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot"
M1_WORKFLOW_DIR = SSOT_DIR / "mof" / "m1" / "workflow"
REGISTRY_FILE = SSOT_DIR / "registry" / "workflow-catalog.yaml"
M2_WORKFLOW_FILE = SSOT_DIR / "mof" / "m2" / "workflow.yaml"


def _load_all_m1_nodes():
    """加载所有 M1 Workflow 节点"""
    nodes = []
    if M1_WORKFLOW_DIR.exists():
        for f in sorted(M1_WORKFLOW_DIR.glob("WORKFLOW-*.yaml")):
            try:
                node = yaml.safe_load(open(f))
                if node and node.get("type") == "Workflow":
                    nodes.append(node)
            except Exception:
                pass
    return nodes


def _load_catalog():
    """加载工作流注册表"""
    if REGISTRY_FILE.exists():
        try:
            return yaml.safe_load(open(REGISTRY_FILE))
        except Exception:
            pass
    return {}


def _find_workflow(name_or_id):
    """根据名称或 ID 查找工作流"""
    nodes = _load_all_m1_nodes()
    name_lower = name_or_id.lower()
    for n in nodes:
        nid = n.get("id", "").lower()
        nname = n.get("name", "").lower()
        # 支持 kebab-case 名称匹配
        kebab = nid.replace("workflow-", "").replace("_", "-")
        if (name_lower == nid or
            name_lower == nname or
            name_lower in nid or
            name_lower in kebab):
            return n
    return None


def cmd_list(domain=None, layer=None, status=None):
    """列出工作流"""
    nodes = _load_all_m1_nodes()
    catalog = _load_catalog()

    # 过滤
    filtered = []
    for n in nodes:
        if domain and n.get("domain") != domain:
            continue
        if layer and n.get("layer") != layer:
            continue
        if status and n.get("status") != status:
            continue
        filtered.append(n)

    # 按域分组显示
    domain_order = ["memory", "omo", "analysis", "persona", "forge", "meta", "infra"]
    by_domain = {}
    for n in filtered:
        d = n.get("domain", "unknown")
        by_domain.setdefault(d, []).append(n)

    print(f"═══ 工作流清单 ({len(filtered)}/{len(nodes)}) ═══\n")
    for d in domain_order:
        if d not in by_domain:
            continue
        wfs = by_domain[d]
        domain_name = catalog.get("domains", {}).get(d, {}).get("description", d)
        print(f"域: {d} — {domain_name}")
        for w in sorted(wfs, key=lambda x: x.get("layer", "")):
            icon = {
                "PipelineWorkflow": "🔗",
                "AgentWorkflow": "🤖",
                "ScheduledWorkflow": "⏰",
                "MCPWorkflow": "🔌",
            }.get(w.get("subtype", ""), "📋")
            print(f"  {icon} [{w.get('layer', '?')}] {w.get('name', w.get('id', '?'))}")
            print(f"     ID: {w.get('id', '?')} | {w.get('subtype', '?')} | bos://ecos/workflow/{w.get('id', '').replace('WORKFLOW-', '').lower()}")
        print()

    # 统计摘要
    from collections import Counter
    layer_counter = Counter(n.get("layer", "?") for n in filtered)
    subtype_counter = Counter(n.get("subtype", "?") for n in filtered)
    print("统计:")
    print(f"  按层:  {dict(layer_counter)}")
    print(f"  按类型: {dict(subtype_counter)}")


def cmd_show(name):
    """查看工作流详情"""
    node = _find_workflow(name)
    if not node:
        print(f"❌ 工作流未找到: {name}")
        sys.exit(1)

    # JSON 模式
    if "--json" in sys.argv:
        print(json.dumps(node, ensure_ascii=False, indent=2, default=str))
        return

    print(f"═══ {node.get('name', node.get('id'))} ═══")
    print(f"  ID:       {node.get('id')}")
    print(f"  类型:     {node.get('subtype')}")
    print(f"  域:       {node.get('domain')} | 层: {node.get('layer')}")
    print(f"  BOS URI:  {node.get('bos_uri')}")
    print(f"  状态:     {node.get('status')} | 版本: {node.get('version')}")
    print(f"  描述:     {node.get('description')}")
    print(f"  维护方:   {node.get('maintained_by')}")
    print()

    # 跨层映射
    cl = node.get("cross_layer", {})
    if cl:
        print("── 跨层映射 ──")
        if cl.get("realized_by"):
            for r in cl["realized_by"]:
                print(f"  实现方: {r.get('project')}/{r.get('package', '')} → {r.get('entrypoint', '?')}")
        if cl.get("invoked_by"):
            for i in cl["invoked_by"]:
                print(f"  调用方: [{i.get('layer', '?')}] {i.get('component', '?')} ({i.get('mechanism', '?')})")
        print()

    # 步骤
    steps = node.get("steps", [])
    if steps:
        print(f"── 步骤 ({len(steps)}) ──")
        for s in steps:
            dep = f" (依赖: {', '.join(s['depends_on'])})" if s.get("depends_on") else ""
            parallel = " ∥" if s.get("parallel") else ""
            print(f"  {s.get('order', '?')}. {s.get('name', '?')}{parallel}{dep}")
            print(f"     动作: {s.get('action', '?')}")
            if s.get("description"):
                print(f"     说明: {s.get('description')}")
        print()

    # 执行
    ex = node.get("execution", {})
    if ex:
        print("── 执行配置 ──")
        print(f"  模式: {ex.get('mode')} | 重试: {ex.get('max_retries')} | 超时: {ex.get('timeout')}s")
        print(f"  失败策略: {ex.get('on_failure')} | 审计: {ex.get('audit_enabled')}")
        print()

    # SLA
    sla = node.get("sla", {})
    if sla:
        print("── SLA ──")
        print(f"  最大执行时间: {sla.get('max_execution_time')}s")
        print(f"  期望完成率:   {sla.get('expected_completion_rate', 0.95)}")
        print(f"  关键路径:     {'是' if sla.get('critical') else '否'}")
        print()

    # 关系
    rels = node.get("relations", [])
    if rels:
        print(f"── 关系 ({len(rels)}) ──")
        for r in rels:
            print(f"  {r.get('type', '?')}: {r.get('from', '?')} → {r.get('to', '?')}")
            if r.get("note"):
                print(f"    备注: {r.get('note')}")

    # 标签
    tags = node.get("tags", [])
    if tags:
        print(f"\n── 标签 ──")
        print(f"  {', '.join(tags)}")


def cmd_validate(name=None):
    """校验工作流"""
    ci_mode = "--ci" in sys.argv

    if name:
        node = _find_workflow(name)
        if not node:
            print(f"❌ 工作流未找到: {name}")
            sys.exit(1)
        nodes = [node]
    else:
        nodes = _load_all_m1_nodes()

    errors = []
    warnings = []
    for n in nodes:
        nid = n.get("id", "?")
        # 必填字段检查
        for field in ["id", "type", "subtype", "name", "description", "domain", "layer", "bos_uri"]:
            if not n.get(field):
                errors.append(f"{nid}: 缺少必填字段 {field}")
        # subtype 检查
        valid_subtypes = ["PipelineWorkflow", "AgentWorkflow", "ScheduledWorkflow", "MCPWorkflow"]
        if n.get("subtype") not in valid_subtypes:
            errors.append(f"{nid}: 无效的 subtype '{n.get('subtype')}'")
        # domain 检查
        valid_domains = ["memory", "omo", "analysis", "persona", "forge", "meta", "infra"]
        if n.get("domain") not in valid_domains:
            errors.append(f"{nid}: 无效的 domain '{n.get('domain')}'")
        # steps 检查
        steps = n.get("steps", [])
        if not steps:
            warnings.append(f"{nid}: 无步骤定义")
        # cross_layer 检查
        cl = n.get("cross_layer", {})
        if not cl.get("realized_by"):
            warnings.append(f"{nid}: 未声明 cross_layer.realized_by")
        # bos_uri 格式检查
        bos = n.get("bos_uri", "")
        if bos and not bos.startswith("bos://ecos/workflow/"):
            warnings.append(f"{nid}: BOS URI 格式应为 bos://ecos/workflow/*")

    if not ci_mode:
        print(f"═══ 工作流校验 ({len(nodes)} 个) ═══\n")

    for w in warnings:
        print(f"⚠️  {w}")
    for e in errors:
        print(f"❌ {e}")

    if not ci_mode:
        print(f"\n✅ {len(nodes) - len(errors)}/{len(nodes)} 通过" if not errors else f"\n❌ {len(errors)} 个错误, {len(warnings)} 个警告")

    if errors:
        sys.exit(1)


def cmd_run(name, dry_run=False, params=None):
    """执行工作流 (通过 BOS URI 路由)"""
    node = _find_workflow(name)
    if not node:
        print(f"❌ 工作流未找到: {name}")
        sys.exit(1)

    bos_uri = node.get("bos_uri")
    print(f"═══ 执行工作流: {node.get('name')} ═══")
    print(f"  BOS URI: {bos_uri}")
    print(f"  实现方: {node.get('cross_layer', {}).get('realized_by', [{}])[0].get('project', '?')}")
    print()

    if dry_run:
        print("🔍 干运行模式 — 仅验证不执行")
        steps = node.get("steps", [])
        for s in steps:
            dep_ok = True
            if s.get("depends_on"):
                dep_ok = all(d in [st.get("name") for st in steps] for d in s["depends_on"])
            icon = "✅" if dep_ok else "⚠️"
            print(f"  {icon} 步骤 {s.get('order')}: {s.get('name')} → {s.get('action')}")
        print(f"\n✅ 干运行完成 ({len(steps)} 步骤可执行)")
        return

    print(f"⚠️ 执行需通过 Agora Service Mesh 路由")
    print(f"   路径: {bos_uri} → agora → {node.get('layer')} → {node.get('cross_layer', {}).get('realized_by', [{}])[0].get('project', '?')}")
    print(f"   提示: 实际执行需 agora MCP 工具 pipeline 支持")


def cmd_relations(name=None):
    """工作流关系图"""
    catalog = _load_catalog()
    global_rels = catalog.get("global_relations", {})

    if name:
        node = _find_workflow(name)
        if not node:
            print(f"❌ 工作流未找到: {name}")
            sys.exit(1)
        print(f"═══ 关系图: {node.get('name')} ═══\n")

        # 向上查找触发器
        triggers = global_rels.get("triggers", [])
        upstream = [t for t in triggers if t.get("to") == node.get("id")]
        if upstream:
            print("上游触发:")
            for u in upstream:
                print(f"  ← {u.get('from')} ({u.get('note', '')})")
        else:
            print("上游触发: (无)")

        # 向下查找被触发
        downstream = [t for t in triggers if t.get("from") == node.get("id")]
        if downstream:
            print("下游触发:")
            for d in downstream:
                print(f"  → {d.get('to')} ({d.get('note', '')})")
        else:
            print("下游触发: (无)")

        # 数据流
        data_flows = global_rels.get("data_flows", [])
        flows_in = [f for f in data_flows if f.get("to") and node.get("bos_uri", "") in f.get("to", "")]
        flows_out = [f for f in data_flows if f.get("from") and node.get("bos_uri", "") in f.get("from", "")]
        if flows_in:
            print("数据流入:")
            for f in flows_in:
                print(f"  ← {f.get('from')} ({f.get('note', '')})")
        if flows_out:
            print("数据流出:")
            for f in flows_out:
                print(f"  → {f.get('to')} ({f.get('note', '')})")

        # 依赖
        deps = global_rels.get("dependencies", [])
        my_deps = [d for d in deps if d.get("dependent") == node.get("id")]
        if my_deps:
            print("依赖:")
            for d in my_deps:
                print(f"  需要: {d.get('depends_on')} ({d.get('note', '')})")
    else:
        # 全局关系
        print("═══ 全局工作流关系图 ═══\n")

        triggers = global_rels.get("triggers", [])
        if triggers:
            print("触发链 (Mechanism → Workflow):")
            for t in triggers:
                print(f"  {t.get('from')} → {t.get('to')}")
                print(f"    {t.get('note', '')}")
            print()

        data_flows = global_rels.get("data_flows", [])
        if data_flows:
            print("数据流 (BOS URI → BOS URI):")
            for f in data_flows:
                print(f"  {f.get('from')} → {f.get('to')}")
                print(f"    {f.get('note', '')}")
            print()

        deps = global_rels.get("dependencies", [])
        if deps:
            print("依赖关系 (Workflow → Workflow):")
            for d in deps:
                print(f"  {d.get('dependent')} 依赖 {d.get('depends_on')}")
                if d.get("note"):
                    print(f"    {d.get('note')}")


def cmd_stats():
    """工作流统计"""
    nodes = _load_all_m1_nodes()
    catalog = _load_catalog()

    from collections import Counter
    layer_counter = Counter(n.get("layer", "?") for n in nodes)
    domain_counter = Counter(n.get("domain", "?") for n in nodes)
    subtype_counter = Counter(n.get("subtype", "?") for n in nodes)
    status_counter = Counter(n.get("status", "?") for n in nodes)

    print("═══ 工作流统计 ═══\n")
    print(f"  总数:   {len(nodes)}")
    print(f"  按层:   {dict(sorted(layer_counter.items()))}")
    print(f"  按域:   {dict(sorted(domain_counter.items()))}")
    print(f"  按类型: {dict(subtype_counter)}")
    print(f"  按状态: {dict(status_counter)}")
    print()

    # 步骤统计
    total_steps = sum(len(n.get("steps", [])) for n in nodes)
    avg_steps = total_steps / len(nodes) if nodes else 0
    print(f"  总步骤数: {total_steps}")
    print(f"  平均步骤: {avg_steps:.1f}")

    # 关键路径
    critical = [n.get("name") for n in nodes if n.get("sla", {}).get("critical")]
    if critical:
        print(f"  关键路径: {', '.join(critical)}")

    # 注册表一致性
    catalog_stats = catalog.get("stats", {})
    if catalog_stats:
        catalog_total = catalog_stats.get("total", 0)
        if catalog_total != len(nodes):
            print(f"\n⚠️ 注册表不一致: catalog={catalog_total}, M1节点={len(nodes)}")


def main():
    if len(sys.argv) < 2:
        print("织星 MOF — 工作流管理")
        print()
        print("用法:")
        print("  mof workflow list    [--domain <d>] [--layer <l>] [--status <s>]")
        print("  mof workflow show    <name> [--json]")
        print("  mof workflow validate [name] [--ci]")
        print("  mof workflow run     <name> [--dry-run]")
        print("  mof workflow relations [name] [--all]")
        print("  mof workflow stats")
        return

    cmd = sys.argv[1]

    # 解析过滤参数
    def _flag(name):
        try:
            idx = sys.argv.index(name)
            return sys.argv[idx + 1]
        except (ValueError, IndexError):
            return None

    domain = _flag("--domain")
    layer = _flag("--layer")
    status = _flag("--status")

    if cmd == "list":
        cmd_list(domain=domain, layer=layer, status=status)
    elif cmd == "show":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        if not name:
            print("❌ 缺少工作流名称")
            sys.exit(1)
        cmd_show(name)
    elif cmd == "validate":
        name = _flag("--name") or (sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None)
        cmd_validate(name)
    elif cmd == "run":
        name = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
        if not name:
            print("❌ 缺少工作流名称")
            sys.exit(1)
        dry_run = "--dry-run" in sys.argv
        params = _flag("--params")
        if params:
            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                print(f"⚠️ 无效 JSON params: {params}")
                params = None
        cmd_run(name, dry_run=dry_run, params=params)
    elif cmd == "relations":
        name = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
        cmd_relations(name)
    elif cmd == "stats":
        cmd_stats()
    else:
        print(f"未知命令: {cmd}")
        print("可用: list | show | validate | run | relations | stats")


if __name__ == "__main__":
    main()
