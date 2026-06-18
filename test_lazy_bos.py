import asyncio
import os
os.environ["AGORA_BOS_ONLY"] = "1"

async def main():
    import sys
    sys.path.insert(0, "./src")
    from agora.server.mcp import _init_proxy
    await _init_proxy()
    
    print("\nCalling resolve_bos_uri")
    try:
        
        # we can just call the underlying function
        from agora.server.tools_bos import resolve_bos_uri
        res = await resolve_bos_uri("bos://analysis/minerva/research_now", "{}")
        print(f"\nResult: {res}")
    except Exception as e:
        print(f"\nError: {e}")

asyncio.run(main())
