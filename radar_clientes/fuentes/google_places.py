"""Google Places API (New): empresas + valoración + hasta 5 reseñas por ficha.

Es la fuente más potente para tu nicho porque trae reseñas, y las reseñas
son donde los pacientes dicen "no cogen el teléfono".
Requiere GOOGLE_PLACES_API_KEY (Google Cloud > APIs > "Places API (New)").
"""
from __future__ import annotations

import time

import requests

from .. import config

URL = "https://places.googleapis.com/v1/places:searchText"
CAMPOS = ",".join([
    "places.id", "places.displayName", "places.formattedAddress",
    "places.nationalPhoneNumber", "places.websiteUri", "places.rating",
    "places.userRatingCount", "places.googleMapsUri", "places.reviews",
    "places.businessStatus", "nextPageToken",
])

# Variantes de búsqueda: Google devuelve máx. 60 resultados por consulta,
# así que lanzamos varias para cubrir más clínicas.
VARIANTES = {
    "clínica estética": ["clínica estética", "medicina estética", "centro de estética",
                         "clínica de depilación láser", "tratamientos faciales"],
}


def buscar(sector: str, ciudad: str, max_paginas: int = 3) -> list[dict]:
    if not config.GOOGLE_PLACES_API_KEY:
        return []
    cabeceras = {"X-Goog-Api-Key": config.GOOGLE_PLACES_API_KEY, "X-Goog-FieldMask": CAMPOS,
                 "Content-Type": "application/json"}
    vistos: dict[str, dict] = {}
    for consulta in VARIANTES.get(sector.lower(), [sector]):
        cuerpo = {"textQuery": f"{consulta} en {ciudad}", "languageCode": "es",
                  "regionCode": "ES", "pageSize": 20}
        for _ in range(max_paginas):
            r = requests.post(URL, json=cuerpo, headers=cabeceras, timeout=config.HTTP_TIMEOUT)
            r.raise_for_status()
            datos = r.json()
            for p in datos.get("places", []):
                if p.get("businessStatus", "OPERATIONAL") != "OPERATIONAL" or p["id"] in vistos:
                    continue
                resenas = [(rv.get("originalText") or rv.get("text") or {}).get("text", "")
                           for rv in p.get("reviews", [])]
                vistos[p["id"]] = {
                    "clave": f"gplaces:{p['id']}",
                    "nombre": p.get("displayName", {}).get("text", "Sin nombre"),
                    "direccion": p.get("formattedAddress", ""),
                    "telefono": p.get("nationalPhoneNumber", ""),
                    "web": p.get("websiteUri", ""),
                    "maps_url": p.get("googleMapsUri", ""),
                    "valoracion": p.get("rating"),
                    "num_resenas": p.get("userRatingCount"),
                    "resenas": [t for t in resenas if t],
                    "fuente": "Google Maps",
                }
            token = datos.get("nextPageToken")
            if not token:
                break
            cuerpo["pageToken"] = token
            time.sleep(2)  # Google tarda unos segundos en activar el token
    return list(vistos.values())
