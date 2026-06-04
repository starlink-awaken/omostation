import os
import tomllib
from pathlib import Path

def discover_mcp_backends():
    packages_dir = Path("projects/kairon/packages")
    backends = []
    for pkg_dir in packages_dir.iterdir():
        if not pkg_dir.is_dir() or not (pkg_dir / "pyproject.toml").exists():
            continue
        
        try:
            with open(pkg_dir / "pyproject.toml", "rb") as f:
                config = tomllib.load(f)
            
            pkg_name = config.get("project", {}).get("name")
            if not pkg_name: continue

            # Search for mcp_server.py or server.py
            mcp_module = None
            for root, _, files in os.walk(pkg_dir):
                if "test" in root: continue
                if "mcp_server.py" in files:
                    mcp_module = "mcp_server"
                    file = "mcp_server.py"
                elif "server.py" in files and "mcp" in root:
                    mcp_module = "server"
                    file = "server.py"
                elif "server.py" in files and "standalone" in root:
                    mcp_module = "server"
                    file = "server.py"
                else:
                    continue

                rel_path = Path(root).relative_to(pkg_dir)
                parts = list(rel_path.parts)
                if parts and parts[0] == "src":
                    parts = parts[1:]
                mod_name = ".".join(parts + [mcp_module])
                
                backends.append({
                    "name": pkg_name,
                    "mcp_endpoint": "",
                    "command": "uv",
                    "args": ["run", "--package", pkg_name, "python", "-m", mod_name]
                })
                break

        except Exception as e:
            print(f"Error {pkg_dir}: {e}")
            pass
    return backends

if __name__ == "__main__":
    for b in discover_mcp_backends():
        print(b["name"], b["args"][-1])
