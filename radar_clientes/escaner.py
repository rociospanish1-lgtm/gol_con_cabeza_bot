"""Orquesta un escaneo: fuentes -> análisis -> puntuación -> base de datos."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import requests

from . import config, db
from .analisis import analizar_resenas, auditar_web, normalizar
from .fuentes import google_places, ofertas_empleo, openstreetmap
from .puntuacion import puntuar

log = logging.getLogger("radar")


def _fusionar(empresas: list[dict]) -> list[dict]:
    """Une la misma empresa encontrada en varias fuentes (por web o nombre)."""
    por_clave: dict[str, dict] = {}
    for e in empresas:
        dominio = normalizar(e.get("web", "")).replace("https://", "").replace("http://", "")
        dominio = dominio.removeprefix("www.").split("/")[0]
        k = dominio or normalizar(e["nombre"])
        if k in por_clave:
            base = por_clave[k]
            base["fuentes"].add(e["fuente"])
            for campo in ("telefono", "web", "direccion", "valoracion", "num_resenas"):
                base[campo] = base.get(campo) or e.get(campo)
            base["resenas"] += e.get("resenas", [])
            if e["fuente"] == "Google Maps":  # Google manda en clave y enlace
                base["clave"], base["maps_url"] = e["clave"], e["maps_url"]
        else:
            por_clave[k] = {**e, "fuentes": {e["fuente"]}, "resenas": list(e.get("resenas", []))}
    return list(por_clave.values())


def escanear(sector: str = config.SECTOR_POR_DEFECTO, ciudad: str = config.CIUDAD_POR_DEFECTO,
             usar_osm: bool = True, progreso: Callable[[str], None] = print) -> dict:
    avisos: list[str] = []
    encontradas: list[dict] = []

    fuentes = [("Google Maps", google_places.buscar, bool(config.GOOGLE_PLACES_API_KEY))]
    if usar_osm:
        fuentes.append(("OpenStreetMap", openstreetmap.buscar, True))
    for nombre, funcion, activa in fuentes:
        if not activa:
            avisos.append(f"{nombre}: desactivado (falta GOOGLE_PLACES_API_KEY)")
            continue
        progreso(f"Buscando en {nombre}…")
        try:
            r = funcion(sector, ciudad)
            encontradas += r
            progreso(f"  {len(r)} resultados en {nombre}")
        except requests.RequestException as e:
            avisos.append(f"{nombre}: error de conexión ({e.__class__.__name__})")

    ofertas: list[dict] = []
    if config.ADZUNA_APP_ID:
        progreso("Buscando ofertas de empleo de recepción/atención…")
        try:
            ofertas = ofertas_empleo.buscar(sector, ciudad)
            progreso(f"  {len(ofertas)} ofertas relevantes")
        except requests.RequestException as e:
            avisos.append(f"Ofertas de empleo: error de conexión ({e.__class__.__name__})")
    else:
        avisos.append("Ofertas de empleo: desactivado (faltan ADZUNA_APP_ID / ADZUNA_APP_KEY)")

    empresas = _fusionar(encontradas)

    # Empresas que publican ofertas pero no aparecieron en mapas: también son leads.
    for o in ofertas:
        if not any(ofertas_empleo.coinciden(e["nombre"], o["empresa"]) for e in empresas):
            empresas.append({"clave": f"oferta:{normalizar(o['empresa'])}", "nombre": o["empresa"],
                             "direccion": o["lugar"], "telefono": "", "web": "", "maps_url": "",
                             "valoracion": None, "num_resenas": None, "resenas": [],
                             "fuentes": {"Oferta de empleo"}})

    progreso(f"Analizando {len(empresas)} webs (reserva online, chatbot, WhatsApp)…")
    sesion = requests.Session()
    with ThreadPoolExecutor(max_workers=8) as pool:
        auditorias = list(pool.map(lambda e: auditar_web(e.get("web", ""), sesion), empresas))

    for e, auditoria in zip(empresas, auditorias):
        quejas = analizar_resenas(e.get("resenas", []))
        suyas = [o for o in ofertas if ofertas_empleo.coinciden(e["nombre"], o["empresa"])]
        r = puntuar(auditoria=auditoria if e.get("web") else None, quejas=quejas,
                    num_resenas=e.get("num_resenas"), valoracion=e.get("valoracion"),
                    ofertas=suyas, tiene_web=bool(e.get("web")))
        db.guardar({
            "clave": e["clave"], "nombre": e["nombre"], "sector": sector, "ciudad": ciudad,
            "direccion": e.get("direccion", ""), "telefono": e.get("telefono", ""),
            "web": e.get("web", ""), "maps_url": e.get("maps_url", ""),
            "valoracion": e.get("valoracion"), "num_resenas": e.get("num_resenas"),
            "fuentes": sorted(e["fuentes"]),
            "senales": {"quejas": quejas, "ofertas": suyas,
                        "web": vars(auditoria) if e.get("web") else None},
            "motivos": r["motivos"], "gancho": r["gancho"],
            "puntuacion": r["puntuacion"], "nivel": r["nivel"], "demo": 0,
        })

    resumen = {"empresas": len(empresas), "ofertas": len(ofertas), "avisos": avisos}
    for a in avisos:
        progreso(f"Aviso: {a}")
    progreso(f"Listo: {len(empresas)} empresas guardadas.")
    return resumen
