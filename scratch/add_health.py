import re
from pathlib import Path

pkgs_dir = Path("projects/kairon/packages")

for pkg_dir in pkgs_dir.iterdir():
    if not pkg_dir.is_dir() or pkg_dir.name.startswith("."):
        continue
    pkg_name = pkg_dir.name
    mod_name = pkg_name.replace("-", "_")
    
    mcp_paths = [
        pkg_dir / "src" / mod_name / "mcp_server.py",
        pkg_dir / "src" / mod_name / "mcp_server" / "server.py",
        pkg_dir / "src" / mod_name / "server" / "mcp_server.py"
    ]
    
    for path in mcp_paths:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if "health_check" in content or "Health Endpoint" in content:
                continue
                
            # If FastMCP is used:
            if "fastmcp" in content.lower() and "@app.tool" in content:
                # find the last @app.tool and append health_check
                replacement = """
    @app.tool(name="health_check", description="Health check endpoint for mesh routing")
    def _health_check() -> dict:
        return {"status": "ok", "service": \"""" + pkg_name + """\"}

    return app"""
                content = re.sub(r'\s*return app\s*$', replacement, content)
                path.write_text(content)
                print(f"Added FastMCP health to {path}")
            # If TOOLS dict is used (e.g. eidos)
            elif "TOOLS" in content and "dict" in content:
                # just finding a way to inject it manually is safer, let's print which need manual
                print(f"Needs manual dict injection: {path}")

