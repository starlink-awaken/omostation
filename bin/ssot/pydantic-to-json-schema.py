#!/usr/bin/env python3
"""Pydantic to JSON Schema converter — migrate omo_io_schemas to unified registry.

Usage:
    cd projects/omo && uv run python ../../bin/ssot/pydantic-to-json-schema.py
"""
import json
import sys
from pathlib import Path

# Add omo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "projects" / "omo" / "src"))

from omo.omo_io_schemas import (
    OmoAuditRecord,
    OmoBosMetricsRecord,
    OmoSyncRecord,
    OmoAlertRecord,
    OmoEventRecord,
    OmoHistoryRecord,
    OmoTrailRecord,
    OmoHealthRecord,
)

SCHEMAS = {
    "omo-audit-record": OmoAuditRecord,
    "omo-bos-metrics-record": OmoBosMetricsRecord,
    "omo-sync-record": OmoSyncRecord,
    "omo-alert-record": OmoAlertRecord,
    "omo-event-record": OmoEventRecord,
    "omo-history-record": OmoHistoryRecord,
    "omo-trail-record": OmoTrailRecord,
    "omo-health-record": OmoHealthRecord,
}

OUTPUT_DIR = Path(__file__).resolve().parents[1] / ".omo" / "standards" / "content-schemas" / "omo"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in SCHEMAS.items():
        schema = model.model_json_schema()
        output_file = OUTPUT_DIR / f"{name}.schema.json"
        with open(output_file, "w") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)
        print(f"  ✅ {name}: {output_file}")
    print(f"\nMigrated {len(SCHEMAS)} Pydantic models to JSON Schema")


if __name__ == "__main__":
    main()
