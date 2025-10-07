import os
import aiohttp

from fastapi import Request
from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

load_dotenv()

# -------------- Config -----------------
WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")
ARIA2 = os.getenv("ARIA2_RPC", "http://127.0.0.1:6800/jsonrpc")
ARIA2_SECRET = os.getenv("ARIA2_SECRET", "")

app = FastAPI(title="Pi5 Media Loader")
app.mount("/downloader", StaticFiles(directory=WEBUI_DIR, html=True), name="downloader")


# -------------- Views -----------------
@app.get("/downloader/", response_class=HTMLResponse)
def downloader_root():
    return FileResponse(os.path.join(WEBUI_DIR, "index.html"))

@app.get("/downloader/{path:path}", response_class=HTMLResponse)
def downloader_fallback(path: str):
    return FileResponse(os.path.join(WEBUI_DIR, "index.html"))

@app.post("/jsonrpc")
async def aria2_jsonrpc_proxy(req: Request):
    """
    Proxy for aria2 JSON-RPC.
    - Injects token for single calls, batch arrays, and system.multicall/aria2.batch.
    """
    payload = await req.json()

    def inject_into_params(params):
        # params is expected to be a list for aria2.* methods
        if isinstance(params, list):
            # special: system.multicall and aria2.batch contain a list of calls
            if len(params) >= 1 and isinstance(params[0], list):
                # each element is a dict: {"methodName": "...", "params": [...]}
                calls = params[0]
                out_calls = []
                for c in calls:
                    if isinstance(c, dict):
                        p = c.get("params", [])
                        if not (p and isinstance(p, list) and isinstance(p[0], str) and p[0].startswith("token:")):
                            p = [f"token:{ARIA2_SECRET}"] + (p if isinstance(p, list) else [])
                        c = {**c, "params": p}
                    out_calls.append(c)
                return [out_calls]
            else:
                # normal aria2.* call
                if not (params and isinstance(params[0], str) and params[0].startswith("token:")):
                    return [f"token:{ARIA2_SECRET}"] + params
        return params

    def inject_token(obj):
        if isinstance(obj, dict):
            m = obj.get("method")
            p = obj.get("params", [])
            if m in ("system.multicall", "aria2.batch"):
                obj["params"] = inject_into_params(p)
            else:
                obj["params"] = inject_into_params(p)
            return obj
        return obj

    if isinstance(payload, list):
        payload = [inject_token(p) for p in payload]
    else:
        payload = inject_token(payload)

    async with aiohttp.ClientSession() as s:
        async with s.post(ARIA2, json=payload) as r:
            data = await r.json(content_type=None)
            return JSONResponse(data, status_code=r.status)


