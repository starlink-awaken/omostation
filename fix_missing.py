import re
from pathlib import Path

files = ["quota_definition.yaml", "routing_policy.yaml", "availability_check.yaml"]
base_dir = Path("/Users/xiamingxing/Workspace/projects/ecos/src/ecos/ssot/mof/m2")

for fname in files:
    fpath = base_dir / fname
    with open(fpath, "r") as f:
        content = f.read()
    
    if "m3_parent:" not in content:
        key = fname.replace(".yaml", "")
        # inject m3_parent: GovernanceElement right after the key:
        content = re.sub(rf'^({key}:)', r'\1\n  m3_parent: GovernanceElement', content, flags=re.MULTILINE)
        
        with open(fpath, "w") as f:
            f.write(content)
        print(f"Injected into {fname}")
