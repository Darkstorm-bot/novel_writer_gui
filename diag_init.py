import asyncio
import traceback
from novelforge_v2 import NovelForge

async def run_init():
    try:
        forge = NovelForge(
            head_endpoint="http://localhost:1234/v1",
            critic_endpoint="http://localhost:1235/v1",
            mcp_servers=[
                "mempalace_mcp_server.py",
                "crawl4ai_mcp_server.py",
                "filesystem_mcp_server.py"
            ]
        )
        ok = await forge.initialize()
        print('initialize returned:', ok)
    except Exception as e:
        print('EXCEPTION in diag_init:')
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(run_init())
