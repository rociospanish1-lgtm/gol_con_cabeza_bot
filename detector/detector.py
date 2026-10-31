"""Detector de clínicas de estética en Sevilla con necesidad de agente IA.

Cruza dos fuentes:
  1. data/maps_busqueda_*.json  -> listado de Google Maps (OpenSEO search_local_businesses)
  2. data/hallazgos_resenas.json -> señales sacadas de las reseñas negativas de cada clínica

Genera:
  leads_clinicas_sevilla.xlsx y leads_clinicas_sevilla.csv, ordenados por puntuación.

Uso:  python3 detector.py
"""
import csv
import glob
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

# --- Reglas de exclusión (no son cliente objetivo) ---------------------------
CADENAS = re.compile(r"dorsia|meye|doctor life|londres", re.I)
NO_ESTETICA = {"Dental clinic", "Dentist", "Periodontist", "Nutritionist"}
NOMBRE_NO_ESTETICA = re.compile(r"fisioterapia|implantes", re.I)

# --- Peso de cada señal detectada en reseñas ---------------------------------
SENALES = {
    "telefono": ("No cogen el teléfono", 10),
    "whatsapp_sin_respuesta": ("WhatsApp sin respuesta", 10),
    "mensajes_sin_respuesta": ("Mensajes sin respuesta", 10),
    "dm_sin_respuesta": ("Instagram/DM sin respuesta", 10),
    "instagram_dm": ("Citas gestionadas a mano por Instagram", 10),
    "whatsapp_descoordinado": ("WhatsApp manual sin enlazar con la agenda", 8),
    "gestion_agenda": ("Citas perdidas o mal apuntadas", 8),
    "citas_anuladas": ("Citas anuladas por falta de personal", 8),
    "cambios_cita": ("Cambios de cita de última hora", 6),
    "esperas": ("Esperas largas sin avisar", 6),
    "seguimiento": ("Promesas de 'te llamamos' incumplidas", 8),
    "fuera_horario": ("Sin canal fuera de horario", 8),
    "leads_ads": ("Captan con anuncios/ofertas en redes", 6),
    "info_telefono_erronea": ("Información errónea por teléfono", 8),
    "doctor_un_dia_semana": ("Médico solo 1 día/semana", 6),
    "telefono_trato": ("Quejas del trato por teléfono", 4),
    "no_responde_resenas": ("No responde reseñas", 5),
    "no_responde_resenas_recientes": ("Ha dejado de responder reseñas", 4),
    "sin_web": ("Sin web propia (solo redes)", 0),  # se puntúa aparte
}
DESCARTE = {"cerrada_o_cadena", "abandono"}


def zona(direccion: str) -> str:
    for z in ("Mairena del Aljarafe", "Tomares", "Camas"):
        if z in direccion:
            return z
    return "Sevilla"


def puntuar(b: dict, h: dict | None):
    """Devuelve (puntuación 0-100, lista de motivos, descartada?, motivo descarte)."""
    titulo, cat = b["title"], b.get("category", "")
    if CADENAS.search(titulo):
        return 0, [], True, "Cadena: decide la central"
    if cat in NO_ESTETICA or NOMBRE_NO_ESTETICA.search(titulo):
        return 0, [], True, "No es clínica de estética principal"
    if h and DESCARTE & set(h["senales"]):
        return 0, [], True, h.get("gancho", "Descartada")

    pts, motivos = 0, []
    n = (b.get("rating") or {}).get("votes_count") or 0
    nota = (b.get("rating") or {}).get("value") or 0

    # 1) Volumen de pacientes (más reseñas = más citas que gestionar). Máx 20.
    vol = 20 if n >= 400 else 15 if n >= 200 else 10 if n >= 100 else 5
    pts += vol

    # 2) Sin web propia => sin reserva online. 12 puntos.
    dominio = (b.get("domain") or "").lower()
    if not dominio or "instagram" in dominio or "facebook" in dominio:
        pts += 12
        motivos.append("Sin web propia (solo redes)")

    # 3) Reputación tocada => motivación para cambiar. 8 puntos.
    if nota and nota < 4.6:
        pts += 8
        motivos.append(f"Valoración {nota} (< 4,6)")

    # 4) Dolor real visto en reseñas. Máx 50.
    if h:
        dolor = 0
        for s in h["senales"]:
            if s in SENALES and SENALES[s][1]:
                dolor += SENALES[s][1]
                motivos.append(SENALES[s][0])
        pts += min(dolor, 50)
        if str(h.get("responde_negativas", "")).startswith("no"):
            pts += 5
            motivos.append("Deja críticas sin responder")
    else:
        motivos.append("Reseñas pendientes de revisar")

    return min(pts, 100), motivos, False, ""


def prioridad(p: int, revisada: bool) -> str:
    if not revisada:
        return "C - revisar reseñas"
    return "A - contactar ya" if p >= 40 else "B - segunda ronda" if p >= 25 else "C - baja"


def main():
    maps = sorted(glob.glob(os.path.join(DATA, "maps_busqueda_*.json")))[-1]
    negocios = json.load(open(maps))["businesses"]
    hallazgos = json.load(open(os.path.join(DATA, "hallazgos_resenas.json")))

    filas, vistos = [], set()
    for b in negocios:
        clave = b.get("phone") or b["title"]  # misma clínica con dos fichas en Maps
        if clave in vistos:
            continue
        vistos.add(clave)
        h = hallazgos.get(b["cid"])
        p, motivos, descartada, motivo_desc = puntuar(b, h)
        r = b.get("rating") or {}
        filas.append({
            "Prioridad": "Descartada" if descartada else prioridad(p, h is not None),
            "Puntuación": p,
            "Clínica": b["title"],
            "Zona": zona(b.get("address", "")),
            "Teléfono": b.get("phone") or "",
            "Web": b.get("url") or "",
            "Valoración": r.get("value"),
            "Nº reseñas": r.get("votes_count"),
            "Señales detectadas": "; ".join(motivos) if not descartada else motivo_desc,
            "Prueba (de sus reseñas)": (h or {}).get("nota", ""),
            "Gancho primer mensaje": (h or {}).get("gancho", "") if not descartada else "",
            "Google Maps": b.get("check_url", ""),
        })

    orden = {"A - contactar ya": 0, "B - segunda ronda": 1, "C - revisar reseñas": 2, "C - baja": 3, "Descartada": 4}
    filas.sort(key=lambda f: (orden[f["Prioridad"]], -f["Puntuación"]))

    with open(os.path.join(BASE, "leads_clinicas_sevilla.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]), delimiter=";")
        w.writeheader()
        w.writerows(filas)

    escribir_xlsx(filas, os.path.join(BASE, "leads_clinicas_sevilla.xlsx"))
    for f in filas:
        print(f'{f["Prioridad"]:<22} {f["Puntuación"]:>3}  {f["Clínica"][:55]}')


def escribir_xlsx(filas, ruta):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"
    cab = list(filas[0])
    ws.append(cab)
    for f in filas:
        ws.append([f[c] for c in cab])

    colores = {"A": "C6EFCE", "B": "FFEB9C", "C": "EDEDED", "D": "F4CCCC"}
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F1F1F")
    for fila in ws.iter_rows(min_row=2):
        clave = "D" if fila[0].value == "Descartada" else fila[0].value[0]
        fila[0].fill = PatternFill("solid", fgColor=colores[clave])
        for c in fila:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    anchos = [20, 11, 38, 18, 15, 30, 10, 10, 40, 70, 55, 30]
    for i, a in enumerate(anchos):
        ws.column_dimensions[chr(65 + i)].width = a
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(ruta)


if __name__ == "__main__":
    main()
