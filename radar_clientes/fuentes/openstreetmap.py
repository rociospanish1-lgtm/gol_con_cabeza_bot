"""OpenStreetMap (Overpass API): gratis y sin clave.

Cobertura parcial (en Sevilla capta una parte de las clínicas, no todas) y
sin reseñas. Útil para empezar sin coste o para completar Google.
"""
from __future__ import annotations

import requests

from .. import config

URL = "https://overpass-api.de/api/interpreter"

ETIQUETAS = {
    "clínica estética": ['["shop"="beauty"]', '["beauty"]', '["healthcare"="cosmetic_surgery"]',
                         '["healthcare:speciality"~"aesthetic|cosmetic|dermatology"]'],
}


def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace('"', '\\"')


def buscar(sector: str, ciudad: str) -> list[dict]:
    filtros = ETIQUETAS.get(sector.lower(), [f'["name"~"{_escapar(sector)}",i]'])
    bloques = "".join(f"nwr{f}(area.a);" for f in filtros)
    consulta = (f'[out:json][timeout:60];area["name"="{_escapar(ciudad)}"]["boundary"="administrative"]->.a;'
                f"({bloques});out center tags;")
    r = requests.post(URL, data={"data": consulta}, timeout=90,
                      headers={"User-Agent": config.USER_AGENT})
    r.raise_for_status()
    resultado = []
    for e in r.json().get("elements", []):
        t = e.get("tags", {})
        if not t.get("name"):
            continue
        calle = " ".join(x for x in [t.get("addr:street", ""), t.get("addr:housenumber", "")] if x)
        resultado.append({
            "clave": f"osm:{e['type']}/{e['id']}",
            "nombre": t["name"],
            "direccion": ", ".join(x for x in [calle, t.get("addr:city", ciudad)] if x),
            "telefono": t.get("phone") or t.get("contact:phone", ""),
            "web": t.get("website") or t.get("contact:website", ""),
            "maps_url": f"https://www.openstreetmap.org/{e['type']}/{e['id']}",
            "valoracion": None, "num_resenas": None, "resenas": [],
            "fuente": "OpenStreetMap",
        })
    return resultado
