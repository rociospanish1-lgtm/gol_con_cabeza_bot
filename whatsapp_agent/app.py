"""Servidor del agente de WhatsApp.

Rutas:
  GET  /webhook  -> verificación del webhook por Meta
  POST /webhook  -> mensajes entrantes de WhatsApp
  GET  /panel    -> panel para encender / apagar el bot desde el móvil (requiere ADMIN_TOKEN)
  GET  /salud    -> comprobación de que el servidor está vivo
"""
import asyncio
import hashlib
import hmac
import html
import json
import logging
import secrets
import time
from collections import defaultdict
from urllib.parse import quote

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

import config
import whatsapp
from agent import Agente
from config import normalizar_telefono
from storage import Storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

app = FastAPI(title="Agente WhatsApp", docs_url=None, redoc_url=None, openapi_url=None)
storage = Storage(config.RUTA_BD, config.BOT_ACTIVO_INICIAL)
_agente: Agente | None = None
_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

AYUDA = (
    "Comandos:\n"
    "#on - activa el bot\n"
    "#off - desactiva el bot (no responde a nadie)\n"
    "#estado - muestra si está activo y los chats pausados\n"
    "#pausar 34600111222 [horas] - el bot deja de responder a ese cliente\n"
    "#reanudar 34600111222 - el bot vuelve a responder a ese cliente\n"
    "#ayuda - esta lista"
)


def agente() -> Agente:
    global _agente
    if _agente is None:
        _agente = Agente()
    return _agente


def texto_estado() -> str:
    lineas = [f"Bot: {'ACTIVO ✅' if storage.bot_activo() else 'DESACTIVADO ⛔'}"]
    pausados = storage.pausados()
    if pausados:
        lineas.append("Chats pausados:")
        for tel, hasta in pausados:
            fin = "indefinido" if hasta is None else time.strftime("%d/%m %H:%M", time.localtime(hasta))
            lineas.append(f"- {tel} (hasta {fin})")
    else:
        lineas.append("Sin chats pausados.")
    return "\n".join(lineas)


async def avisar_admins(texto: str) -> None:
    for numero in config.ADMIN_NUMEROS:
        await whatsapp.enviar_texto(numero, texto)


# ---------------------------------------------------------------- comandos admin
def ejecutar_comando(texto: str) -> str:
    partes = texto.strip().split()
    cmd = partes[0].lower().lstrip("#")
    if cmd in {"on", "activar", "encender"}:
        storage.set_bot_activo(True)
        return "Bot ACTIVADO ✅. Responderá a tus clientes."
    if cmd in {"off", "desactivar", "apagar"}:
        storage.set_bot_activo(False)
        return "Bot DESACTIVADO ⛔. No responderá a nadie hasta que mandes #on."
    if cmd == "estado":
        return texto_estado()
    if cmd in {"pausar", "reanudar"}:
        if len(partes) < 2 or not normalizar_telefono(partes[1]):
            return f"Falta el número. Ejemplo: #{cmd} 34600111222"
        tel = normalizar_telefono(partes[1])
        if cmd == "reanudar":
            return f"El bot vuelve a atender a {tel}." if storage.reanudar(tel) else f"{tel} no estaba pausado."
        horas = None
        if len(partes) > 2:
            try:
                horas = float(partes[2].replace(",", "."))
            except ValueError:
                return "Las horas deben ser un número. Ejemplo: #pausar 34600111222 24"
        storage.pausar(tel, horas)
        return f"Chat con {tel} pausado {'indefinidamente' if not horas else f'{horas:g} h'}. Respondes tú."
    return AYUDA


# ---------------------------------------------------------------- mensajes entrantes
def extraer_texto(msg: dict) -> str | None:
    tipo = msg.get("type")
    if tipo == "text":
        return msg.get("text", {}).get("body", "")
    if tipo == "button":
        return msg.get("button", {}).get("text", "")
    if tipo == "interactive":
        inter = msg.get("interactive", {})
        return (inter.get("button_reply") or inter.get("list_reply") or {}).get("title", "")
    if tipo in {"reaction", "unsupported", "system", "request_welcome"}:
        return None
    nombres = {"audio": "un audio", "image": "una imagen", "video": "un vídeo", "document": "un documento",
               "sticker": "un sticker", "location": "una ubicación", "contacts": "un contacto"}
    return f"[El cliente ha enviado {nombres.get(tipo, 'un archivo')}, que el asistente no puede ver ni escuchar]"


