from pathlib import Path

# Iris
p = Path("projects/kairon/packages/iris/src/iris/mcp_server.py")
if p.exists():
    content = p.read_text()
    if "health_check" not in content:
        content = content.replace(
            'TOOLS: dict[str, dict[str, Any]] = {',
            'TOOLS: dict[str, dict[str, Any]] = {\n    "health_check": {"func": lambda p: {"status": "ok", "service": "iris"}, "description": "Health check", "input_schema": {"type": "object", "properties": {}}},'
        )
        p.write_text(content)
        print("Added to iris")

# MetaOS
p = Path("projects/kairon/packages/metaos/src/metaos/mcp_server.py")
if p.exists():
    content = p.read_text()
    if "health_check" not in content:
        content = content.replace(
            'TOOLS = {',
            'TOOLS = {\n    "health_check": {"func": lambda p: {"status": "ok", "service": "metaos"}, "description": "Health check", "input_schema": {"type": "object", "properties": {}}},'
        )
        p.write_text(content)
        print("Added to metaos")

# cron-service
p = Path("projects/kairon/packages/cron-service/src/cron_service/mcp_server.py")
if p.exists():
    content = p.read_text()
    if "health_check" not in content:
        if "FastMCP" in content:
            replacement = """
@mcp.tool(name="health_check", description="Health check endpoint for mesh routing")
def _health_check() -> dict:
    return {"status": "ok", "service": "cron-service"}
"""
            content = content.replace('def start', replacement + '\ndef start')
            p.write_text(content)
            print("Added to cron-service")
            
