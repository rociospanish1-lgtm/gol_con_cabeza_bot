"""Comandos de Telegram para crear vídeos ASMR desde el móvil.

/asmr [preset] [segundos] [texto gancho]
    Ej.: /asmr clinica 30 Así suena una limpieza facial en Sevilla
Foto con pie de foto "/asmr ..."  -> usa la foto como fondo.
/asmr_ayuda -> lista de presets.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from asmr_creator import Config, crear
from asmr_creator.presets import PRESETS

MAX_SEG = int(os.getenv("ASMR_MAX_SEG", "60"))  # límite para no saturar el servidor
MARCA = os.getenv("ASMR_MARCA")  # p. ej. "@tuagencia", se añade a todos los vídeos
_cola = asyncio.Semaphore(1)  # un render a la vez


def _parsear(args: list[str]) -> tuple[str, float, str | None]:
    preset, seg, resto = "clinica", 30.0, list(args)
    if resto and resto[0].lower() in PRESETS:
        preset = resto.pop(0).lower()
    if resto:
        try:
            seg = float(resto[0])
            resto.pop(0)
        except ValueError:
            pass
    seg = max(5.0, min(float(MAX_SEG), seg))
    return preset, seg, (" ".join(resto) or None)


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lineas = [f"• {k} – {v['descripcion']}" for k, v in PRESETS.items()]
    await update.message.reply_text(
        "🎧 Creador de vídeos ASMR\n\n"
        "Uso: /asmr [preset] [segundos] [texto]\n"
        "Ej.: /asmr clinica 30 Así suena tu primera sesión\n\n"
        "Envía una FOTO con el pie «/asmr …» para usarla de fondo.\n\n"
        f"Presets:\n" + "\n".join(lineas) + f"\n\nMáximo {MAX_SEG} s por vídeo."
    )


async def asmr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.photo:  # foto con pie "/asmr ..."
        args = (msg.caption or "").split()[1:]
    else:
        args = context.args or []
    preset, seg, texto = _parsear(args)

    if _cola.locked():
        await msg.reply_text("⏳ Hay otro vídeo renderizándose, el tuyo va a continuación.")

    async with _cola:
        aviso = await msg.reply_text(f"🎬 Creando ASMR «{preset}» de {seg:.0f}s… (≈{seg * 1.5:.0f}s de espera)")
        with tempfile.TemporaryDirectory(prefix="asmrbot_") as tmp:
            fondo = None
            if msg.photo:
                fondo = os.path.join(tmp, "fondo.jpg")
                archivo = await msg.photo[-1].get_file()
                await archivo.download_to_drive(fondo)
            salida = os.path.join(tmp, "asmr.mp4")
            cfg = Config(salida=salida, preset=preset, duracion=seg, texto=texto, marca=MARCA, fondo=fondo,
                         calidad=23, portada=False, progreso=lambda _m: None)
            try:
                await asyncio.to_thread(crear, cfg)
            except Exception as e:  # el bot no debe caerse por un render fallido
                await aviso.edit_text(f"❌ No se pudo crear el vídeo: {e}")
                return
            with open(salida, "rb") as fh:
                await msg.reply_video(fh, caption=f"🎧 {preset} · {seg:.0f}s · escúchalo con auriculares",
                                      supports_streaming=True, read_timeout=120, write_timeout=120)
        await aviso.delete()


def registrar(app) -> None:
    app.add_handler(CommandHandler("asmr", asmr))
    app.add_handler(CommandHandler("asmr_ayuda", ayuda))
    app.add_handler(MessageHandler(filters.PHOTO & filters.CaptionRegex(r"^/asmr\b"), asmr))
