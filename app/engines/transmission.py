import aiohttp
import os
import base64

URL = os.getenv("TRANSMISSION_URL")
U = os.getenv("TRANSMISSION_USER")
P = os.getenv("TRANSMISSION_PASS")


async def _call(session, method, arguments=None):
    arguments = arguments or {}
    headers = {}
    # First call may need X-Transmission-Session-Id negotiation
    async with session.post(
        URL,
        json={"method": method, "arguments": arguments},
        auth=aiohttp.BasicAuth(U, P) if U or P else None,
    ) as r:
        if r.status == 409:
            sid = r.headers["X-Transmission-Session-Id"]
            headers["X-Transmission-Session-Id"] = sid
    async with session.post(
        URL,
        json={"method": method, "arguments": arguments},
        headers=headers,
        auth=aiohttp.BasicAuth(U, P) if U or P else None,
    ) as r:
        return await r.json()


async def add_magnet(magnet: str, dirpath: str) -> str:
    async with aiohttp.ClientSession() as s:
        j = await _call(s, "torrent-add", {"filename": magnet, "download-dir": dirpath})
        t = j["arguments"].get("torrent-added") or j["arguments"].get(
            "torrent-duplicate"
        )
        return t["hashString"]


async def add_torrent_bytes(torrent_bytes: bytes, dirpath: str) -> str:
    """
    Add a .torrent using base64 'metainfo'. Returns hashString.
    """
    meta = base64.b64encode(torrent_bytes).decode("ascii")
    async with aiohttp.ClientSession() as s:
        j = await _call(s, "torrent-add", {"metainfo": meta, "download-dir": dirpath})
        t = j["arguments"].get("torrent-added") or j["arguments"].get(
            "torrent-duplicate"
        )
        return t["hashString"]


async def get_status(t_hash: str):
    async with aiohttp.ClientSession() as s:
        j = await _call(
            s,
            "torrent-get",
            {
                "ids": [t_hash],
                "fields": ["percentDone", "isFinished", "downloadDir", "name"],
            },
        )
        arr = j["arguments"]["torrents"]
        return arr[0] if arr else None


