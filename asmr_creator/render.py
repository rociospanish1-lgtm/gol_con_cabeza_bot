"""Ensambla audio + vídeo con ffmpeg."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import audio as A
from .presets import FORMATOS, PRESETS, parsear_capas
from .visuals import ESTILOS, Imagen

FUENTES = [
    "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
    "/usr/share/fonts/truetype/inter/Inter-SemiBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

EXT_VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
EXT_IMAGEN = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class Config:
    salida: str = "asmr.mp4"
    preset: str = "clinica"
    duracion: float = 30.0
    formato: str = "vertical"
    fps: int = 30
    capas: Optional[str] = None          # sobrescribe las del preset
    estilo: Optional[str] = None         # bokeh | seda | lluvia | brasas
    paleta: Optional[str] = None         # nombre o "#hex,#hex,#hex"
    fondo: Optional[str] = None          # foto o vídeo propio
    voz: Optional[str] = None            # audio de voz/susurro propio
    volumen_voz: float = 1.0
    texto: Optional[str] = None          # gancho en pantalla
    texto_seg: float = 0.0               # 0 = todo el vídeo
    marca: Optional[str] = None          # @usuario o web, abajo
    fuente: Optional[str] = None
    semilla: int = 7
    bucle: bool = True
    portada: bool = True
    calidad: int = 20                    # CRF x264 (menor = mejor)
    lufs: float = -16.0
    solo_audio: bool = False
    progreso: Optional[Callable[[str], None]] = field(default=None, repr=False)


def _log(cfg: Config, msg: str) -> None:
    (cfg.progreso or print)(msg)


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("No se encuentra ffmpeg. Instálalo: https://ffmpeg.org/download.html "
                           "(macOS: brew install ffmpeg · Ubuntu: sudo apt install ffmpeg)")
    return exe


def _fuente(cfg: Config) -> str:
    for f in ([cfg.fuente] if cfg.fuente else []) + FUENTES:
        if f and os.path.exists(f):
            return f
    raise RuntimeError("No encuentro una fuente para el texto. Usa --fuente /ruta/a/fuente.ttf")


def _esc(ruta: str) -> str:
    """Escapa una ruta para usarla dentro de un filtergraph de ffmpeg."""
    return ruta.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _filtros_texto(cfg: Config, W: int, H: int, tmp: str) -> list[str]:
    filtros = []
    if not cfg.texto and not cfg.marca:
        return filtros
    fuente = _esc(_fuente(cfg))
    sombra = "shadowcolor=black@0.45:shadowx=0:shadowy=3"
    if cfg.texto:
        tam = int(W * 0.062)
        ancho_chars = max(10, int(W * 0.82 / (tam * 0.55)))
        lineas = []
        for parrafo in cfg.texto.replace("\\n", "\n").split("\n"):
            lineas += textwrap.wrap(parrafo, ancho_chars) or [""]
        y0 = int(H * 0.17) if H > W else int(H * 0.12)
        enable = f":enable='lt(t,{cfg.texto_seg})'" if cfg.texto_seg > 0 else ""
        for i, linea in enumerate(lineas):
            ruta = os.path.join(tmp, f"linea{i}.txt")
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write(linea)
            filtros.append(
                f"drawtext=fontfile='{fuente}':textfile='{_esc(ruta)}':fontsize={tam}:fontcolor=white:"
                f"x=(w-text_w)/2:y={y0 + int(i * tam * 1.25)}:{sombra}{enable}")
    if cfg.marca:
        ruta = os.path.join(tmp, "marca.txt")
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(cfg.marca)
        tam = int(W * 0.034)
        y = int(H * 0.62) if H > W else int(H * 0.88)
        filtros.append(f"drawtext=fontfile='{fuente}':textfile='{_esc(ruta)}':fontsize={tam}:"
                       f"fontcolor=white@0.85:x=(w-text_w)/2:y={y}:{sombra}")
    return filtros


def _degradado(W: int, H: int, tmp: str) -> str:
    """PNG con sombra suave arriba (donde va el texto) para que se lea sobre cualquier fondo."""
    import numpy as np
    from PIL import Image

    y = np.linspace(0, 1, H, dtype=np.float32)
    alfa = 0.55 * np.clip(1 - y / 0.42, 0, 1) ** 1.6
    img = np.zeros((H, W, 4), dtype=np.uint8)
    img[..., 3] = (alfa[:, None] * 255).astype(np.uint8)
    ruta = os.path.join(tmp, "degradado.png")
    Image.fromarray(img, "RGBA").save(ruta)
    return ruta


def _grafo(base: list[str], txt: list[str], audio_f: str, con_degradado: bool) -> str:
    v = f"[0:v]{','.join(base)}"
    if con_degradado:
        v += "[b];[b][2:v]overlay=0:0:format=auto"
    v += "".join("," + t for t in txt) + ",format=yuv420p[v]"
    return f"{v};[1:a]{audio_f}[a]"


def _cargar_voz(ruta: str, tmp: str):
    destino = os.path.join(tmp, "voz.wav")
    subprocess.run([_ffmpeg(), "-y", "-v", "error", "-i", ruta, "-ac", "2", "-ar", str(A.SR),
                    "-af", "highpass=f=80,acompressor=threshold=-24dB:ratio=3:attack=5:release=120",
                    "-c:a", "pcm_s16le", destino], check=True)
    return A.cargar_wav(destino)


def crear(cfg: Config) -> str:
    ff = _ffmpeg()
    if cfg.preset not in PRESETS:
        raise ValueError(f"Preset desconocido '{cfg.preset}'. Disponibles: {', '.join(PRESETS)}")
    if cfg.formato not in FORMATOS:
        raise ValueError(f"Formato desconocido '{cfg.formato}'. Usa: {', '.join(FORMATOS)}")
    if not 3 <= cfg.duracion <= 3600:
        raise ValueError("La duración debe estar entre 3 y 3600 segundos")

    p = PRESETS[cfg.preset]
    capas = parsear_capas(cfg.capas) if cfg.capas else p["capas"]
    estilo = cfg.estilo or p["estilo"]
    paleta = cfg.paleta or p["paleta"]
    W, H = FORMATOS[cfg.formato]
    tmp = tempfile.mkdtemp(prefix="asmr_")
    try:
        voz = None
        if cfg.voz:
            _log(cfg, "· Procesando voz…")
            voz = _cargar_voz(cfg.voz, tmp)

        _log(cfg, f"· Sintetizando audio ({', '.join(n for n, _ in capas)}) – {cfg.duracion:.0f}s…")
        mezcla = A.mezclar(capas, cfg.duracion, cfg.semilla, cfg.bucle, voz, cfg.volumen_voz)
        wav = os.path.join(tmp, "audio.wav")
        A.guardar_wav(wav, mezcla)

        if cfg.solo_audio:
            ext = os.path.splitext(cfg.salida)[1].lower() or ".wav"
            salida = cfg.salida if os.path.splitext(cfg.salida)[1] else cfg.salida + ext
            codec = ["-c:a", "libmp3lame", "-b:a", "256k"] if ext == ".mp3" else ["-c:a", "pcm_s16le"]
            subprocess.run([ff, "-y", "-v", "error", "-i", wav, "-af",
                            f"loudnorm=I={cfg.lufs}:TP=-1.5:LRA=11,aresample={A.SR}", *codec, salida], check=True)
            _log(cfg, f"✓ Audio listo: {salida}")
            return salida

        n_frames = int(round(cfg.duracion * cfg.fps))
        energia = A.envolvente(mezcla, cfg.fps, n_frames)
        txt = _filtros_texto(cfg, W, H, tmp)
        grad_in = ["-i", _degradado(W, H, tmp)] if cfg.texto else []
        audio_f = f"loudnorm=I={cfg.lufs}:TP=-1.5:LRA=11,aresample={A.SR}"
        if not cfg.bucle:
            audio_f = f"afade=t=in:d=1,afade=t=out:st={cfg.duracion - 1.5}:d=1.5," + audio_f
        salida_v = ["-c:v", "libx264", "-preset", "medium", "-crf", str(cfg.calidad), "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{cfg.duracion}"]

        ext_fondo = os.path.splitext(cfg.fondo or "")[1].lower()
        if cfg.fondo and ext_fondo in EXT_VIDEO:
            _log(cfg, "· Montando vídeo de fondo…")
            vf = [f"scale={W}:{H}:force_original_aspect_ratio=increase", f"crop={W}:{H}", f"fps={cfg.fps}",
                  "setsar=1"]
            cmd = [ff, "-y", "-v", "error", "-stats", "-stream_loop", "-1", "-i", cfg.fondo, "-i", wav, *grad_in,
                   "-filter_complex", _grafo(vf, txt, audio_f, bool(grad_in)),
                   "-map", "[v]", "-map", "[a]", *salida_v, cfg.salida]
            subprocess.run(cmd, check=True)
        else:
            if cfg.fondo and ext_fondo in EXT_IMAGEN:
                escena = Imagen(W, H, cfg.duracion, cfg.fps, paleta, cfg.semilla, ruta=cfg.fondo)
            elif cfg.fondo:
                raise ValueError(f"Formato de fondo no soportado: {ext_fondo}")
            else:
                if estilo not in ESTILOS:
                    raise ValueError(f"Estilo desconocido '{estilo}'. Usa: {', '.join(ESTILOS)}")
                escena = ESTILOS[estilo](W, H, cfg.duracion, cfg.fps, paleta, semilla=cfg.semilla)
            vf = []
            if escena.escala != 1:
                vf.append(f"scale={W}:{H}:flags=lanczos")
            vf.append("noise=alls=4:allf=t")
            if not cfg.bucle:
                vf.insert(0, f"fade=t=in:d=0.8,fade=t=out:st={cfg.duracion - 1.2}:d=1.2")
            cmd = [ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                   "-s", f"{escena.W}x{escena.H}", "-r", str(cfg.fps), "-i", "pipe:0", "-i", wav, *grad_in,
                   "-filter_complex", _grafo(vf, txt, audio_f, bool(grad_in)),
                   "-map", "[v]", "-map", "[a]", *salida_v, cfg.salida]
            _log(cfg, f"· Renderizando {n_frames} fotogramas ({estilo if not cfg.fondo else 'foto'}, {W}x{H})…")
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            paso = max(1, n_frames // 10)
            try:
                for i, fr in enumerate(escena.fotogramas(energia)):
                    proc.stdin.write(fr)
                    if i % paso == 0 and i:
                        _log(cfg, f"  {int(100 * i / n_frames)}%")
            finally:
                proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError("ffmpeg falló al codificar el vídeo")

        if cfg.portada:
            portada = os.path.splitext(cfg.salida)[0] + "_portada.jpg"
            subprocess.run([ff, "-y", "-v", "error", "-i", cfg.salida, "-frames:v", "1", "-q:v", "2", portada],
                           check=True)
        _log(cfg, f"✓ Vídeo listo: {cfg.salida}")
        return cfg.salida
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
