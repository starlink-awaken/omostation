import re
from pathlib import Path

pkgs_dir = Path("projects/kairon/packages")
l1_pkgs = {"kos", "ontoderive", "metaos", "ssot", "eidos", "minerva", "sophia", "kronos", "llm_gateway", "agent_runtime"}

violations = []

for pkg_dir in pkgs_dir.iterdir():
    if not pkg_dir.is_dir() or pkg_dir.name.startswith("."):
        continue
    pkg_name_underscored = pkg_dir.name.replace("-", "_")
    
    for py_file in pkg_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
            
        for i, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if not (line.startswith("import ") or line.startswith("from ")):
                continue
                
            for l1 in l1_pkgs:
                if l1 == pkg_name_underscored:
                    continue # self import
                if re.search(rf"\bimport\s+{l1}\b", line) or re.search(rf"\bfrom\s+{l1}\b", line) or re.search(rf"\bfrom\s+{l1}\.", line):
                    violations.append(f"{py_file}:{i}: {line}")

for v in violations:
    print(v)
