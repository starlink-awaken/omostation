#!/usr/bin/env python3
# bin/gac-kos-sync.py — KOS 运行时违规与 OMO 状态同步特权代理 (GaC-v6 治理标准)

import os
import sys
import sqlite3
import yaml
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
db_path = WORKSPACE / "kos/kos-index.sqlite"
health_yaml_path = WORKSPACE / ".omo/state/health.yaml"

def main() -> int:
    if not db_path.is_file() or not health_yaml_path.is_file():
        return 0
    try:
        # 1. 从 KOS SQLite 读取层级违规关系
        db_conn = sqlite3.connect(str(db_path))
        db_conn.row_factory = sqlite3.Row
        violations = db_conn.execute(
            "SELECT source_id, target_id FROM kos_relations WHERE predicate='violates_layer_dependency'"
        ).fetchall()
        db_conn.close()

        # 2. 读取当前健康状态
        with open(health_yaml_path, "r", encoding="utf-8") as hf:
            health_data = yaml.safe_load(hf) or {}

        # 3. 构造 anomalies 异常
        anomalies = []
        for idx, v in enumerate(violations):
            anomalies.append({
                "checker": "kos-layer-dependency",
                "message": f"Architecture Violation: Low-layer '{v['source_id']}' illegally depends on high-layer '{v['target_id']}'",
                "severity": "error",
                "detected_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            })

        # 每个违规扣除 15 分
        deductions = 15 * len(anomalies)
        new_score = max(0, 100 - deductions)

        health_data["anomalies"] = anomalies
        health_data["health_score"] = new_score
        health_data["anomaly_count"] = len(anomalies)
        health_data["generated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

        # 4. 合规写回健康分 (由于脚本以 gac- 开头，被 contract_gatekeeper 自动豁免)
        with open(health_yaml_path, "w", encoding="utf-8") as hf:
            yaml.safe_dump(health_data, hf, allow_unicode=True)
            
        print(f"📊 KOS Active Loop: Synced {len(anomalies)} violations to OMO health state. New Score: {new_score}")

        # 5. 自动导出 Mermaid 全域拓扑图至 docs/generated/kos-ontology-graph.md
        db_conn = sqlite3.connect(str(db_path))
        db_conn.row_factory = sqlite3.Row
        all_edges = db_conn.execute("SELECT source_id, predicate, target_id FROM kos_relations").fetchall()
        all_ents = {r["entity_id"]: dict(r) for r in db_conn.execute("SELECT * FROM kos_entities").fetchall()}
        db_conn.close()

        mermaid_lines = [
            "# eCOS v6 物理拓扑与架构依赖图谱",
            "",
            "> **自动刷新时间**: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "> **数据源**: KOS SQLite 本体引擎 · `EicosParser` 自动提取",
            "",
            "```mermaid",
            "graph TD",
            "    %% Style definitions",
            "    classDef project fill:#2b303c,stroke:#4f5b66,stroke-width:1px,color:#fff;",
            "    classDef node fill:#1f3c3d,stroke:#3e787a,stroke-width:2px,color:#fff;",
            "    classDef axiom fill:#4a3c31,stroke:#8f7b6e,stroke-width:1px,color:#fff;",
            "    classDef concept fill:#3c2b3d,stroke:#77567a,stroke-width:1px,color:#fff;",
            "    classDef evidence fill:#5c2b2b,stroke:#b85c5c,stroke-width:2px,color:#fff;"
        ]

        link_index = 0
        violation_links = []
        seen_relations = set()

        for edge in all_edges:
            s = edge["source_id"]
            p = edge["predicate"]
            t = edge["target_id"]
            
            s_type = all_ents.get(s, {}).get("entity_type", "unknown")
            t_type = all_ents.get(t, {}).get("entity_type", "unknown")
            
            rel_key = (s, p, t)
            if rel_key in seen_relations:
                continue
            seen_relations.add(rel_key)

            s_label = all_ents.get(s, {}).get("label", s)
            t_label = all_ents.get(t, {}).get("label", t)
            
            def get_mermaid_node(eid, label, etype):
                escaped_label = label.replace('"', '\\"')
                if etype == "Project":
                    return f'{eid}["J:{escaped_label}"]:::project'
                elif etype == "Node":
                    return f'{eid}["N:{escaped_label}"]:::node'
                elif etype == "Axiom":
                    return f'{eid}["A:{escaped_label}"]:::axiom'
                elif etype == "Concept":
                    return f'{eid}["C:{escaped_label}"]:::concept'
                elif etype == "Document" and "evidence" in eid:
                    return f'{eid}["D:{escaped_label}"]:::evidence'
                return f'{eid}["{escaped_label}"]'

            # Format IDs for Mermaid compatibility
            s_id = s.replace(":", "_").replace("-", "_")
            t_id = t.replace(":", "_").replace("-", "_")

            s_node = get_mermaid_node(s_id, s_label, s_type)
            t_node = get_mermaid_node(t_id, t_label, t_type)

            mermaid_lines.append(f'    {s_node} -->|{p}| {t_node}')
            
            if p in ("violates_layer_dependency", "has_active_violation"):
                violation_links.append(link_index)
            
            link_index += 1

        for idx in violation_links:
            mermaid_lines.append(f"    linkStyle {idx} stroke:#ff4444,stroke-width:3px,stroke-dasharray: 5 5;")

        mermaid_lines.append("```")
        mermaid_lines.append("")
        mermaid_lines.append("---")
        mermaid_lines.append("## 📊 实体指标统计")
        mermaid_lines.append(f"* **总实体数**: {len(all_ents)}")
        mermaid_lines.append(f"* **总关系数**: {len(all_edges)}")

        graph_md_path = WORKSPACE / "docs/generated/kos-ontology-graph.md"
        graph_md_path.parent.mkdir(parents=True, exist_ok=True)
        with open(graph_md_path, "w", encoding="utf-8") as gf:
            gf.write("\n".join(mermaid_lines))
            
        print(f"📈 KOS Map exported successfully: {graph_md_path}")
        return 0
    except Exception as e:
        print(f"❌ KOS Active Loop Sync Failed: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
