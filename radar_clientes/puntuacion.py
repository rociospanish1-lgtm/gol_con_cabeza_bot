"""Puntuación 0-100 de probabilidad de compra, con motivos explicados.

Cada motivo lleva sus puntos para que veas POR QUÉ un lead está arriba
y puedas usar ese motivo en tu primer mensaje.
"""
from __future__ import annotations

from .analisis import AuditoriaWeb

NIVELES = [(60, "Caliente"), (35, "Templado"), (0, "Frío")]

GANCHOS = {
    "oferta": "He visto vuestra oferta de «{puesto}». Antes de cerrar la contratación, "
              "¿os interesa ver cómo un agente IA atiende llamadas y WhatsApp y agenda citas 24/7?",
    "telefono": "He leído en vuestras reseñas de Google que a algunos pacientes les cuesta "
                "contactar por teléfono. Eso es exactamente lo que resolvemos con un agente IA.",
    "mensajes": "He visto en vuestras reseñas que algunos mensajes tardan en responderse. "
                "Un agente IA contesta WhatsApp e Instagram en segundos, también de noche.",
    "citas": "Varias reseñas mencionan problemas con las citas (cambios, recordatorios). "
             "Automatizamos confirmaciones y recordatorios para reducir ausencias.",
    "sin_reservas": "En vuestra web se pide cita por teléfono o formulario. Cada cita que "
                    "llega fuera de horario es una cita que se puede perder.",
    "sin_web": "He visto que todas vuestras citas entran por teléfono o redes. Un agente IA "
               "puede responder y agendar por WhatsApp aunque no tengáis web.",
    "whatsapp": "Veo que atendéis por WhatsApp. ¿Cuántos mensajes os llegan al día fuera de "
                "horario? Un agente IA los responde y agenda sin que nadie del equipo intervenga.",
    "volumen": "Con vuestro volumen de reseñas, calculo que recibís muchas consultas al día. "
               "Os enseño cómo automatizar las repetitivas en 15 minutos.",
}


def puntuar(*, auditoria: AuditoriaWeb | None, quejas: dict[str, list[str]],
            num_resenas: int | None, valoracion: float | None,
            ofertas: list[dict], tiene_web: bool) -> dict:
    motivos: list[tuple[int, str, str]] = []  # (puntos, clave_gancho, texto)

    if ofertas:
        puestos = ", ".join(sorted({o["titulo"] for o in ofertas}))[:120]
        motivos.append((30, "oferta", f"Contratando personal de atención/agenda: {puestos}"))

    n_tel = len(quejas.get("telefono", []))
    if n_tel:
        motivos.append((min(10 + 8 * n_tel, 30), "telefono",
                        f"{n_tel} reseña(s) se quejan de que no cogen el teléfono"))
    n_msg = len(quejas.get("mensajes", []))
    if n_msg:
        motivos.append((min(8 + 6 * n_msg, 20), "mensajes",
                        f"{n_msg} reseña(s) se quejan de respuestas lentas por mensaje"))
    n_cita = len(quejas.get("citas", []))
    if n_cita:
        motivos.append((min(8 + 6 * n_cita, 20), "citas",
                        f"{n_cita} reseña(s) mencionan problemas con las citas"))

    if auditoria and auditoria.accesible:
        if not auditoria.reservas:
            motivos.append((20, "sin_reservas", "Su web no tiene sistema de reserva online"))
        if auditoria.whatsapp and not auditoria.chatbots:
            motivos.append((10, "whatsapp", "Atiende por WhatsApp de forma manual (botón en la web, sin bot)"))
        if auditoria.chatbots:
            motivos.append((-20, "", f"Ya tiene chat/bot: {', '.join(auditoria.chatbots)}"))
        if auditoria.reservas:
            motivos.append((0, "", f"Usa reservas online: {', '.join(auditoria.reservas)} "
                                   "(argumento: integración con WhatsApp/llamadas)"))
    elif not tiene_web:
        motivos.append((10, "sin_web", "No tiene web: todas las citas entran por teléfono/redes"))

    if num_resenas:
        if num_resenas >= 150:
            motivos.append((15, "volumen", f"Alto volumen: {num_resenas} reseñas en Google"))
        elif num_resenas >= 50:
            motivos.append((8, "volumen", f"Volumen medio: {num_resenas} reseñas en Google"))
        elif num_resenas < 10:
            motivos.append((-5, "", f"Poco volumen: {num_resenas} reseñas (negocio pequeño)"))

    if valoracion is not None and valoracion < 4.2 and (n_tel or n_msg or n_cita):
        motivos.append((5, "", f"Valoración {valoracion} con quejas de atención en reseñas"))

    total = max(0, min(100, sum(p for p, _, _ in motivos)))
    nivel = next(n for umbral, n in NIVELES if total >= umbral)

    gancho = ""
    for _, clave, _ in sorted(motivos, key=lambda m: -m[0]):
        if clave in GANCHOS:
            puesto = ofertas[0]["titulo"] if (clave == "oferta" and ofertas) else ""
            gancho = GANCHOS[clave].format(puesto=puesto)
            break

    return {
        "puntuacion": total,
        "nivel": nivel,
        "motivos": [{"puntos": p, "texto": t} for p, _, t in sorted(motivos, key=lambda m: -m[0])],
        "gancho": gancho,
    }
