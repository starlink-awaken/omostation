from pathlib import Path

m2_dir = Path("/Users/xiamingxing/Workspace/projects/ecos/src/ecos/ssot/mof/m2")

targets = [
    "governance_event.yaml",
    "quota_definition.yaml",
    "trigger.yaml",
    "routing_policy.yaml",
    "constraint_mgmt.yaml",
    "omo_task.yaml",
    "availability_check.yaml",
    "governance_policy.yaml",
    "governance_check.yaml"
]

parent_map = {
    "governance_event.yaml": "GovernanceElement",
    "quota_definition.yaml": "GovernanceElement",
    "trigger.yaml": "BehavioralElement",
    "routing_policy.yaml": "GovernanceElement",
    "constraint_mgmt.yaml": "GovernanceElement",
    "omo_task.yaml": "GovernanceElement",
    "availability_check.yaml": "GovernanceElement",
    "governance_policy.yaml": "GovernanceElement",
    "governance_check.yaml": "GovernanceElement"
}

for t in targets:
    f = m2_dir / t
    if f.exists():
        with open(f, "r") as file:
            content = file.read()
        
        # We can just replace any m3_parent: line with the new one
        import re
        content = re.sub(r'm3_parent:\s*.*', f'm3_parent: {parent_map[t]}', content)
        
        with open(f, "w") as file:
            file.write(content)
        print(f"Fixed {t}")
    else:
        print(f"Not found: {t}")