async def procesar_mensaje(msg: dict, nombre: str | None) -> None:
    tel = normalizar_telefono(msg.get("from", ""))
    texto = extraer_texto(msg)
    if not tel or texto is None or not texto.strip():
        return

    async with _locks[tel]:  # respuestas en orden aunque el cliente mande varios mensajes seguidos
        if tel in config.ADMIN_NUMEROS and texto.strip().startswith("#"):
            await whatsapp.enviar_texto(tel, ejecutar_comando(texto))
            return

        storage.guardar_contacto(tel, nombre)
        storage.guardar_mensaje(tel, "user", texto)

        if not storage.bot_activo():
            log.info("Bot desactivado: no se responde a %s", tel)
            return
        if storage.esta_pausado(tel):
            log.info("Chat %s pausado: no se responde", tel)
            return

        if storage.respuestas_recientes(tel) >= config.MAX_RESPUESTAS_HORA:
            log.warning("Límite de %s respuestas/hora alcanzado con %s", config.MAX_RESPUESTAS_HORA, tel)
            storage.pausar(tel, 1)
            await avisar_admins(f"⚠️ {tel} ha superado {config.MAX_RESPUESTAS_HORA} mensajes en una hora. "
                                f"Bot pausado 1 h en ese chat. Revisa: https://wa.me/{tel}")
            return

        respuesta = await agente().responder(storage.historial(tel, config.MAX_HISTORIAL), nombre)

        if respuesta.texto and await whatsapp.enviar_texto(tel, respuesta.texto):
            storage.guardar_mensaje(tel, "assistant", respuesta.texto)

        for aviso in respuesta.avisos:
            if aviso.pausar_bot:
                storage.pausar(tel)
            quien = f"{nombre} ({tel})" if nombre else tel
            await avisar_admins(
                f"🔔 {quien}\nMotivo: {aviso.motivo.replace('_', ' ')}\n{aviso.resumen}\n\n"
                f"Escríbele: https://wa.me/{tel}"
                + (f"\nEl bot está pausado en ese chat. Para devolvérselo: #reanudar {tel}" if aviso.pausar_bot else "")
            )


def procesar_eco(eco: dict) -> None:
    """Modo coexistencia: tú has respondido a mano desde la app de WhatsApp Business -> el bot se calla en ese chat."""
    tel = normalizar_telefono(eco.get("to", ""))
    if not tel:
        return
    texto = extraer_texto(eco)
    if texto:
        storage.guardar_mensaje(tel, "assistant", texto)
    if config.HORAS_PAUSA_MANUAL > 0:
        storage.pausar(tel, config.HORAS_PAUSA_MANUAL)
        log.info("Respuesta manual detectada en %s: bot pausado %s h", tel, config.HORAS_PAUSA_MANUAL)


async def procesar_payload(payload: dict) -> None:
    for entrada in payload.get("entry", []):
        for cambio in entrada.get("changes", []):
            campo = cambio.get("field")
            valor = cambio.get("value", {})
            if campo == "smb_message_echoes":
                for eco in valor.get("message_echoes", []):
                    if eco.get("id") and storage.marcar_procesado(eco["id"]):
                        procesar_eco(eco)
                continue
            if campo != "messages":
                continue
            nombres = {
                normalizar_telefono(c.get("wa_id", "")): c.get("profile", {}).get("name")
                for c in valor.get("contacts", [])
            }
            for msg in valor.get("messages", []):
                if not msg.get("id") or not storage.marcar_procesado(msg["id"]):
                    continue  # duplicado: Meta reenvía el webhook si no contestamos rápido
                try:
                    await procesar_mensaje(msg, nombres.get(normalizar_telefono(msg.get("from", ""))))
                except Exception:
                    log.exception("Error procesando el mensaje %s", msg.get("id"))


