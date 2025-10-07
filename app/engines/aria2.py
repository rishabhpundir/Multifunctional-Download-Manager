import aiohttp
import os
import base64
from dotenv import load_dotenv

load_dotenv()

ARIA2 = os.getenv("ARIA2_RPC")
SECRET = os.getenv("ARIA2_SECRET")


def _payload(method, params):
    p = ["token:" + SECRET] if SECRET else []
    p.extend(params)
    return {"jsonrpc": "2.0", "id": "pi5", "method": method, "params": p}


async def add_uri(url: str, dirpath: str) -> str:
    """
    Works for HTTP(S) links and magnet: URIs. Returns GID.
    """
    async with aiohttp.ClientSession() as s:
        data = _payload("aria2.addUri", [[url], {"dir": dirpath}])
        async with s.post(ARIA2, json=data) as r:
            j = await r.json()
            return j["result"]  # GID


async def add_torrent_bytes(torrent_bytes: bytes, dirpath: str) -> str:
    """
    Upload a .torrent file to aria2 via RPC. Returns GID.
    """
    b64 = base64.b64encode(torrent_bytes).decode("ascii")
    opts = {"dir": dirpath}
    async with aiohttp.ClientSession() as s:
        data = _payload("aria2.addTorrent", [b64, [], opts])
        async with s.post(ARIA2, json=data) as r:
            j = await r.json()
            return j["result"]  # GID


async def tell_status(gid: str):
    """
    Returns aria2 status JSON.
    """
    async with aiohttp.ClientSession() as s:
        data = _payload(
            "aria2.tellStatus",
            [gid, ["status", "completedLength", "totalLength", "files","dir","downloadSpeed"]],
        )
        async with s.post(ARIA2, json=data) as r:
            return await r.json()


async def pause(gid: str):
    async with aiohttp.ClientSession() as s:
        data = _payload("aria2.pause", [gid])
        async with s.post(ARIA2, json=data) as r:
            return await r.json()


async def unpause(gid: str):
    async with aiohttp.ClientSession() as s:
        data = _payload("aria2.unpause", [gid])
        async with s.post(ARIA2, json=data) as r:
            return await r.json()


async def remove(gid: str):
    async with aiohttp.ClientSession() as s:
        data = _payload("aria2.remove", [gid])
        async with s.post(ARIA2, json=data) as r:
            return await r.json()

