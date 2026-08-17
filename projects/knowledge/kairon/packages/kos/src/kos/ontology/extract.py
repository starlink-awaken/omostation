#!/usr/bin/env python3
# ruff: noqa
"""KOS Ontology Extract — 实体抽取 + 元数据自动发现.

从 ontology/engine.py 抽出 (God Module 拆分 wave 1, engine.py 1318->~768).
含 extract() (MD 实体抽取) + _auto_discover_metadata() (project-registry/patterns/governance/health 自动发现).
依赖 schema 组 (从 schema.py import).
"""

import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from kos.ontology.schema import (  # type: ignore[no-redef]
    MD_HEADING_RE,
    MD_LINK_RE,
    MD_TAG_RE,
    PREFIX_LIST,
    TYPE_MAP,
    _predicate_patterns,
    entity_files,
    get_db,
    init_schema,
)


def extract() -> dict[str, Any]:  # type: ignore[no-untyped-def]
    conn = get_db()  # type: ignore[no-untyped-call]
    init_schema(conn)  # type: ignore[no-untyped-call]
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    added = 0

    for file_path in entity_files():
        p = Path(file_path)
        if not p.exists():
            print(f"  ⚠️  Not found: {file_path}", file=sys.stderr)
            continue
        content = p.read_text(encoding="utf-8")
        zone = "guozhuan" if "国转中心" in str(p) else "gongwen"

        # Match entity sections like: ### person-xxx
        for m in MD_HEADING_RE.finditer(content):
            heading = m.group(1).strip()
            em = re.match(
                r"(person|org|project|regulation|doc|concept|event|role|axiom|principle|theory|framework|skill|consensus|task)-([\w-]+)",
                heading,
                re.IGNORECASE,
            )
            if not em:
                continue
            etype_raw = em.group(1).lower()
            eid_raw = em.group(2)
            etype = TYPE_MAP.get(etype_raw, etype_raw.capitalize())
            entity_id = f"{etype[0].upper()}:{eid_raw}"

            # Extract body until next ### or ---
            body_start = m.end()
            next_section = re.search(r"(^###|\n---)", content[body_start:], re.MULTILINE)
            body_end = body_start + next_section.start() if next_section else len(content)
            body = content[body_start:body_end].strip()

            # Extract label: **名称**: 夏同学 or **名称**：夏同学
            label = eid_raw.replace("-", " ").replace("_", " ")
            # Try multiple patterns for 名称 extraction
            name_match = re.search(r"\*\*名称\*\*\s*[：:]\s*(.+)", body)
            if not name_match:
                # Try without 名称 prefix: first non-empty meaningful line
                for line in body.split("\n"):
                    line = line.strip().lstrip("-").strip()
                    nm = re.match(r"\*\*([^*]+)\*\*\s*[：:]\s*(.+)", line)
                    if nm and nm.group(1).strip() not in (
                        "名称",
                        "标签",
                        "角色",
                        "背景",
                        "关联",
                        "详见",
                        "当前状态",
                        "成员",
                        "双重使命",
                    ):
                        label = nm.group(2).strip()
                        name_match = re.search(r"(.+)", label)  # dummy to pass the check below
                        break
            if name_match:
                label = name_match.group(1).strip()

            # Extract description: prefer background, fallback to role, then cleaned body
            for key in ["背景", "角色", "职责"]:
                dm = re.search(rf"\*\*{key}\*\*\s*[：:]\s*(.+?)(?:\n\*\*|\n##|\n\n\n|\Z)", body, re.DOTALL)
                if dm:
                    desc = dm.group(1).strip()
                    if len(desc) > 10:
                        description = desc[:200]
                        break
            else:
                clean_body = re.sub(r"\*\*[^*]+\*\*[：:]?\s*", "", body).strip()
                description = clean_body[:200]

            # Extract relations with per-relation predicate matching
            tags = MD_TAG_RE.findall(body)
            for m_link in MD_LINK_RE.finditer(body):
                m_link.group(1)
                rid = m_link.group(2)
                for prefix in PREFIX_LIST:
                    if rid.startswith(prefix):
                        etype_char = prefix[0].upper()
                        target_id = f"{etype_char}:{rid[len(prefix) :]}"
                        # Per-relation predicate: look at text after the link up to next | or [
                        post_link_start = m_link.end()
                        next_sep = re.search(r"[\[|]", body[post_link_start : post_link_start + 80])
                        post_text = body[post_link_start : post_link_start + 80]
                        if next_sep:
                            post_text = post_text[: next_sep.start()]
                        # Match predicate from the text between link and next separator
                        pred = "related_to"
                        for kn, patterns in _predicate_patterns().items():
                            for pattern in patterns:
                                if re.search(pattern, post_text):
                                    pred = kn
                                    break
                            if pred != "related_to":
                                break
                        # Insert with specific predicate
                        conn.execute(
                            """INSERT OR REPLACE INTO kos_relations
                            (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                            VALUES (?,?,?,?,?,?,?)""",
                            (entity_id, pred, target_id, 0.8, str(p), "auto-extract", now),
                        )
                        break

            # Associate entity with source document
            canonical = "kos::guozhuan::_工作机制/wiki/ENTITIES.md"
            doc_id = hashlib.sha1(canonical.encode()).hexdigest()
            conn.execute(
                """INSERT OR REPLACE INTO kos_entity_docs
                (entity_id,doc_id,relevance) VALUES (?,?,?)""",
                (entity_id, doc_id, 1.0),
            )

            # Upsert entity
            conn.execute(
                """INSERT OR REPLACE INTO kos_entities
                (entity_id,entity_type,label,aliases,description,primary_zone,source_file,metadata,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    entity_id,
                    etype,
                    label,
                    json.dumps([label]),
                    description,
                    zone,
                    str(p),
                    json.dumps({"tags": tags}),
                    now,
                ),
            )
            added += 1

    # ── Named-predicate entity extraction (entities.md format) ──
    ENTITY_HEADING_RE = re.compile(r"^###\s+([POJCDRANTFKSW]):(\S+)", re.MULTILINE)
    PRED_LINE_RE = re.compile(r"-\s+(\w+)::\[\[([A-Z]):([^\]]+)\]\]")
    TYPE_PREFIX_MAP = {
        "P": "Person",
        "O": "Organization",
        "J": "Project",
        "C": "Concept",
        "D": "Document",
        "R": "Role",
        "A": "Axiom",
        "N": "Principle",
        "T": "Theory",
        "F": "Framework",
        "K": "Skill",
        "S": "Consensus",
        "W": "Task",
    }

    for file_path in entity_files():
        p = Path(file_path)
        if not p.exists() or "entities.md" not in str(p):
            continue
        content = p.read_text(encoding="utf-8")
        for em in ENTITY_HEADING_RE.finditer(content):
            etype_char = em.group(1)
            eid = em.group(2)
            etype = TYPE_PREFIX_MAP.get(etype_char, "Concept")
            entity_id = f"{etype_char}:{eid}"
            body_start = em.end()
            ns = re.search(r"\n###", content[body_start:])
            body = content[body_start : body_start + ns.start()] if ns else content[body_start:]
            label = eid.replace("-", " ").replace("_", " ").title()
            for pm in PRED_LINE_RE.finditer(body):
                target_id = f"{pm.group(2)}:{pm.group(3)}"
                conn.execute(
                    """INSERT OR REPLACE INTO kos_relations
                    (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                    VALUES (?,?,?,?,?,?,?)""",
                    (entity_id, pm.group(1), target_id, 1.0, str(p), "manual", now),
                )
            conn.execute(
                """INSERT OR REPLACE INTO kos_entities
                (entity_id,entity_type,label,aliases,description,primary_zone,source_file,metadata,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    entity_id,
                    etype,
                    label,
                    json.dumps([label]),
                    body.strip()[:200],
                    "obsidian",
                    str(p),
                    json.dumps({"source": "entities.md"}),
                    now,
                ),
            )
            added += 1

    # 4. Meta-data driven auto-discovery (EicosParser)
    added += _auto_discover_metadata(conn, now)

    conn.commit()
    # ── Gongwen domain structure (NOT extracted as Concepts) ──
    # Directory names like "组织机构", "制度规范" are file categories, not knowledge concepts.
    # They are accessible via KOS zone browsing (`kos domains`, `kos status`).
    # See: kos-entity-governance.py for entity quality rules.

    conn.commit()
    conn.close()
    return {"extracted": added, "timestamp": now}


def _auto_discover_metadata(conn: sqlite3.Connection, now: str) -> int:
    """自动从项目物理元数据注册表（docs/project-registry.yaml、checks 等）提取本体实体与规则"""
    added = 0

    # 1. 动态定位 Workspace 根目录
    workspace_root = None
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "docs/project-registry.yaml").is_file():
            workspace_root = parent
            break
    if not workspace_root:
        workspace_root = Path("/Users/xiamingxing/Workspace")

    # 2. 自动提取 docs/project-registry.yaml (项目与微服务席位)
    registry_path = workspace_root / "docs/project-registry.yaml"
    if registry_path.is_file():
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                reg_data = yaml.safe_load(f)

            projects_dict = reg_data.get("projects", {})
            for proj_name, details in projects_dict.items():
                if not details:
                    continue
                entity_id = f"J:{proj_name}"
                entity_type = "Project"
                label = proj_name.replace("-", " ").title()
                description = details.get("role", f"Subproject in workspace: {proj_name}")
                primary_zone = "workspace"
                metadata = {
                    "layer": details.get("layer"),
                    "stack": details.get("stack"),
                    "version": details.get("version"),
                    "python": details.get("python"),
                }

                conn.execute(
                    """INSERT OR REPLACE INTO kos_entities
                    (entity_id,entity_type,label,aliases,description,primary_zone,source_file,metadata,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        entity_id,
                        entity_type,
                        label,
                        json.dumps([label, proj_name]),
                        description,
                        primary_zone,
                        str(registry_path),
                        json.dumps(metadata),
                        now,
                    ),
                )
                added += 1

                layer = details.get("layer")
                if layer:
                    layer_concept = f"C:Layer-{layer}"
                    conn.execute(
                        """INSERT OR IGNORE INTO kos_entities
                        (entity_id,entity_type,label,aliases,description,primary_zone,source_file,metadata,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (
                            layer_concept,
                            "Concept",
                            f"Layer {layer}",
                            json.dumps([f"Layer {layer}"]),
                            f"eCOS Architecture Layer {layer}",
                            "workspace",
                            str(registry_path),
                            "{}",
                            now,
                        ),
                    )
                    conn.execute(
                        """INSERT OR REPLACE INTO kos_relations
                        (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                        VALUES (?,?,?,?,?,?,?)""",
                        (entity_id, "member_of", layer_concept, 1.0, str(registry_path), "auto-discover", now),
                    )

            # 2.2 自动提取 omlx Local Compute Mesh Nodes (算力节点席位)
            nodes_dict = reg_data.get("compute_nodes", {}) or {}
            for node_name, details in nodes_dict.items():
                if not details:
                    continue
                entity_id = f"N:{node_name}"
                entity_type = "Node"
                label = node_name.replace("-", " ")
                ip = details.get("ip", "unknown")
                hardware = details.get("hardware", "unknown")
                vram = details.get("vram", "unknown")
                description = f"{label} (IP: {ip}) - {hardware}, {vram} VRAM."
                primary_zone = "workspace"
                metadata = {"ip": ip, "hardware": hardware, "vram": vram, "role": details.get("role")}

                conn.execute(
                    """INSERT OR REPLACE INTO kos_entities
                    (entity_id,entity_type,label,aliases,description,primary_zone,source_file,metadata,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        entity_id,
                        entity_type,
                        label,
                        json.dumps([label, node_name]),
                        description,
                        primary_zone,
                        str(registry_path),
                        json.dumps(metadata),
                        now,
                    ),
                )
                added += 1

                # 建立与托管模型的 runs_model 关系
                models_list = details.get("models", []) or []
                for model in models_list:
                    model_concept = f"C:Model-{model}"
                    conn.execute(
                        """INSERT OR IGNORE INTO kos_entities
                        (entity_id,entity_type,label,aliases,description,primary_zone,source_file,metadata,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (
                            model_concept,
                            "Concept",
                            f"Model {model}",
                            json.dumps([f"Model {model}", model]),
                            f"omlx Gateway LLM Model: {model}",
                            "workspace",
                            str(registry_path),
                            "{}",
                            now,
                        ),
                    )
                    conn.execute(
                        """INSERT OR REPLACE INTO kos_relations
                        (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                        VALUES (?,?,?,?,?,?,?)""",
                        (entity_id, "runs_model", model_concept, 1.0, str(registry_path), "auto-discover", now),
                    )
        except Exception as ex:
            print(f"  ⚠️  Failed to parse project registry: {ex}", file=sys.stderr)

    # 2.3 自动发现 .omo/_knowledge/patterns/ 下的 Consensus 避坑共识
    patterns_dir = workspace_root / ".omo/_knowledge/patterns"
    if patterns_dir.is_dir():
        try:
            for md_file in patterns_dir.glob("*.md"):
                file_name = md_file.stem
                entity_id = f"S:{file_name}"
                entity_type = "Consensus"

                label = file_name.replace("-", " ").title()
                description = "Consensus pattern guidelines"

                try:
                    with open(md_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for line in lines:
                        if line.startswith("# "):
                            label = line.replace("# ", "").strip()
                            break
                    for line in lines:
                        cleaned = line.strip()
                        if cleaned and not cleaned.startswith("#") and not cleaned.startswith(">"):
                            description = cleaned[:150] + ("..." if len(cleaned) > 150 else "")
                            break
                except Exception:
                    pass

                conn.execute(
                    """INSERT OR REPLACE INTO kos_entities
                    (entity_id,entity_type,label,aliases,description,primary_zone,source_file,metadata,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        entity_id,
                        entity_type,
                        label,
                        json.dumps([label, file_name]),
                        description,
                        "workspace",
                        str(md_file),
                        "{}",
                        now,
                    ),
                )
                added += 1
        except Exception as ex:
            print(f"  ⚠️  Failed to auto-discover Consensus patterns: {ex}", file=sys.stderr)

    # 3. 自动提取 .omo/_truth/registry/governance-checks.yaml (X1-X4 治理规则)
    checks_path = workspace_root / ".omo/_truth/registry/governance-checks.yaml"
    if checks_path.is_file():
        try:
            with open(checks_path, "r", encoding="utf-8") as f:
                contents = f.read()
                parts = contents.split("---")
                yaml_content = parts[-1] if len(parts) > 1 else contents
                checks_data = yaml.safe_load(yaml_content) or {}

            checkers_list = checks_data.get("checkers", [])
            for checker in checkers_list:
                cid = checker.get("id")
                if not cid:
                    continue
                entity_id = f"W:checker-{cid}"
                label = checker.get("name", cid)
                description = checker.get("description", "")
                metadata = {
                    "dimension": checker.get("dimension"),
                    "severity": checker.get("severity"),
                    "class": checker.get("class"),
                }
                conn.execute(
                    """INSERT OR REPLACE INTO kos_entities
                    (entity_id,entity_type,label,aliases,description,primary_zone,source_file,metadata,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        entity_id,
                        "Task",
                        label,
                        json.dumps([label, cid]),
                        description,
                        "omo",
                        str(checks_path),
                        json.dumps(metadata),
                        now,
                    ),
                )
                added += 1

            gac_dict = checks_data.get("gac") or {}
            rules_list = gac_dict.get("rules", []) if isinstance(gac_dict, dict) else []
            for rule in rules_list:
                rid = rule.get("id")
                if not rid:
                    continue
                entity_id = f"A:{rid}"
                label = rule.get("name", rid)
                description = rule.get("description", "")
                metadata = {
                    "dimension": rule.get("dimension"),
                    "layer": rule.get("layer"),
                    "lifecycle": rule.get("lifecycle"),
                    "adr": rule.get("adr"),
                }
                conn.execute(
                    """INSERT OR REPLACE INTO kos_entities
                    (entity_id,entity_type,label,aliases,description,primary_zone,source_file,metadata,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        entity_id,
                        "Axiom",
                        label,
                        json.dumps([label, rid]),
                        description,
                        "omo",
                        str(checks_path),
                        json.dumps(metadata),
                        now,
                    ),
                )
                added += 1

                adr = rule.get("adr")
                if adr:
                    adr_doc = f"D:{adr}"
                    conn.execute(
                        """INSERT OR IGNORE INTO kos_entities
                        (entity_id,entity_type,label,aliases,description,primary_zone,source_file,metadata,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (
                            adr_doc,
                            "Document",
                            adr,
                            json.dumps([adr]),
                            f"Architecture Decision Record: {adr}",
                            "omo",
                            str(checks_path),
                            "{}",
                            now,
                        ),
                    )
                    conn.execute(
                        """INSERT OR REPLACE INTO kos_relations
                        (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                        VALUES (?,?,?,?,?,?,?)""",
                        (entity_id, "related_to", adr_doc, 1.0, str(checks_path), "auto-discover", now),
                    )
        except Exception as ex:
            print(f"  ⚠️  Failed to parse governance checks: {ex}", file=sys.stderr)

    # 4. 动态关联 OMO 运行时 Anomaly 异常状况 (MOF Closed-loop Trace)
    health_path = workspace_root / ".omo/state/health.yaml"
    if health_path.is_file():
        try:
            with open(health_path, "r", encoding="utf-8") as f:
                health_data = yaml.safe_load(f) or {}
            anomalies = health_data.get("anomalies", [])
            for index, anomaly in enumerate(anomalies):
                checker_id = anomaly.get("checker", "unknown")
                message = anomaly.get("message", "Anomaly detected")
                entity_id = f"D:evidence-{checker_id}-{index}"
                label = f"Evidence ({checker_id})"

                conn.execute(
                    """INSERT OR REPLACE INTO kos_entities
                    (entity_id,entity_type,label,aliases,description,primary_zone,source_file,metadata,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        entity_id,
                        "Document",
                        label,
                        json.dumps([label]),
                        message,
                        "omo",
                        str(health_path),
                        json.dumps(anomaly),
                        now,
                    ),
                )
                added += 1

                rule_rows = conn.execute("SELECT entity_id FROM kos_entities WHERE entity_type='Axiom'").fetchall()
                matched_rule = None
                for r in rule_rows:
                    rid = r["entity_id"]
                    if checker_id.lower().replace("-", "") in rid.lower().replace("-", "") or rid.lower().replace(
                        "-", ""
                    ) in checker_id.lower().replace("-", ""):
                        matched_rule = rid
                        break
                if matched_rule:
                    conn.execute(
                        """INSERT OR REPLACE INTO kos_relations
                        (source_id,predicate,target_id,confidence,source_doc,source_type,updated_at)
                        VALUES (?,?,?,?,?,?,?)""",
                        (matched_rule, "has_active_violation", entity_id, 1.0, str(health_path), "mof-linkage", now),
                    )
        except Exception as ex:
            print(f"  ⚠️  Failed to link MOF runtime anomalies: {ex}", file=sys.stderr)

    return added
