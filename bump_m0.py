import yaml
from datetime import datetime, timezone
from pathlib import Path

m0_file = Path("/Users/xiamingxing/Workspace/projects/ecos/src/ecos/ssot/mof/m0/snapshot.yaml")

if m0_file.exists():
    with open(m0_file, "r") as f:
        m0 = yaml.safe_load(f)

    m0["generated_at"] = datetime.now(timezone.utc).isoformat()
    m0["daemon"]["cycles"] += 1

    with open(m0_file, "w") as f:
        yaml.dump(m0, f, default_flow_style=False)
    print("M0 snapshot bumped")
else:
    print("M0 snapshot not found at", m0_file)
