"""Envío de mensajes por la WhatsApp Cloud API de Meta."""
import logging

import httpx

import config

log = logging.getLogger("whatsapp")


async def enviar_texto(telefono: str, texto: str) -> bool:
    if not (config.WHATSAPP_TOKEN and config.WHATSAPP_PHONE_NUMBER_ID):
        log.error("Faltan WHATSAPP_TOKEN o WHATSAPP_PHONE_NUMBER_ID: no se puede enviar")
        return False
    url = f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": telefono,
        "type": "text",
        "text": {"preview_url": True, "body": texto[:4096]},
    }
    try:
        async with httpx.AsyncClient(timeout=20) as cliente:
            r = await cliente.post(url, json=payload, headers={"Authorization": f"Bearer {config.WHATSAPP_TOKEN}"})
        if r.status_code >= 400:
            log.error("WhatsApp rechazó el envío a %s: %s %s", telefono, r.status_code, r.text[:500])
            return False
        return True
    except httpx.HTTPError as e:
        log.error("Error de red enviando a %s: %s", telefono, e)
        return False
