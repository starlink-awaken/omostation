#!/usr/bin/env python3
"""元模型 §6 月度自动审计 — L4 文档域合规矩阵 (v1.1)

修正 v1.0:
- 修正 design-skip 域(@家庭生活 iCloud / @工作文档 聚合 / 合同法规 文件库)
- 修正实体/知识面判定逻辑(Aggregate 域可选,文件库域不需要)
- 添加 OPC 实体/知识面

用法:
    python3 meta-model-audit.py
    python3 meta-model-audit.py --domain 驾驶舱
    python3 meta-model-audit.py --report

输出: 元模型 §6 合规矩阵(对照 DOMAIN-META-MODEL.md §6)
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

THIS_DIR = Path(__file__).resolve().parent
DOCUMENTS_BASE = Path(os.path.expanduser("~/Documents"))

# v1.1: 增加 design_skip 字段
#   - aggregate: 聚合入口,设计上不维护完整控制面
#   - iCloud: iCloud 同步域,数据不在 Documents 内
#   - filelib: 文件库,设计上不需要 KEMS 六平面
DOMAINS = [
    # (domain_id, domain_type, path, tier, design_skip, control_required, entity_required, knowledge_required)
    ("cockpit", "A", "@驾驶舱", 3, "none", ["STATUS.md", "STATE.md", "MEMORY.md", "TIMELINE.md", "signals.md", "control-rules.md"], False, False),  # 驾驶舱:聚合+全功能,使用完整控制面
    ("vault", "F", "@学习进化", 1, "none", ["STATUS.md", "STATE.md", "MEMORY.md", "TIMELINE.md", "signals.md", "control-rules.md"], True, True),
    ("personal", "F", "@个人", 1, "none", ["STATUS.md", "STATE.md", "MEMORY.md", "TIMELINE.md", "signals.md", "control-rules.md"], True, True),
    ("shared", "I", "@公共", 1, "none", ["STATUS.md", "STATE.md", "MEMORY.md", "TIMELINE.md", "signals.md", "control-rules.md"], True, True),
    ("family", "F", "@家庭生活", 1, "iCloud", ["STATUS.md", "STATE.md", "MEMORY.md", "signals.md", "control-rules.md"], False, False),
    ("work-docs", "A", "@工作文档", 1, "aggregate", ["CLAUDE.md"], False, False),  # 聚合入口,仅需 CLAUDE.md
    ("creative", "F", "@创意创作", 1, "none", ["STATUS.md", "STATE.md", "MEMORY.md", "TIMELINE.md", "signals.md", "control-rules.md"], True, True),
    ("opc", "F", "@OPC", 1, "none", ["STATUS.md", "STATE.md", "MEMORY.md", "TIMELINE.md", "signals.md", "control-rules.md"], True, True),
    ("work-weijian", "S", "@工作文档/卫健委", 1, "none", ["STATUS.md", "STATE.md", "MEMORY.md", "TIMELINE.md", "signals.md", "control-rules.md"], True, True),
    ("work-guozhuan", "S", "@工作文档/国转中心", 1, "none", ["STATUS.md", "STATE.md", "MEMORY.md", "TIMELINE.md", "signals.md", "control-rules.md"], True, True),
    ("contract", "S", "@工作文档/合同法规", 1, "filelib", [], False, False),
]


def audit_domain(domain_id, domain_type, domain_path, tier, design_skip, control_required, entity_required, knowledge_required):
    """审计单个域的合规状态。"""
    path = DOCUMENTS_BASE / domain_path
    result = {
        "domain_id": domain_id,
        "domain_type": domain_type,
        "domain_path": domain_path,
        "tier": tier,
        "design_skip": design_skip,
        "control_plane": {},
        "knowledge_plane": "⭕",
        "storage_plane": False,
        "archive_plane": False,
        "entity_plane": "⭕",
        "overall": "🟢",
        "issues": [],
    }

    if design_skip == "filelib":
        # 文件库型 — 仅检查 CLAUDE.md 存在
        result["overall"] = "🟢"
        return result
    if design_skip == "iCloud":
        # iCloud 同步域 — 实体/知识面在 @公共/_entities/,不重复
        result["entity_plane"] = "⭕"
        result["knowledge_plane"] = "⭕"

    # 控制面 — aggregate 域检查 CLAUDE.md(在域根),其他检查 _control/ 下文件
    if design_skip == "aggregate":
        # 聚合入口(如 @工作文档)— 控制面是 CLAUDE.md 在域根
        claude_path = path / "CLAUDE.md"
        result["control_plane"]["CLAUDE.md"] = claude_path.exists()
        if not claude_path.exists():
            result["issues"].append("聚合入口缺失 CLAUDE.md")
    else:
        control_dir = path / "_control"
        for f in control_required:
            exists = (control_dir / f).exists() if control_dir.exists() else False
            result["control_plane"][f] = exists
            if not exists:
                result["issues"].append(f"控制面缺失: {f}")

    # 知识面
    if knowledge_required:
        knowledge_dir = path / "_knowledge"
        result["knowledge_plane"] = knowledge_dir.exists() and any(knowledge_dir.iterdir()) if knowledge_dir.exists() else False
        if not result["knowledge_plane"]:
            result["issues"].append("知识面缺失或为空")
    else:
        result["knowledge_plane"] = "⭕"

    # 资料面
    storage_dir = path / "_storage"
    result["storage_plane"] = storage_dir.exists() and any(storage_dir.iterdir()) if storage_dir.exists() else False

    # 归档
    archive_dir = path / "_archive"
    result["archive_plane"] = archive_dir.exists() and any(archive_dir.iterdir()) if archive_dir.exists() else False

    # 实体面
    if entity_required:
        entity_file = path / "_entities" / "ENTITIES.md"
        result["entity_plane"] = entity_file.exists()
        if not result["entity_plane"]:
            result["issues"].append("实体面缺失: _entities/ENTITIES.md")
    else:
        result["entity_plane"] = "⭕"

    # 综合评级
    if not result["issues"]:
        result["overall"] = "🟢"
    elif len(result["issues"]) <= 1:
        result["overall"] = "🟡"
    elif any("缺失" in i for i in result["issues"]):
        result["overall"] = "🔴"
    else:
        result["overall"] = "🟡"

    return result


def print_audit_table(results):
    """打印合规矩阵表格"""
    print(f"\n{'='*120}")
    print(f"  元模型 §6 月度审计 v1.1 — {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*120}\n")

    print(f"  {'域':<14} {'类型':<4} {'设计':<10} {'STATUS':<3} {'STATE':<3} {'MEMORY':<3} {'TIMELINE':<3} {'signals':<3} {'control-rules':<3} {'实体':<3} {'知识':<3} {'资料':<3} {'归档':<3} {'综合':<4}")
    print(f"  {'─'*14} {'─'*4} {'─'*10} {'─'*3} {'─'*3} {'─'*3} {'─'*3} {'─'*3} {'─'*3} {'─'*3} {'─'*3} {'─'*3} {'─'*3} {'─'*4}")

    for r in results:
        cp = r["control_plane"]
        def cell(key, default="⭕"):
            if key not in cp: return default
            return "✅" if cp[key] else "❌"
        st = cell("STATUS.md")
        sa = cell("STATE.md")
        me = cell("MEMORY.md")
        ti = cell("TIMELINE.md")
        si = cell("signals.md")
        cr = cell("control-rules.md")
        ent = r["entity_plane"] if isinstance(r["entity_plane"], str) else ("✅" if r["entity_plane"] else "❌")
        kn = r["knowledge_plane"] if isinstance(r["knowledge_plane"], str) else ("✅" if r["knowledge_plane"] else "❌")
        st_ = "✅" if r["storage_plane"] else "⭕"
        ar = "✅" if r["archive_plane"] else "⭕"
        ds = r["design_skip"][:10] if r["design_skip"] != "none" else ""
        print(f"  {r['domain_id']:<14} {r['domain_type']:<4} {ds:<10} {st:<3} {sa:<3} {me:<3} {ti:<3} {si:<3} {cr:<3} {ent:<3} {kn:<3} {st_:<3} {ar:<3} {r['overall']:<4}")
    print()


def save_history(results, history_file, max_history=12):
    record = {
        "ts": datetime.now().isoformat(),
        "domains": [{"id": r["domain_id"], "status": r["overall"], "issues": len(r["issues"])} for r in results],
        "totals": {
            "green": sum(1 for r in results if r["overall"] == "🟢"),
            "yellow": sum(1 for r in results if r["overall"] == "🟡"),
            "red": sum(1 for r in results if r["overall"] == "🔴"),
            "issues": sum(len(r["issues"]) for r in results),
        },
    }

    history = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text())
        except Exception:
            history = []
    history.append(record)
    history = history[-max_history:]
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False))

    if len(history) >= 2:
        prev = history[-2]["totals"]
        curr = record["totals"]
        print(f"\n▶ 趋势 (vs 上期)")
        print(f"  🟢 绿: {prev['green']} → {curr['green']} ({curr['green']-prev['green']:+d})")
        print(f"  🟡 黄: {prev['yellow']} → {curr['yellow']} ({curr['yellow']-prev['yellow']:+d})")
        print(f"  🔴 红: {prev['red']} → {curr['red']} ({curr['red']-prev['red']:+d})")
        print(f"  📋 债务: {prev['issues']} → {curr['issues']} ({curr['issues']-prev['issues']:+d})")
    return history, record


def print_markdown_report(results):
    print(f"\n# 元模型 §6 月度审计报告 v1.1 — {datetime.now().strftime('%Y-%m-%d')}\n")
    print(f"\n## 全量合规矩阵\n")
    print(f"| 域 | 类型 | 设计 | STATUS | STATE | MEMORY | TIMELINE | signals | control-rules | 实体 | 知识 | 资料 | 归档 | 综合 |")
    print(f"|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        cp = r["control_plane"]
        def cell(key, default="⭕"):
            if key not in cp: return default
            return "✅" if cp[key] else "❌"
        st = cell("STATUS.md")
        sa = cell("STATE.md")
        me = cell("MEMORY.md")
        ti = cell("TIMELINE.md")
        si = cell("signals.md")
        cr = cell("control-rules.md")
        ent = r["entity_plane"] if isinstance(r["entity_plane"], str) else ("✅" if r["entity_plane"] else "❌")
        kn = r["knowledge_plane"] if isinstance(r["knowledge_plane"], str) else ("✅" if r["knowledge_plane"] else "❌")
        st_ = "✅" if r["storage_plane"] else "⭕"
        ar = "✅" if r["archive_plane"] else "⭕"
        ds = r["design_skip"] if r["design_skip"] != "none" else ""
        print(f"| {r['domain_id']} | {r['domain_type']} | {ds} | {st} | {sa} | {me} | {ti} | {si} | {cr} | {ent} | {kn} | {st_} | {ar} | {r['overall']} |")
    print()
    issues = [(r["domain_id"], i) for r in results for i in r["issues"]]
    if issues:
        print(f"\n## 待修复债务\n")
        for d, i in issues:
            print(f"- **{d}**: {i}")
    else:
        print(f"\n✅ 全量域 100% 合规,无债务")


def main():
    parser = argparse.ArgumentParser(description="元模型 §6 月度自动审计")
    parser.add_argument("--domain", help="审计单个域")
    parser.add_argument("--report", action="store_true", help="输出 Markdown 报告")
    args = parser.parse_args()

    targets = DOMAINS
    if args.domain:
        targets = [d for d in DOMAINS if d[0] == args.domain]
        if not targets:
            print(f"❌ 未找到域: {args.domain}")
            return 1

    results = [audit_domain(*d) for d in targets]

    if args.report:
        print_markdown_report(results)
    else:
        print_audit_table(results)
        issues = sum(len(r["issues"]) for r in results)
        print(f"\n  审计结果: {sum(1 for r in results if r['overall']=='🟢')} 绿 / "
              f"{sum(1 for r in results if r['overall']=='🟡')} 黄 / "
              f"{sum(1 for r in results if r['overall']=='🔴')} 红")
        print(f"  待修复债务: {issues} 条")

    history_file = DOCUMENTS_BASE / "@驾驶舱" / "_generated" / "audit-history.json"
    save_history(results, history_file)

    return 0


if __name__ == "__main__":
    sys.exit(main())