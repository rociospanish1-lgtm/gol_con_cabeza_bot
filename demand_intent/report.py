"""Exportación de resultados: CSV ordenado + informe HTML."""

from __future__ import annotations

import csv
import html
from datetime import date

from .scoring import ScoredAccount

CSV_COLUMNS = [
    "ranking", "temperatura", "total", "fit", "intent", "nombre", "telefono", "web",
    "instagram", "direccion", "valoracion", "num_resenas", "reserva_online", "chat",
    "whatsapp", "contratando", "resenas_con_dolor", "angulo", "mensaje_apertura",
    "motivos", "evidencia_resenas", "error_web",
]


def write_csv(results: list[ScoredAccount], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:  # utf-8-sig: Excel lo abre bien
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, delimiter=";")
        writer.writeheader()
        for i, r in enumerate(results, 1):
            a = r.account
            writer.writerow({
                "ranking": i,
                "temperatura": r.temperatura,
                "total": r.total,
                "fit": r.fit,
                "intent": r.intent,
                "nombre": a.nombre,
                "telefono": a.telefono,
                "web": a.web,
                "instagram": a.instagram,
                "direccion": a.direccion,
                "valoracion": a.valoracion if a.valoracion is not None else "",
                "num_resenas": a.num_resenas if a.num_resenas is not None else "",
                "reserva_online": ", ".join(r.web.booking_tools) or "NO",
                "chat": ", ".join(r.web.chat_tools) or "NO",
                "whatsapp": "SÍ" if r.web.has_whatsapp else "NO",
                "contratando": "SÍ" if r.web.hiring else "NO",
                "resenas_con_dolor": r.reviews.pain_reviews,
                "angulo": r.angulo,
                "mensaje_apertura": r.mensaje_apertura,
                "motivos": " | ".join(r.motivos),
                "evidencia_resenas": " | ".join(r.reviews.evidence),
                "error_web": r.web.error,
            })


_TEMP_COLOR = {"CALIENTE": "#d64545", "TEMPLADA": "#e0a030", "FRÍA": "#6b8fb3"}


def write_html(results: list[ScoredAccount], path: str) -> None:
    e = html.escape
    hot = sum(r.temperatura == "CALIENTE" for r in results)
    warm = sum(r.temperatura == "TEMPLADA" for r in results)
    cards = []
    for i, r in enumerate(results, 1):
        a = r.account
        color = _TEMP_COLOR.get(r.temperatura, "#999")
        motivos = "".join(f"<li>{e(m)}</li>" for m in r.motivos)
        evid = "".join(f"<blockquote>{e(q)}</blockquote>" for q in r.reviews.evidence)
        contacto = " · ".join(x for x in [e(a.telefono),
                                          f'<a href="{e(a.web)}">{e(a.web)}</a>' if a.web else "",
                                          e(a.instagram)] if x)
        cards.append(f"""
<section class="card">
  <header>
    <span class="rank">#{i}</span>
    <h2>{e(a.nombre)}</h2>
    <span class="badge" style="background:{color}">{e(r.temperatura)} · {r.total}/100</span>
  </header>
  <p class="meta">FIT {r.fit}/40 · INTENT {r.intent}/60 · {contacto}</p>
  <h3>Ángulo de entrada</h3><p><strong>{e(r.angulo)}</strong></p>
  <h3>Primer mensaje sugerido</h3><p class="msg">{e(r.mensaje_apertura)}</p>
  <h3>Señales detectadas</h3><ul>{motivos}</ul>
  {"<h3>Lo que dicen sus reseñas</h3>" + evid if evid else ""}
  {f'<p class="err">Web: {e(r.web.error)}</p>' if r.web.error and r.web.error != "sin web" else ""}
</section>""")

    doc = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Demand Intent · Clínicas de estética</title>
<style>
 body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#222;background:#faf8f6}}
 h1{{margin-bottom:.2rem}} .sub{{color:#666;margin-top:0}}
 .card{{background:#fff;border-radius:12px;padding:1.2rem 1.4rem;margin:1rem 0;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
 .card header{{display:flex;align-items:center;gap:.8rem;flex-wrap:wrap}}
 .card h2{{margin:0;font-size:1.2rem;flex:1}} .rank{{color:#999;font-weight:600}}
 .badge{{color:#fff;padding:.25rem .7rem;border-radius:999px;font-size:.85rem;font-weight:600}}
 .meta{{color:#666;font-size:.9rem}} h3{{font-size:.95rem;margin:1rem 0 .3rem;color:#555}}
 .msg{{background:#f3efe9;border-left:4px solid #c9a27e;padding:.7rem 1rem;border-radius:6px}}
 blockquote{{margin:.4rem 0;padding:.4rem .8rem;border-left:3px solid #d64545;color:#444;font-style:italic}}
 .err{{color:#b00;font-size:.85rem}}
</style></head><body>
<h1>Demand Intent · Clínicas de estética</h1>
<p class="sub">{date.today().isoformat()} · {len(results)} cuentas analizadas · {hot} calientes · {warm} templadas</p>
{''.join(cards)}
</body></html>"""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
