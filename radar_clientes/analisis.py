"""Detección de señales de necesidad: reseñas y web de cada empresa."""
from __future__ import annotations

import ipaddress
import re
import socket
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import config


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar textos en español."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.lower()).strip()


# ---------------------------------------------------------------------------
# Reseñas: quejas que un agente IA resuelve directamente
# ---------------------------------------------------------------------------
PATRONES_QUEJA = {
    "telefono": [
        r"no (cogen|coge|contestan|contesta|responden|responde|atienden|atiende) (el|al) telefono",
        r"no (cogen|coge|contestan|contesta|responden|responde|atienden|atiende) (las|nunca las) llamadas",
        r"imposible (contactar|hablar|comunicar|localizar)",
        r"(nadie|nunca) (lo )?(coge|contesta|responde|atiende)",
        r"(llame|he llamado|llamamos) (varias|muchas|mil|\d+) veces",
        r"no (me|nos) (devolvieron|devuelven|han devuelto) (la|las) llamada",
        r"comunica(ndo)? (todo el rato|siempre)",
    ],
    "mensajes": [
        r"no (contestan|contesta|responden|responde)n? (al|los|el|a los)? ?(whatsapp|mensajes?|correos?|emails?|mails?|instagram|dm)",
        r"(dejaron|dejan|deja) en visto",
        r"tarda(n|ron)? (dias|mucho|una semana|horas) en (responder|contestar)",
        r"sin respuesta",
    ],
    "citas": [
        r"(dificil|imposible|complicado) (conseguir|coger|pedir|reservar) (una )?cita",
        r"(cancelaron|anularon|cambiaron) (mi|la) cita",
        r"no (me|nos) (avisaron|recordaron|confirmaron)",
        r"(se olvidaron|olvidaron) (de )?(mi|la) cita",
        r"(me|nos) (dieron|dan) cita (para|dentro de) (\d+|un|dos|tres) (semanas|meses|mes)",
        r"overbooking|doble reserva",
    ],
}
_REGEX_QUEJA = {k: [re.compile(p) for p in v] for k, v in PATRONES_QUEJA.items()}


def analizar_resenas(resenas: list[str]) -> dict[str, list[str]]:
    """Devuelve {tipo_queja: [fragmentos de reseña]} con las quejas encontradas."""
    hallazgos: dict[str, list[str]] = {}
    for texto in resenas:
        t = normalizar(texto)
        for tipo, regexes in _REGEX_QUEJA.items():
            if any(r.search(t) for r in regexes):
                fragmento = texto.strip().replace("\n", " ")
                hallazgos.setdefault(tipo, []).append(fragmento[:220])
    return hallazgos


# ---------------------------------------------------------------------------
# Web: ¿tiene reserva online? ¿chatbot? ¿WhatsApp manual?
# ---------------------------------------------------------------------------
SOFTWARE_RESERVAS = {
    "koibox": "Koibox", "flowww": "Flowww", "booksy": "Booksy",
    "treatwell": "Treatwell", "fresha": "Fresha", "doctoralia": "Doctoralia",
    "reservio": "Reservio", "simplybook": "SimplyBook", "calendly": "Calendly",
    "timify": "Timify", "bewe.": "BEWE", "salonized": "Salonized",
    "agendapro": "AgendaPro", "setmore": "Setmore", "acuityscheduling": "Acuity",
    "clinic-cloud": "Clinic Cloud", "clinicminds": "Clinicminds",
    "bookitit": "Bookitit", "glofox": "Glofox", "appointlet": "Appointlet",
}
CHATBOTS = {
    "tidio": "Tidio", "crisp.chat": "Crisp", "intercom": "Intercom",
    "tawk.to": "Tawk.to", "zopim": "Zendesk Chat", "zdassets": "Zendesk",
    "manychat": "ManyChat", "landbot": "Landbot", "chatbase": "Chatbase",
    "botpress": "Botpress", "voiceflow": "Voiceflow", "wati.io": "WATI",
    "respond.io": "respond.io", "hs-scripts": "HubSpot", "livechatinc": "LiveChat",
    "smartsupp": "Smartsupp", "chatwoot": "Chatwoot", "callbell": "Callbell",
}
PATRON_WHATSAPP = re.compile(r"(wa\.me/|api\.whatsapp\.com|web\.whatsapp\.com|whatsapp://)", re.I)
PATRON_CITA = re.compile(r"(pide|pedir|reserva|reservar|solicita|solicitar|agenda|pedir) ?(tu|una)? ?cita", re.I)


@dataclass
class AuditoriaWeb:
    accesible: bool = False
    error: str = ""
    reservas: list[str] = field(default_factory=list)
    chatbots: list[str] = field(default_factory=list)
    whatsapp: bool = False
    formulario: bool = False
    pide_cita_manual: bool = False  # texto "pide tu cita" sin software detrás


class URLNoPermitida(Exception):
    pass


def _validar_url(url: str) -> None:
    """Evita que el escáner acceda a redes internas (protección SSRF)."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise URLNoPermitida("solo se admiten URLs http/https")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror as e:
        raise URLNoPermitida(f"dominio no resuelve: {e}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise URLNoPermitida("la URL apunta a una red privada")


def descargar_web(url: str, sesion: requests.Session | None = None) -> str:
    """Descarga HTML con límites de tamaño, tiempo y redirecciones."""
    sesion = sesion or requests.Session()
    if not urlparse(url).scheme:
        url = "https://" + url
    for _ in range(4):
        _validar_url(url)
        r = sesion.get(url, timeout=config.HTTP_TIMEOUT, allow_redirects=False, stream=True,
                       headers={"User-Agent": config.USER_AGENT, "Accept-Language": "es-ES,es"})
        if r.is_redirect or r.is_permanent_redirect:
            url = urljoin(url, r.headers.get("Location", ""))
            r.close()
            continue
        r.raise_for_status()
        contenido = b""
        for trozo in r.iter_content(65536):
            contenido += trozo
            if len(contenido) > config.MAX_BYTES_WEB:
                break
        r.close()
        return contenido.decode(r.encoding or "utf-8", errors="replace")
    raise URLNoPermitida("demasiadas redirecciones")


def auditar_html(html: str) -> AuditoriaWeb:
    a = AuditoriaWeb(accesible=True)
    bajo = html.lower()
    a.reservas = sorted({nombre for clave, nombre in SOFTWARE_RESERVAS.items() if clave in bajo})
    a.chatbots = sorted({nombre for clave, nombre in CHATBOTS.items() if clave in bajo})
    a.whatsapp = bool(PATRON_WHATSAPP.search(html))
    sopa = BeautifulSoup(html, "html.parser")
    a.formulario = any(f.find(["input", "textarea"]) for f in sopa.find_all("form"))
    texto = normalizar(sopa.get_text(" "))
    a.pide_cita_manual = bool(PATRON_CITA.search(texto)) and not a.reservas
    return a


def auditar_web(url: str, sesion: requests.Session | None = None) -> AuditoriaWeb:
    if not url:
        return AuditoriaWeb(error="sin web")
    try:
        return auditar_html(descargar_web(url, sesion))
    except (requests.RequestException, URLNoPermitida, UnicodeError) as e:
        return AuditoriaWeb(error=str(e)[:150])
