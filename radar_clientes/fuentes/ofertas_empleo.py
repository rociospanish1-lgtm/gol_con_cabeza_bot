"""Ofertas de empleo (Adzuna, incluye portales españoles).

Señal de compra más fuerte: una clínica que publica una oferta de
recepcionista ya ha decidido pagar un sueldo para cubrir la atención y la
agenda: el problema está reconocido y hay presupuesto. Requiere ADZUNA_APP_ID y ADZUNA_APP_KEY
(registro gratuito en developer.adzuna.com).
"""
from __future__ import annotations

import requests

from .. import config
from ..analisis import normalizar

URL = "https://api.adzuna.com/v1/api/jobs/es/search/{pagina}"
GENERICAS = {"clinica", "centro", "de", "la", "el", "y", "en"}


def palabras_sector(sector: str) -> str:
    utiles = [w for w in normalizar(sector).split() if w not in GENERICAS]
    return " ".join(utiles) or normalizar(sector)


def buscar(sector: str, ciudad: str, dias: int = 45) -> list[dict]:
    if not (config.ADZUNA_APP_ID and config.ADZUNA_APP_KEY):
        return []
    ofertas: dict[str, dict] = {}
    for puesto in config.PUESTOS_SENAL:
        params = {
            "app_id": config.ADZUNA_APP_ID, "app_key": config.ADZUNA_APP_KEY,
            "what": f"{puesto} {palabras_sector(sector)}", "where": ciudad,
            "max_days_old": dias, "results_per_page": 50, "content-type": "application/json",
        }
        r = requests.get(URL.format(pagina=1), params=params, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        for o in r.json().get("results", []):
            empresa = (o.get("company") or {}).get("display_name", "").strip()
            if not empresa:
                continue
            ofertas.setdefault(o.get("id") or o.get("redirect_url"), {
                "empresa": empresa,
                "titulo": o.get("title", "").strip(),
                "url": o.get("redirect_url", ""),
                "fecha": (o.get("created") or "")[:10],
                "lugar": (o.get("location") or {}).get("display_name", ""),
            })
    return list(ofertas.values())


_RUIDO = {"clinica", "centro", "estetica", "medicina", "medica", "sl", "s.l.", "slu", "sa",
          "s.a.", "grupo", "de", "la", "el", "y", "beauty", "spa", "instituto"}


def _tokens(nombre: str) -> set[str]:
    return {w.strip(".,-") for w in normalizar(nombre).split()} - _RUIDO - {""}


def coinciden(nombre_empresa: str, nombre_oferta: str) -> bool:
    a, b = _tokens(nombre_empresa), _tokens(nombre_oferta)
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= 0.6
