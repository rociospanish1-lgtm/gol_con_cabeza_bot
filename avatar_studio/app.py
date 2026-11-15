"""Avatar Studio: clon sencillo de un generador de vídeos con avatar hablando."""
import base64
import hmac
import os
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

import pipeline as P

DATA = Path(os.environ.get("DATA_DIR", Path(__file__).parent / "data"))
DATA.mkdir(parents=True, exist_ok=True)
TTS = os.environ.get("TTS_PROVIDER", "edge")          # edge | mock
VIDEO = os.environ.get("VIDEO_PROVIDER", "did" if os.environ.get("DID_API_KEY") else "local")
MAX_CHARS, MAX_IMG = 1500, 8 * 1024 * 1024

app = FastAPI(title="Avatar Studio")
PASSWORD = os.environ.get("APP_PASSWORD", "")


@app.middleware("http")
async def basic_auth(request, call_next):
    """Si APP_PASSWORD está definida, exige contraseña (usuario: cualquiera)."""
    if PASSWORD:
        ok = False
        h = request.headers.get("authorization", "")
        if h.lower().startswith("basic "):
            try:
                pwd = base64.b64decode(h[6:]).decode().partition(":")[2]
                ok = hmac.compare_digest(pwd, PASSWORD)
            except Exception:  # noqa: BLE001
                pass
        if not ok:
            return Response("Acceso restringido", 401,
                            headers={"WWW-Authenticate": 'Basic realm="Avatar Studio"'})
    return await call_next(request)

JOBS: dict[str, dict] = {}


@app.get("/api/config")
def config():
    return {"voices": {k: v[1] for k, v in P.VOICES.items()}, "video_provider": VIDEO,
            "lipsync": VIDEO == "did", "max_chars": MAX_CHARS}


def _work(jid: str, image: Path, text: str, voice: str, rate: str):
    job = JOBS[jid]
    try:
        out = P.generate(DATA / jid, image, text, voice, rate, TTS, VIDEO,
                         on_step=lambda s: job.update(step=s))
        job.update(status="done", step="Listo", file=str(out))
    except Exception as e:  # noqa: BLE001
        job.update(status="error", step="Error", error=str(e))


@app.post("/api/videos")
async def create(image: UploadFile = File(...), text: str = Form(...),
                 voice: str = Form("elvira"), speed: int = Form(0)):
    text = P.clean_text(text)
    if not text:
        raise HTTPException(400, "El guion está vacío")
    if len(text) > MAX_CHARS:
        raise HTTPException(400, f"Máximo {MAX_CHARS} caracteres")
    if voice not in P.VOICES:
        raise HTTPException(400, "Voz no válida")
    if not (image.content_type or "").startswith("image/"):
        raise HTTPException(400, "El avatar debe ser una imagen")
    raw = await image.read()
    if len(raw) > MAX_IMG:
        raise HTTPException(400, "Imagen demasiado grande (máx. 8 MB)")
    jid = uuid.uuid4().hex[:12]
    (DATA / jid).mkdir(parents=True)
    img = DATA / jid / "avatar.img"
    img.write_bytes(raw)
    rate = f"{max(-30, min(30, speed)):+d}%"
    JOBS[jid] = {"status": "running", "step": "En cola"}
    threading.Thread(target=_work, args=(jid, img, text, voice, rate), daemon=True).start()
    return {"id": jid}


@app.get("/api/videos/{jid}")
def status(jid: str):
    job = JOBS.get(jid)
    if not job:
        raise HTTPException(404, "No existe")
    return {k: v for k, v in job.items() if k != "file"} | (
        {"url": f"/api/videos/{jid}/file"} if job["status"] == "done" else {})


@app.get("/api/videos/{jid}/file")
def file(jid: str):
    job = JOBS.get(jid)
    if not job or job["status"] != "done":
        raise HTTPException(404, "No disponible")
    return FileResponse(job["file"], media_type="video/mp4", filename=f"avatar-{jid}.mp4")


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