def firma_valida(cuerpo: bytes, cabecera: str | None) -> bool:
    if not config.WHATSAPP_APP_SECRET:
        return config.PERMITIR_SIN_FIRMA
    if not cabecera or not cabecera.startswith("sha256="):
        return False
    esperada = hmac.new(config.WHATSAPP_APP_SECRET.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, cabecera.removeprefix("sha256="))


@app.get("/webhook")
async def verificar_webhook(
    modo: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    reto: str = Query("", alias="hub.challenge"),
):
    if modo == "subscribe" and config.WHATSAPP_VERIFY_TOKEN and secrets.compare_digest(token, config.WHATSAPP_VERIFY_TOKEN):
        return PlainTextResponse(reto)
    raise HTTPException(status_code=403, detail="Token de verificación incorrecto")


@app.post("/webhook")
async def recibir_webhook(request: Request, tareas: BackgroundTasks):
    cuerpo = await request.body()
    if not firma_valida(cuerpo, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=401, detail="Firma no válida")
    try:
        payload = json.loads(cuerpo)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON no válido")
    # Respondemos 200 al momento y procesamos en segundo plano (Meta exige respuesta rápida).
    tareas.add_task(procesar_payload, payload)
    return {"ok": True}


# ---------------------------------------------------------------- panel web
def _token_ok(token: str) -> bool:
    return bool(config.ADMIN_TOKEN) and secrets.compare_digest(token.encode(), config.ADMIN_TOKEN.encode())


@app.get("/panel", response_class=HTMLResponse)
async def panel(token: str = ""):
    if not _token_ok(token):
        raise HTTPException(status_code=403, detail="Acceso denegado")
    activo = storage.bot_activo()
    t = html.escape(token, quote=True)
    filas = "".join(
        f"<li>{html.escape(tel)} <form method=post action=/panel style=display:inline>"
        f"<input type=hidden name=token value='{t}'><input type=hidden name=accion value=reanudar>"
        f"<input type=hidden name=telefono value='{html.escape(tel, quote=True)}'><button>Reanudar</button></form></li>"
        for tel, _ in storage.pausados()
    ) or "<li>Ninguno</li>"
    estado = "ACTIVO" if activo else "DESACTIVADO"
    color = "#1a7f37" if activo else "#b42318"
    accion, boton = ("off", "Desactivar bot") if activo else ("on", "Activar bot")
    return f"""<!doctype html><html lang=es><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><meta name=robots content=noindex>
<title>Agente WhatsApp</title>
<style>body{{font-family:system-ui,sans-serif;max-width:420px;margin:40px auto;padding:0 16px}}
.estado{{font-size:28px;font-weight:700;color:{color}}}button{{font-size:18px;padding:12px 20px;border-radius:10px;
border:0;background:#111;color:#fff;cursor:pointer}}li button{{font-size:13px;padding:4px 10px}}</style></head>
<body><h1>{html.escape(config.NOMBRE_NEGOCIO)}</h1><p class=estado>Bot {estado}</p>
<form method=post action=/panel><input type=hidden name=token value='{t}'>
<input type=hidden name=accion value={accion}><button>{boton}</button></form>
<h2>Chats pausados</h2><ul>{filas}</ul></body></html>"""


@app.post("/panel")
async def panel_accion(token: str = Form(""), accion: str = Form(""), telefono: str = Form("")):
    if not _token_ok(token):
        raise HTTPException(status_code=403, detail="Acceso denegado")
    if accion == "on":
        storage.set_bot_activo(True)
    elif accion == "off":
        storage.set_bot_activo(False)
    elif accion == "reanudar" and normalizar_telefono(telefono):
        storage.reanudar(normalizar_telefono(telefono))
    else:
        raise HTTPException(status_code=400, detail="Acción no válida")
    log.info("Panel: acción %s", accion)
    return RedirectResponse(f"/panel?token={quote(token)}", status_code=303)


@app.get("/salud")
async def salud():
    return {"ok": True, "bot_activo": storage.bot_activo()}
