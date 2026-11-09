"""Recolectores de señales: web de la clínica, reseñas y Google Places (opcional).

Solo usa la librería estándar de Python para que funcione en cualquier
ordenador sin instalar nada.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser

from . import config

USER_AGENT = "Mozilla/5.0 (compatible; DemandIntentBot/1.0)"
TIMEOUT = 15
# Subpáginas que merece la pena mirar además de la portada.
SUBPAGE_HINTS = ("contacto", "cita", "reserva", "trabaja", "empleo", "equipo",
                 "tratamientos", "servicios", "centros", "clinicas", "sedes")
MAX_SUBPAGES = 4


# ---------------------------------------------------------------------------
# Utilidades HTML
# ---------------------------------------------------------------------------

class _LinkAndTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.text_parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.text_parts.append(data.strip())


def parse_html(html: str) -> tuple[str, list[str]]:
    """Devuelve (texto visible en minúsculas, enlaces)."""
    parser = _LinkAndTextParser()
    try:
        parser.feed(html)
    except Exception:  # HTML roto: nos quedamos con lo que se haya leído
        pass
    return " ".join(parser.text_parts).lower(), parser.links


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept-Language": "es-ES,es;q=0.9"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read(2_000_000).decode(charset, errors="replace")


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url and not re.match(r"^https?://", url):
        url = "https://" + url
    return url


# ---------------------------------------------------------------------------
# Señales de la web
# ---------------------------------------------------------------------------

@dataclass
class WebSignals:
    url: str = ""
    ok: bool = False
    error: str = ""
    pages_scanned: int = 0
    booking_tools: list[str] = field(default_factory=list)
    chat_tools: list[str] = field(default_factory=list)
    has_whatsapp: bool = False
    manual_booking: bool = False
    hiring: bool = False
    high_ticket: list[str] = field(default_factory=list)
    multi_location: bool = False
    is_aesthetic: bool = False
    city_mentions: list[str] = field(default_factory=list)


def _detect(raw_html: str, text: str, signals: WebSignals) -> None:
    raw = raw_html.lower()
    for name, needles in config.BOOKING_TECH.items():
        if name not in signals.booking_tools and any(n in raw for n in needles):
            signals.booking_tools.append(name)
    for name, needles in config.CHAT_TECH.items():
        if name not in signals.chat_tools and any(n in raw for n in needles):
            signals.chat_tools.append(name)
    if any(p in raw for p in config.WHATSAPP_PATTERNS):
        signals.has_whatsapp = True
    if any(p in text for p in config.MANUAL_BOOKING_PHRASES):
        signals.manual_booking = True
    if any(p in text for p in config.HIRING_PHRASES):
        signals.hiring = True
    for t in config.HIGH_TICKET_TREATMENTS:
        if t in text and t not in signals.high_ticket:
            signals.high_ticket.append(t)
    if any(k in text for k in config.AESTHETIC_KEYWORDS):
        signals.is_aesthetic = True
    for c in config.TARGET_CITIES:
        if c in text and c not in signals.city_mentions:
            signals.city_mentions.append(c)
    if re.search(r"\b(nuestros centros|nuestras clínicas|nuestras clinicas|nuestras sedes|"
                 r"[2-9] centros|[2-9] clínicas|[2-9] clinicas)\b", text):
        signals.multi_location = True


def _pick_subpages(base_url: str, links: list[str]) -> list[str]:
    base_host = urllib.parse.urlparse(base_url).netloc
    picked: list[str] = []
    for href in links:
        full = urllib.parse.urljoin(base_url, href.split("#")[0])
        parsed = urllib.parse.urlparse(full)
        if parsed.scheme not in ("http", "https") or parsed.netloc != base_host:
            continue
        if any(h in parsed.path.lower() for h in SUBPAGE_HINTS) and full not in picked:
            picked.append(full)
        if len(picked) >= MAX_SUBPAGES:
            break
    return picked


def scan_website(url: str, fetcher=fetch) -> WebSignals:
    """Analiza portada + hasta 4 subpáginas relevantes."""
    url = normalize_url(url)
    signals = WebSignals(url=url)
    if not url:
        signals.error = "sin web"
        return signals
    try:
        home = fetcher(url)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        signals.error = f"no se pudo abrir la web: {exc}"
        return signals

    signals.ok = True
    text, links = parse_html(home)
    _detect(home, text, signals)
    signals.pages_scanned = 1
    for sub in _pick_subpages(url, links):
        try:
            html = fetcher(sub)
        except (urllib.error.URLError, OSError, ValueError):
            continue
        sub_text, _ = parse_html(html)
        _detect(html, sub_text, signals)
        signals.pages_scanned += 1
    return signals


# ---------------------------------------------------------------------------
# Señales de reseñas
# ---------------------------------------------------------------------------

@dataclass
class ReviewSignals:
    total_reviews_analyzed: int = 0
    pain_reviews: int = 0
    pain_by_type: dict[str, int] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)  # citas literales


def analyze_reviews(reviews: list[str]) -> ReviewSignals:
    out = ReviewSignals(total_reviews_analyzed=len(reviews))
    for review in reviews:
        low = review.lower()
        hit_types = [kind for kind, phrases in config.REVIEW_PAIN.items()
                     if any(p in low for p in phrases)]
        # "whatsapp" por sí solo no es dolor: solo cuenta si va con otra queja
        if hit_types == ["whatsapp_mensajes"]:
            continue
        if hit_types:
            out.pain_reviews += 1
            for kind in hit_types:
                out.pain_by_type[kind] = out.pain_by_type.get(kind, 0) + 1
            if len(out.evidence) < 3:
                snippet = review.strip().replace("\n", " ")
                out.evidence.append(snippet[:220] + ("…" if len(snippet) > 220 else ""))
    return out


def split_reviews(raw: str) -> list[str]:
    """Las reseñas en el CSV van separadas por '||'."""
    return [r.strip() for r in (raw or "").split("||") if r.strip()]


# ---------------------------------------------------------------------------
# Google Places API (New) — opcional, necesita GOOGLE_PLACES_API_KEY
# ---------------------------------------------------------------------------

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_FIELDS = ",".join([
    "places.id", "places.displayName", "places.formattedAddress",
    "places.websiteUri", "places.nationalPhoneNumber", "places.rating",
    "places.userRatingCount", "places.reviews", "places.primaryTypeDisplayName",
    "nextPageToken",
])


def places_search(query: str, api_key: str | None = None, max_results: int = 60) -> list[dict]:
    """Busca clínicas en Google Maps y devuelve filas listas para el CSV.

    Ojo: el campo `reviews` se factura como SKU Enterprise+Atmosphere.
    Google solo devuelve hasta 5 reseñas por sitio.
    """
    api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise RuntimeError("Falta GOOGLE_PLACES_API_KEY")

    rows: list[dict] = []
    page_token = None
    while len(rows) < max_results:
        body = {"textQuery": query, "languageCode": "es", "regionCode": "ES", "pageSize": 20}
        if page_token:
            body["pageToken"] = page_token
        req = urllib.request.Request(
            PLACES_URL, data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Goog-Api-Key": api_key,
                     "X-Goog-FieldMask": PLACES_FIELDS})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
        for p in data.get("places", []):
            reviews = [r.get("text", {}).get("text", "") for r in p.get("reviews", [])]
            rows.append({
                "nombre": p.get("displayName", {}).get("text", ""),
                "web": p.get("websiteUri", ""),
                "telefono": p.get("nationalPhoneNumber", ""),
                "direccion": p.get("formattedAddress", ""),
                "categoria": p.get("primaryTypeDisplayName", {}).get("text", ""),
                "valoracion": p.get("rating", ""),
                "num_resenas": p.get("userRatingCount", ""),
                "resenas": " || ".join(r.replace("||", "|") for r in reviews if r),
                "instagram": "",
                "notas": "",
            })
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return rows[:max_results]
