import asyncio
from src.agora.mcp.bos_resolver import resolve_bos_uri
import pprint
r = asyncio.run(resolve_bos_uri("bos://governance/omo/inspect", **{}))
pprint.pprint(r)
