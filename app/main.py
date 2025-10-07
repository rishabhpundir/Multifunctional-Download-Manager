import os

from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

load_dotenv()

WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")

app = FastAPI(title="Pi5 Media Loader")
app.mount("/", StaticFiles(directory=WEBUI_DIR, html=True), name="downloader")


# -------------- Views -----------------

@app.get("/", response_class=HTMLResponse)
def downloader_root():
    return FileResponse(os.path.join(WEBUI_DIR, "index.html"))

@app.get("/{path:path}", response_class=HTMLResponse)
def downloader_fallback(path: str):
    idx = os.path.join(WEBUI_DIR, "index.html")
    return FileResponse(idx)

