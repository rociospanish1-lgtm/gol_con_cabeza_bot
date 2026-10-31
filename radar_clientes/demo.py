"""Datos de demostración FICTICIOS para ver el panel sin claves de API.

Los nombres llevan el prefijo [DEMO] y no corresponden a empresas reales.
Pasan por el mismo análisis y puntuación que los datos reales.
"""
from . import db
from .analisis import analizar_resenas, auditar_html
from .puntuacion import puntuar

WEB_SIN_RESERVAS = '<html><body><h1>Pide tu cita</h1><a href="https://wa.me/34600000000">WhatsApp</a>' \
                   '<form><input name="email"></form></body></html>'
WEB_CON_KOIBOX = '<html><body><script src="https://widget.koibox.cloud/x.js"></script></body></html>'
WEB_CON_BOT = '<html><body><script src="//code.tidio.co/abc.js"></script>' \
              '<script src="https://booksy.com/widget.js"></script></body></html>'

EJEMPLOS = [
    dict(nombre="[DEMO] Clínica Estética Ejemplo Nervión", direccion="Nervión, Sevilla",
         valoracion=4.1, num_resenas=212, web=WEB_SIN_RESERVAS,
         resenas=["El tratamiento genial pero no cogen el teléfono nunca, llamé varias veces.",
                  "Imposible contactar por teléfono, al final fui en persona.",
                  "Me cambiaron la cita dos veces y no me avisaron."],
         ofertas=[{"empresa": "Ejemplo Nervión", "titulo": "Recepcionista clínica estética",
                   "url": "", "fecha": "2026-10-20", "lugar": "Sevilla"}]),
    dict(nombre="[DEMO] Centro Médico Estético Ejemplo Triana", direccion="Triana, Sevilla",
         valoracion=4.6, num_resenas=96, web=WEB_SIN_RESERVAS,
         resenas=["Muy buen trato. Eso sí, tardan días en responder al WhatsApp."], ofertas=[]),
    dict(nombre="[DEMO] Instituto Láser Ejemplo Los Remedios", direccion="Los Remedios, Sevilla",
         valoracion=4.8, num_resenas=340, web=WEB_CON_KOIBOX,
         resenas=["Todo perfecto, reservé online en un minuto."], ofertas=[]),
    dict(nombre="[DEMO] Estética Ejemplo Centro", direccion="Centro, Sevilla",
         valoracion=4.9, num_resenas=58, web=WEB_CON_BOT, resenas=[], ofertas=[]),
    dict(nombre="[DEMO] Belleza Ejemplo Macarena", direccion="Macarena, Sevilla",
         valoracion=4.4, num_resenas=7, web=None, resenas=[], ofertas=[]),
]


def cargar() -> int:
    for i, e in enumerate(EJEMPLOS):
        auditoria = auditar_html(e["web"]) if e["web"] else None
        quejas = analizar_resenas(e["resenas"])
        r = puntuar(auditoria=auditoria, quejas=quejas, num_resenas=e["num_resenas"],
                    valoracion=e["valoracion"], ofertas=e["ofertas"], tiene_web=bool(e["web"]))
        db.guardar({
            "clave": f"demo:{i}", "nombre": e["nombre"], "sector": "clínica estética",
            "ciudad": "Sevilla", "direccion": e["direccion"], "telefono": "",
            "web": "https://ejemplo.invalid" if e["web"] else "", "maps_url": "",
            "valoracion": e["valoracion"], "num_resenas": e["num_resenas"],
            "fuentes": ["Demo"], "senales": {"quejas": quejas, "ofertas": e["ofertas"],
                                             "web": vars(auditoria) if auditoria else None},
            "motivos": r["motivos"], "gancho": r["gancho"], "puntuacion": r["puntuacion"],
            "nivel": r["nivel"], "demo": 1,
        })
    return len(EJEMPLOS)
