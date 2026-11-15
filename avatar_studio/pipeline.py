"""Pipeline: guion -> voz (TTS) -> subtítulos -> vídeo vertical 9:16.

Proveedores de voz:  edge (gratis, voces neuronales es-ES)  |  mock (pruebas sin red)
Proveedores de vídeo: local (imagen + zoom + subtítulos, SIN sincronía labial)
                      did   (avatar con sincronía labial vía API de D-ID)
"""
import asyncio
import base64
import os
import re
import subprocess
import time
from pathlib import Path

import httpx

W, H, FPS = 1080, 1920, 25

VOICES = {
    "elvira": ("es-ES-ElviraNeural", "Elvira (mujer, España)"),
    "ximena": ("es-ES-XimenaNeural", "Ximena (mujer, España)"),
    "alvaro": ("es-ES-AlvaroNeural", "Álvaro (hombre, España)"),
    "dalia": ("es-MX-DaliaNeural", "Dalia (mujer, México)"),
}


class PipelineError(RuntimeError):
    pass


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise PipelineError(f"{cmd[0]} falló: {p.stderr[-600:]}")


def audio_duration(path: Path) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        raise PipelineError("No se pudo leer la duración del audio")


# ---------------------------------------------------------------- voz
async def _tts_edge(text: str, voice: str, out: Path, rate: str):
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words, chunks = [], bytearray()
    async for ch in comm.stream():
        if ch["type"] == "audio":
            chunks += ch["data"]
        elif ch["type"] == "WordBoundary":
            start = ch["offset"] / 1e7
            words.append((ch["text"], start, start + ch["duration"] / 1e7))
    if not chunks:
        raise PipelineError("edge-tts no devolvió audio (¿sin red hacia Bing?)")
    out.write_bytes(bytes(chunks))
    return words


def _tts_mock(text: str, out: Path):
    """Audio sintético para pruebas sin red: tono suave, ~0.35 s por palabra."""
    toks = text.split()
    dur = max(1.0, 0.35 * len(toks))
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         f"sine=frequency=180:duration={dur}", "-c:a", "libmp3lame", str(out)])
    return [(t, i * 0.35, (i + 1) * 0.35) for i, t in enumerate(toks)]


def synthesize(text: str, voice_key: str, out: Path, rate: str = "+0%", provider: str = "edge"):
    if provider == "mock":
        return _tts_mock(text, out)
    voice = VOICES.get(voice_key, VOICES["elvira"])[0]
    return asyncio.run(_tts_edge(text, voice, out, rate))


# ---------------------------------------------------------------- subtítulos
def _ts(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def build_ass(words, out: Path, max_words: int = 3, color: str = "&H00FFFFFF&",
              accent: str = "&H0000D7FF&") -> None:
    """Subtítulos estilo reel: 2-3 palabras por línea, grandes, abajo-centro."""
    head = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {W}\nPlayResY: {H}\n\n"
        "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
        "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,"
        "Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Default,DejaVu Sans,84,{color},{accent},&H00000000&,&H80000000&,"
        "-1,0,0,0,100,100,0,0,1,6,2,2,60,60,260,1\n\n"
        "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )
    lines = []
    for i in range(0, len(words), max_words):
        grp = words[i:i + max_words]
        text = " ".join(w[0] for w in grp).upper()
        end = grp[-1][2] if i + max_words >= len(words) else words[i + max_words][1]
        lines.append(f"Dialogue: 0,{_ts(grp[0][1])},{_ts(end)},Default,,0,0,0,,{text}")
    out.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- vídeo
def _fit_image(src: Path, dst: Path) -> None:
    """Recorta/escala el avatar a 9:16 (cover) y lo guarda como PNG."""
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf",
         f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
         "-frames:v", "1", str(dst)])


def render_local(image: Path, audio: Path, ass: Path, out: Path) -> None:
    """Imagen + zoom lento + audio + subtítulos. No hay sincronía labial."""
    dur = audio_duration(audio) + 0.3
    fit = out.with_suffix(".fit.png")
    _fit_image(image, fit)
    ass_f = str(ass).replace("\\", "/").replace(":", r"\:")
    vf = (f"scale={int(W*1.2)}:{int(H*1.2)},"
          f"zoompan=z='min(1+0.0004*on,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d=1:s={W}x{H}:fps={FPS},ass='{ass_f}',format=yuv420p")
    run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS),
         "-i", str(fit), "-i", str(audio), "-t", f"{dur:.2f}", "-vf", vf,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
         "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)])
    fit.unlink(missing_ok=True)


def render_did(image: Path, audio: Path, ass: Path, out: Path) -> None:
    """Avatar con sincronía labial usando la API de D-ID (requiere DID_API_KEY)."""
    key = os.environ.get("DID_API_KEY")
    if not key:
        raise PipelineError("Falta DID_API_KEY")
    auth = {"Authorization": "Basic " + base64.b64encode(key.encode()).decode()}
    base = "https://api.d-id.com"
    with httpx.Client(timeout=120, headers=auth) as c:
        r = c.post(f"{base}/images", files={"image": (image.name, image.read_bytes())})
        r.raise_for_status()
        img_url = r.json()["url"]
        r = c.post(f"{base}/audios", files={"audio": (audio.name, audio.read_bytes())})
        r.raise_for_status()
        aud_url = r.json()["url"]
        r = c.post(f"{base}/talks", json={
            "source_url": img_url,
            "script": {"type": "audio", "audio_url": aud_url},
            "config": {"result_format": "mp4"}})
        r.raise_for_status()
        tid = r.json()["id"]
        for _ in range(120):
            time.sleep(3)
            r = c.get(f"{base}/talks/{tid}")
            r.raise_for_status()
            d = r.json()
            if d["status"] == "done":
                raw = out.with_suffix(".raw.mp4")
                raw.write_bytes(c.get(d["result_url"]).content)
                break
            if d["status"] in ("error", "rejected"):
                raise PipelineError(f"D-ID: {d.get('error') or d['status']}")
        else:
            raise PipelineError("D-ID: tiempo de espera agotado")
    # Recorte 9:16 + subtítulos sobre el resultado de D-ID
    ass_f = str(ass).replace("\\", "/").replace(":", r"\:")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-vf",
         f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},ass='{ass_f}',format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-c:a", "copy",
         "-movflags", "+faststart", str(out)])
    raw.unlink(missing_ok=True)


def generate(job_dir: Path, image: Path, text: str, voice: str, rate: str,
             tts_provider: str, video_provider: str, on_step=lambda s: None) -> Path:
    job_dir.mkdir(parents=True, exist_ok=True)
    audio, ass, out = job_dir / "voz.mp3", job_dir / "subs.ass", job_dir / "video.mp4"
    on_step("Generando voz")
    words = synthesize(text, voice, audio, rate, tts_provider)
    if not words:  # algunos motores no devuelven tiempos: reparte por duración
        toks = text.split()
        step = audio_duration(audio) / max(1, len(toks))
        words = [(t, i * step, (i + 1) * step) for i, t in enumerate(toks)]
    on_step("Creando subtítulos")
    build_ass(words, ass)
    on_step("Renderizando vídeo")
    (render_did if video_provider == "did" else render_local)(image, audio, ass, out)
    return out


def clean_text(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()
