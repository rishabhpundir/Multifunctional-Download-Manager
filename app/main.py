import os
import asyncio
import glob
from pathlib import Path
from fastapi import (FastAPI, UploadFile, File, Form, Response,
                     WebSocket, WebSocketDisconnect, BackgroundTasks)
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, field_validator
from .db import init_db, Session
from .models import Download
from .engines import aria2, transmission
from .postprocess import move_and_enrich
from . import jellyfin
from dotenv import load_dotenv

load_dotenv()

DOWNLOADS_ROOT = os.getenv("DOWNLOADS_ROOT")
MEDIA_ROOT = os.getenv("MEDIA_ROOT")

app = FastAPI(title="Pi5 Media Loader")


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("app/static/index.html")


class AddPayload(BaseModel):
    source: str         # magnet:... or http(s)://...
    engine: str         # "aria2" | "transmission"
    kind: str           # "movie" | "tv"

    @field_validator("engine")
    @classmethod
    def validate_engine(cls, v):
        if v not in {"aria2", "transmission"}:
            raise ValueError("engine must be 'aria2' or 'transmission'")
        return v

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v):
        if v not in {"movies", "tvshows"}:
            raise ValueError("kind must be 'movie' or 'tv'")
        return v


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.post("/api/add")
async def add_job(p: AddPayload, bg: BackgroundTasks):
    """
    Enqueue a magnet or direct HTTP(S) download.
    - Default: use aria2 for both magnets and HTTP(S).
    - If engine=transmission and source is magnet, use Transmission instead.
    """
    try:
        target_dir = os.path.join(DOWNLOADS_ROOT, p.kind)
        os.makedirs(target_dir, exist_ok=True)

        async with Session() as s:
            d = Download(source=p.source, engine=p.engine, kind=p.kind, status="starting")
            s.add(d)
            await s.commit()
            await s.refresh(d)

        bg.add_task(run_download, d.id, p.source, p.engine, target_dir, p.kind, is_file=False, file_bytes=None)
        return {"ok": True, "id": d.id}
    except Exception as e:
        print(f"Error occured while adding link : \n{e}")
        return {"ok": False, "id": str(e)}


@app.post("/api/add-torrent-file")
async def add_torrent_file(
    bg: BackgroundTasks,
    engine: str = Form("aria2"),
    kind: str = Form("movie"),
    torrent: UploadFile = File(...),
):
    """
    Upload a .torrent file and enqueue it with the chosen engine.
    """
    if engine not in {"aria2", "transmission"}:
        return {"ok": False, "error": "engine must be 'aria2' or 'transmission'"}
    if kind not in {"movie", "tv"}:
        return {"ok": False, "error": "kind must be 'movie' or 'tv'"}

    target_dir = os.path.join(DOWNLOADS_ROOT, kind)
    os.makedirs(target_dir, exist_ok=True)

    data = await torrent.read()

    async with Session() as s:
        d = Download(
            source=torrent.filename,
            engine=engine,
            kind=kind,
            status="starting",
            note="torrent-file",
        )
        s.add(d)
        await s.commit()
        await s.refresh(d)

    bg.add_task(run_download, d.id, torrent.filename, engine, target_dir, kind, is_file=True, file_bytes=data)
    return {"ok": True, "id": d.id}


