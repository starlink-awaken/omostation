"""ecos.l0.ssot.cli_export — cmd_export 拆分 (P110 步骤2).

TASK-F7114ABA (omo lint god-module 800L 硬规则).
ecos/l0/ssot/cli.py 958L 拆分: cmd_export (~122L) 独立到本模块,
cli.py 降至 <840L (继续 P110 步骤3 拆 cmd_graph).

业务: 导出知识库为通用格式 (单源 + 子模型 + 状态机 + transitions + rules).

模式: 顶层 re-export (PFC) 保持 `from .cli import cmd_export` 仍可用.
调用方 `from ecos.l0.ssot.cli import cmd_export` 不破.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from .config_loader import load_domain


def cmd_export(args):
    """导出知识库为通用格式"""
    config = load_domain(args.dir)
    fmt = args.format
    out = args.output

    if fmt == "json":
        data = {
            "domain": config.domain.get("name", "unknown"),
            "entities": [
                {
                    "id": e.id,
                    "type": e.entity_type,
                    "name": e.name,
                    "status": e.status,
                    "attributes": dict(e.attributes),
                }
                for e in config.entities
            ],
            "facts": [
                {
                    "id": f.id,
                    "title": f.title,
                    "value": f.value,
                    "unit": f.unit,
                    "source": f.source,
                }
                for f in config.facts
            ],
            "inferences": [
                {
                    "id": i.id,
                    "title": i.title,
                    "conclusion": i.conclusion,
                    "theory": i.theory,
                    "derives_from": i.derives_from,
                }
                for i in config.inferences
            ],
            "relations": [
                {"source": r.source_id, "type": r.relation_type, "target": r.target_id}
                for r in config.relations
            ],
            "rules": [
                {"id": r.id, "pattern": r.pattern, "name": r.name} for r in config.rules
            ],
            "state_machines": [
                {
                    "id": sm.id,
                    "name": sm.name,
                    "states": [{"id": s.id, "name": s.name} for s in sm.states],
                    "transitions": [
                        {
                            "from": t.from_state,
                            "to": t.to_state,
                            "condition": t.condition,
                        }
                        for t in sm.transitions
                    ],
                }
                for sm in config.state_machines
            ],
        }
        output = json.dumps(data, ensure_ascii=False, indent=2)

    elif fmt == "csv":
        import csv
        import io

        buf = io.StringIO()

        w = csv.writer(buf)
        w.writerow(["type", "id", "name", "detail"])
        for e in config.entities:
            w.writerow(["entity", e.id, e.name, e.entity_type])
        for f in config.facts:
            w.writerow(["fact", f.id, f.title, str(f.value or "")])
        for i in config.inferences:
            w.writerow(["inference", i.id, i.title, i.conclusion[:60]])
        for r in config.relations:
            w.writerow(
                ["relation", f"{r.source_id}→{r.target_id}", r.relation_type, ""]
            )
        output = buf.getvalue()

    elif fmt == "md":
        lines = [f"# SSOT 知识库: {config.domain.get('name', 'unknown')}", ""]
        lines.append(f"生成时间: {datetime.datetime.now().isoformat()}", "")  # type: ignore[reportCallIssue]
        lines.append("## 实体")
        for e in config.entities:
            attrs = "; ".join(f"{k}={v}" for k, v in list(e.attributes.items())[:3])
            lines.append(f"- **{e.id}**: {e.name} ({e.entity_type}) — {attrs}")
        lines.append("")
        lines.append("## 事实")
        for f in config.facts:
            lines.append(f"- **{f.id}**: {f.title} = {f.value} {f.unit}")
        lines.append("")
        lines.append("## 推论")
        for i in config.inferences:
            theory = f" [{i.theory}]" if i.theory else ""
            lines.append(f"- **{i.id}**: {i.title}{theory}")
        lines.append("")
        lines.append("## 规则")
        for r in config.rules:
            lines.append(f"- **{r.id}** ({r.pattern}): {r.name}")
        lines.append("")
        lines.append("## 关系")
        for r in config.relations:
            lines.append(f"- {r.source_id} --[{r.relation_type}]--> {r.target_id}")
        output = "\n".join(lines)

    else:
        print(f"❌ 不支持的格式: {fmt}（可选: json, csv, md）")
        return 1

    if out:
        Path(out).write_text(output, encoding="utf-8")
        print(f"✅ 已导出: {out} ({len(output)} 字节)")
    else:
        print(output)

    return 0
