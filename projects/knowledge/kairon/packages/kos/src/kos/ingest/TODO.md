---
title: TODO
type: doc
---

{
  "steps": [
    {"id": "create-parsers-pkg", "description": "Create kos/ingest/parsers/__init__.py"},
    {"id": "create-wechat-parser", "description": "Migrate parse_wechat.py → kos/ingest/parsers/wechat.py"},
    {"id": "create-notes-parser", "description": "Migrate parse_notes.py → kos/ingest/parsers/notes.py"},
    {"id": "create-bookmarks-parser", "description": "Migrate parse_bookmarks.py → kos/ingest/parsers/bookmarks.py"},
    {"id": "create-ingest-module", "description": "Migrate ingest_to_factgraph.py → kos/ingest/ingest.py (use kos.perception.fact_injector)"},
    {"id": "create-tracker", "description": "Migrate tracker.py → kos/ingest/tracker.py"},
    {"id": "create-pipeline", "description": "Migrate run_pipeline.py → kos/ingest/pipeline.py"},
    {"id": "create-test-file", "description": "Migrate test_parsers.py → kos/tests/test_parsers_ingest.py"},
    {"id": "verify", "description": "Run python3 -m py_compile on all migrated files"}
  ]
}
