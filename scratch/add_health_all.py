import re
from pathlib import Path

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
    
    for path in mcp_paths:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if 'name="health_check"' in content or '"health_check"' in content:
                print(f"Skipping {path}, already has health_check")
                continue
                
            # Detect variable name
            match = re.search(r'^([a-zA-Z0-9_]+)\s*=\s*FastMCP\(', content, re.MULTILINE)
            if match:
                var_name = match.group(1)
                replacement = f"""
@{var_name}.tool(name="health_check", description="Health check endpoint for mesh routing")
def _health_check() -> dict:
    return {{"status": "ok", "service": "{pkg_name}"}}
"""
                # find if there's if __name__ == "__main__", put it before that
                if "if __name__" in content:
                    content = content.replace('if __name__ == "__main__":', replacement + '\nif __name__ == "__main__":')
                else:
                    content += "\n" + replacement
                path.write_text(content)
                print(f"Added FastMCP health (var {var_name}) to {path}")
            elif "TOOLS" in content and "dict" in content:
                print(f"Needs manual dict injection: {path}")

