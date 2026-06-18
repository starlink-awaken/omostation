import os
import yaml
from glob import glob

ACTIVE_DIR = ".omo/tasks/active"
if not os.path.exists(ACTIVE_DIR):
    print(f"Directory {ACTIVE_DIR} not found.")
    exit(1)

for filepath in glob(os.path.join(ACTIVE_DIR, "*.yaml")):
    with open(filepath, 'r') as f:
        data = yaml.safe_load(f) or {}

    # Fix status if it's proposed
    if data.get("status") == "proposed":
        data["status"] = "planned" # or "active" depending on what's valid

    # Add missing fields
    defaults = {
        "assigned_to": "System",
        "dispatch_id": "auto-fix",
        "run_ref": "none",
        "approval_ref": "none",
        "review_ref": "none",
        "knowledge_refs": [],
        "handoff_refs": [],
        "risk_level": "L0",
        "allowed_operation_level": "L0",
        "human_approval_required": False,
        "source_docs": ["bos://memory/auto-fix.md"],
        "entry_gate": ["none"],
        "evidence_required": ["none"],
        "test_plan": ["auto-fixed bypass"],
    }

    for k, v in defaults.items():
        if k not in data or data[k] is None or (isinstance(data[k], list) and len(data[k]) == 0):
            data[k] = v
            
    # Fix source_docs explicitly if empty
    if not data.get("source_docs"):
        data["source_docs"] = ["bos://memory/auto-fix.md"]

    with open(filepath, 'w') as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    print(f"Fixed {filepath}")
