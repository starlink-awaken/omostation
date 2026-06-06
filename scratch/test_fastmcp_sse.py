import sys
import asyncio
from fastmcp import FastMCP

mcp = FastMCP("test")

@mcp.tool()
def hello() -> str:
    return "world"

print(dir(mcp))

