from pathlib import Path

def discover_backends():
    backends = []
    pkgs_dir = Path("projects/kairon/packages")
    
    for pkg_dir in pkgs_dir.iterdir():
        if not pkg_dir.is_dir() or pkg_dir.name.startswith("."):
            continue
            
        pkg_name = pkg_dir.name
        if pkg_name == "agora":
            continue
            
        mod_name = pkg_name.replace("-", "_")
        
        mcp_paths = [
            pkg_dir / "src" / mod_name / "mcp_server.py",
            pkg_dir / "src" / mod_name / "mcp_server" / "server.py",
            pkg_dir / "src" / mod_name / "server" / "mcp_server.py"
        ]
        
        mcp_module = None
        for path in mcp_paths:
            if path.exists():
                if "mcp_server/server.py" in str(path):
                    mcp_module = f"{mod_name}.mcp_server.server"
                elif "server/mcp_server.py" in str(path):
                    mcp_module = f"{mod_name}.server.mcp_server"
                else:
                    mcp_module = f"{mod_name}.mcp_server"
                break
                
        if mcp_module:
            backends.append({
                "name": pkg_name,
                "command": "uv",
                "args": ["run", "--package", pkg_name, "python", "-m", mcp_module],
            })
            
    return backends

import pprint
pprint.pprint(discover_backends())
