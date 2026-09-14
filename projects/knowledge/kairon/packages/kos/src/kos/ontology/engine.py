#!/usr/bin/env python3
# ruff: noqa
"""
KOS Ontology Engine v1.0 — 本体推理与实体管理
"""

import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# Re-export schema 组 (抽到 schema.py, 保持 engine API 向后兼容 + mypy 跟踪)
from kos.ontology.schema import (  # type: ignore[no-redef]
    ENTITY_REF_RE,
    FRONTMATTER_RE,
    KNOWN_PREDICATES,
    MD_HEADING_RE,
    MD_LINK_RE,
    MD_TAG_RE,
    PREFIX_LIST,
    PREDICATE_RE,
    TYPE_MAP,
    _entity_sources,
    _manifest,
    _predicate_patterns,
    cross_domain_file,
    entity_files,
    get_db,
    init_schema,
)

# Re-export extract 组 (抽到 extract.py, wave 1, 保持 engine API)
from kos.ontology.extract import (  # type: ignore[no-redef]
    _auto_discover_metadata,
    extract,
)

# Re-export infer 组 (抽到 infer.py, wave 2, 保持 engine API)
from kos.ontology.infer import (  # type: ignore[no-redef]
    _reason_governance_rules,
    infer,
)

# Re-export enrich 组 (抽到 enrich.py, wave 3)
from kos.ontology.enrich import (  # type: ignore[no-redef]
    _enrich_with_local_llm,
    enrich,
)

# Re-export query 组 (抽到 query.py, wave 4)
from kos.ontology.query import (  # type: ignore[no-redef]
    _entity_graph_2hop,
    card,
    deduplicate_entities,
    entity_timeline,
    find_path,
    list_entities,
)

# Re-export ops 组 (抽到 ops.py, wave 5)
from kos.ontology.ops import (  # type: ignore[no-redef]
    _record_source_mtimes,
    check_stale,
    graph,
    rebuild,
)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

    if cmd == "rebuild":
        print(json.dumps(rebuild(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]
    elif cmd == "check-stale":
        print(json.dumps(check_stale(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]

    elif cmd == "enrich":
        print(json.dumps(enrich(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]
    elif cmd == "extract":
        print(json.dumps(extract(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]
    elif cmd == "infer":
        print(json.dumps(infer(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]
    elif cmd == "card":
        eid = sys.argv[2] if len(sys.argv) > 2 else ""
        print(json.dumps(card(eid), ensure_ascii=False, indent=2))
    elif cmd == "path":
        a = sys.argv[2] if len(sys.argv) > 2 else ""
        b = sys.argv[3] if len(sys.argv) > 3 else ""
        print(json.dumps(find_path(a, b), ensure_ascii=False, indent=2))
    elif cmd == "discover":
        print(json.dumps(discover(), ensure_ascii=False, indent=2))  # type: ignore[no-untyped-call]
    elif cmd == "graph":
        etype = None
        for i, a in enumerate(sys.argv):
            if a == "--type" and i + 1 < len(sys.argv):
                etype = sys.argv[i + 1]
        print(json.dumps(graph(etype), ensure_ascii=False, indent=2))  # type: ignore[arg-type]
    elif cmd == "list":
        etype = None
        for i, a in enumerate(sys.argv):
            if a == "--type" and i + 1 < len(sys.argv):
                etype = sys.argv[i + 1]
        print(json.dumps(list_entities(etype), ensure_ascii=False, indent=2))  # type: ignore[arg-type]
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}, ensure_ascii=False))


if __name__ == "__main__":
    main()  # type: ignore[no-untyped-call]