async def run_download(did, source, engine, target_dir, kind, is_file: bool, file_bytes: bytes | None):
    """
    Core runner. Uses aria2 for everything by default; Transmission only when chosen.
    """
    engine_id = None

    # Queue into the selected engine
    if is_file:
        # .torrent upload path
        if engine == "aria2":
            engine_id = await aria2.add_torrent_bytes(file_bytes, target_dir)
        else:
            engine_id = await transmission.add_torrent_bytes(file_bytes, target_dir)
    else:
        # magnet or HTTP(S)
        if source.startswith("magnet:"):
            if engine == "transmission":
                engine_id = await transmission.add_magnet(source, target_dir)
            else:
                engine_id = await aria2.add_uri(source, target_dir)
        else:
            # direct link -> aria2 (even if engine=transmission was selected by mistake)
            engine_id = await aria2.add_uri(source, target_dir)

    # Persist engine_id
    async with Session() as s:
        d = await s.get(Download, did)
        d.engine_id = engine_id
        await s.commit()

    # Poll until complete
    while True:
        prog = 0.0
        done = False
        save_dir = target_dir

        if engine == "transmission" and (source.startswith("magnet:") or is_file):
            st = await transmission.get_status(engine_id)
            if st:
                prog = float(st.get("percentDone", 0.0)) * 100.0
                save_dir = st.get("downloadDir") or save_dir
                done = bool(st.get("isFinished"))
        else:
            # aria2 path for magnets and HTTP(S)
            st = await aria2.tell_status(engine_id)
            r = st.get("result", {}) if isinstance(st, dict) else {}
            tl = int(r.get("totalLength") or 1)
            cl = int(r.get("completedLength") or 0)
            prog = (cl * 100.0) / tl if tl else 0.0
            state = r.get("status")
            done = state in ("complete", "seeding")
            save_dir = r.get("dir") or save_dir

        async with Session() as s:
            d = await s.get(Download, did)
            d.progress = round(prog, 2)
            d.status = (
                "seeding" if done and (source.startswith("magnet:") or is_file) else
                ("downloading" if not done else "completed")
            )
            d.save_path = save_dir
            await s.commit()

        if done:
            break
        await asyncio.sleep(2)

    # Post-process: pick largest video file and enrich
    candidates = sorted(
        glob.glob(os.path.join(save_dir, "**/*.mkv"), recursive=True)
        + glob.glob(os.path.join(save_dir, "**/*.mp4"), recursive=True),
        key=lambda p: os.path.getsize(p),
        reverse=True,
    )
    if candidates:
        final_folder = move_and_enrich(candidates[0], kind)
        result = await jellyfin.refresh_library()
        print("Library refreshed!") if result else "Refreshed failed!"


@app.get("/api/downloads")
async def list_downloads():
    async with Session() as s:
        rows = (await s.execute(__import__("sqlalchemy").select(Download))).scalars().all()
        return [
            dict(
                id=r.id,
                source=r.source,
                engine=r.engine,
                kind=r.kind,
                status=r.status,
                progress=r.progress,
                save_path=r.save_path,
            )
            for r in rows
        ]


@app.delete("/api/content/{did}")
async def delete_content(did: int):
    async with Session() as s:
        d = await s.get(Download, did)
        if not d:
            return {"ok": False, "error": "not found"}

        # try removing organized folder if exists; else the original save dir
        import shutil
        if d.save_path and os.path.isdir(d.save_path):
            shutil.rmtree(d.save_path, ignore_errors=True)

        d.status = "deleted"
        await s.commit()

    result = await jellyfin.refresh_library()
    return {"ok": result}


# Simple broadcast of the queue every 2s
clients = set()


@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await asyncio.sleep(2)
            items = []
            async with Session() as s:
                rows = (await s.execute(__import__("sqlalchemy").select(Download))).scalars().all()

            for r in rows:
                speed_bps = 0
                try:
                    if r.engine == "transmission" and (str(r.source).startswith("magnet:") or (r.note or "") == "torrent-file"):
                        st = await transmission.get_status(r.engine_id)
                        if st:
                            speed_bps = int(st.get("rateDownload") or 0)
                    else:
                        # aria2 for everything else (magnets, http/https, torrent file via aria2)
                        st = await aria2.tell_status(r.engine_id)
                        res = st.get("result", {}) if isinstance(st, dict) else {}
                        speed_bps = int(res.get("downloadSpeed") or 0)
                except Exception:
                    speed_bps = 0
                    
                # display name and timestamp
                display_name = ""
                added_ts = getattr(r, "created_at", None)

                try:
                    if r.engine == "transmission" and (str(r.source).startswith("magnet:") or (r.note or "") == "torrent-file"):
                        if st:
                            display_name = (st.get("name") or "").strip()
                    else:
                        # aria2
                        if isinstance(st, dict):
                            res = st.get("result", {})
                            files = res.get("files") or []
                            if files:
                                p = (files[0].get("path") or "").strip()
                                if p:
                                    display_name = os.path.basename(p)
                except Exception:
                    pass

                if not display_name:
                    # fallback to the source itself
                    display_name = os.path.basename(str(r.source)) or str(r.source)

                items.append({
                    "id": r.id,
                    "name": display_name,
                    "progress": r.progress,
                    "status": r.status,
                    "engine": r.engine,
                    "kind": r.kind,
                    "speed_bps": speed_bps,
                    "created_at": (added_ts.isoformat() if added_ts else None),
                })
            await ws.send_json(items)
    except WebSocketDisconnect:
        return
    
    

