import yaml
from pathlib import Path

m2_dir = Path("/Users/xiamingxing/Workspace/projects/ecos/src/ecos/ssot/mof/m2")

for f in m2_dir.glob("*.yaml"):
    try:
        with open(f, "r") as file:
            data = yaml.safe_load(file)
            
        mtype = data.get("m2_type")
        if not mtype:
            continue
            
        # find the actual key that contains the schema (which might be snake_case)
        # It's usually the only other key besides m2_type, version, created, etc.
        schema_key = None
        for k in data.keys():
            if k not in ["m2_type", "version", "created"] and isinstance(data[k], dict):
                schema_key = k
                break
                
        if schema_key and schema_key != mtype:
            print(f"Fixing {f.name}: renaming key '{schema_key}' to '{mtype}'")
            # We must do string replacement to preserve formatting and comments
            with open(f, "r") as file:
                content = file.read()
                
            import re
            # Replace ^schema_key: with ^mtype:
            content = re.sub(rf'^{schema_key}:', f'{mtype}:', content, flags=re.MULTILINE)
            
            with open(f, "w") as file:
                file.write(content)
                
    except Exception as e:
        print(f"Failed {f.name}: {e}")
