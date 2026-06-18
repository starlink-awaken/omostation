import os
import yaml

filepath = ".omo/tasks/active/OPC-P15-KAI-02.yaml"
with open(filepath, 'r') as f:
    data = yaml.safe_load(f)

data["evidence_paths"] = ["AGENTS.md"]

with open(filepath, 'w') as f:
    yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
