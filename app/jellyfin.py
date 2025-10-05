import aiohttp, os

BASE = os.getenv("JELLYFIN_URL")
TOKEN = os.getenv("JELLYFIN_TOKEN")
HEAD = {"X-MediaBrowser-Token": TOKEN}

async def refresh_library():
    # Some builds accept GET, others expect POST with empty body.
    async with aiohttp.ClientSession() as s:
        for method in ("get","post"):
            req = getattr(s, method)
            async with req(f"{BASE}/Library/Refresh", headers=HEAD) as r:
                if r.status in (200,204,202): return True
    return False


