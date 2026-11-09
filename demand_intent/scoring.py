"""Scoring FIT + INTENT y ángulo de entrada para cada clínica."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config
from .collectors import ReviewSignals, WebSignals


PAIN_LABELS = {
    "telefono_no_atendido": "teléfono sin atender",
    "respuesta_lenta": "respuesta lenta",
    "problemas_agenda": "problemas con la agenda",
    "whatsapp_mensajes": "mensajes de WhatsApp/Instagram",
}


@dataclass
class Account:
    nombre: str
    web: str = ""
    telefono: str = ""
    direccion: str = ""
    categoria: str = ""
    valoracion: float | None = None
    num_resenas: int | None = None
    instagram: str = ""
    notas: str = ""
    resenas: list[str] = field(default_factory=list)


@dataclass
class ScoredAccount:
    account: Account
    web: WebSignals
    reviews: ReviewSignals
    fit: int = 0
    intent: int = 0
    total: int = 0
    temperatura: str = ""
    motivos: list[str] = field(default_factory=list)
    angulo: str = ""
    mensaje_apertura: str = ""


def _to_float(v) -> float | None:
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _to_int(v) -> int | None:
    try:
        return int(float(str(v).replace(".", "").replace(",", ".")))
    except (TypeError, ValueError):
        return None


def account_from_row(row: dict) -> Account:
    from .collectors import split_reviews
    return Account(
        nombre=(row.get("nombre") or "").strip(),
        web=(row.get("web") or "").strip(),
        telefono=(row.get("telefono") or "").strip(),
        direccion=(row.get("direccion") or "").strip(),
        categoria=(row.get("categoria") or "").strip(),
        valoracion=_to_float(row.get("valoracion")),
        num_resenas=_to_int(row.get("num_resenas")),
        instagram=(row.get("instagram") or "").strip(),
        notas=(row.get("notas") or "").strip(),
        resenas=split_reviews(row.get("resenas", "")),
    )


def score(account: Account, web: WebSignals, reviews: ReviewSignals) -> ScoredAccount:
    w = config.WEIGHTS
    s = ScoredAccount(account=account, web=web, reviews=reviews)
    fit = intent = 0
    m = s.motivos

    # ------------------------------ FIT ------------------------------------
    location_text = f"{account.direccion} {account.nombre}".lower()
    if any(c in location_text for c in config.TARGET_CITIES) or web.city_mentions:
        fit += w["fit_ciudad_objetivo"]
        m.append("Ubicada en Sevilla o área metropolitana")

    cat_text = f"{account.categoria} {account.nombre}".lower()
    if web.is_aesthetic or any(k in cat_text for k in config.AESTHETIC_KEYWORDS):
        fit += w["fit_categoria_estetica"]
        m.append("Encaja en estética / medicina estética")

    if web.high_ticket:
        fit += w["fit_alto_ticket"]
        m.append(f"Tratamientos de ticket alto: {', '.join(web.high_ticket[:3])}")

    n = account.num_resenas or 0
    if n >= 300:
        fit += w["fit_volumen_resenas"]
        m.append(f"{n} reseñas en Google: volumen alto de clientes")
    elif n >= 100:
        fit += round(w["fit_volumen_resenas"] * 0.6)
        m.append(f"{n} reseñas en Google: volumen medio")
    elif n >= 30:
        fit += round(w["fit_volumen_resenas"] * 0.3)

    if web.multi_location:
        fit += w["fit_varias_sedes"]
        m.append("Varias sedes: la coordinación de agenda se complica")

    # ----------------------------- INTENT ----------------------------------
    if web.ok:
        if not web.booking_tools:
            intent += w["intent_sin_reserva_online"]
            m.append("Sin reserva online detectada: las citas entran a mano")
        if web.manual_booking:
            intent += w["intent_reserva_manual"]
            m.append("La web pide llamar o rellenar formulario para la cita")
        if not web.chat_tools:
            intent += w["intent_sin_chat"]
            m.append("Sin chat ni agente en la web: nadie responde fuera de horario")
        if web.has_whatsapp and not web.chat_tools:
            intent += w["intent_whatsapp_manual"]
            m.append("WhatsApp atendido a mano (sin bot detectado)")
        if web.hiring:
            intent += w["intent_contratando"]
            m.append("Está contratando: señal de crecimiento o de saturación")
    elif account.web.strip().upper() == "NO":
        # Sin web confirmado: dolor casi seguro, pero menos información
        intent += round(w["intent_sin_reserva_online"] * 0.7)
        m.append("Sin web: toda la captación depende del teléfono e Instagram")
    elif not account.web:
        m.append("Web sin revisar: falta añadir la URL para medir la intención")

    if reviews.pain_reviews:
        # 1 reseña = 50 %, 2 = 80 %, 3+ = 100 % del peso
        factor = {1: 0.5, 2: 0.8}.get(reviews.pain_reviews, 1.0)
        intent += round(w["intent_dolor_resenas"] * factor)
        tipos = ", ".join(PAIN_LABELS.get(k, k) for k in reviews.pain_by_type)
        m.append(f"{reviews.pain_reviews} reseña(s) quejándose de: {tipos}")

    s.fit = min(fit, config.MAX_FIT)
    s.intent = min(intent, config.MAX_INTENT)
    s.total = s.fit + s.intent
    if s.total >= config.HOT_THRESHOLD:
        s.temperatura = "CALIENTE"
    elif s.total >= config.WARM_THRESHOLD:
        s.temperatura = "TEMPLADA"
    else:
        s.temperatura = "FRÍA"

    s.angulo, s.mensaje_apertura = build_angle(s)
    return s


def build_angle(s: ScoredAccount) -> tuple[str, str]:
    """Elige el dolor más fuerte y redacta un primer mensaje (DM / WhatsApp).

    Estructura: dato concreto observado -> escena sensorial -> pregunta abierta.
    Sin vender en el primer mensaje: el objetivo es conseguir respuesta.
    """
    nombre = s.account.nombre or "vuestra clínica"
    pain = s.reviews.pain_by_type

    if pain.get("telefono_no_atendido") or pain.get("respuesta_lenta"):
        angulo = "Llamadas y mensajes sin responder (lo dicen sus propias reseñas)"
        msg = (f"Hola, equipo de {nombre}. Leyendo vuestras reseñas de Google he visto a "
               f"clientas comentar que les cuesta que les cojan el teléfono. Imagino la "
               f"escena: cabina ocupada, el móvil vibrando en recepción y nadie libre para "
               f"contestar. ¿Cuántas llamadas calculáis que se os quedan sin atender en "
               f"una semana normal?")
    elif pain.get("problemas_agenda"):
        angulo = "Errores y huecos en la agenda"
        msg = (f"Hola, equipo de {nombre}. En vuestras reseñas aparecen quejas por "
               f"cambios o esperas en las citas. Ese hueco de las 17:00 que se queda "
               f"vacío porque nadie confirmó la cita a tiempo es dinero que no vuelve. "
               f"¿Cómo confirmáis ahora las citas del día siguiente?")
    elif s.web.ok and not s.web.booking_tools and (s.web.manual_booking or s.web.has_whatsapp):
        angulo = "La cita solo se pide llamando o por WhatsApp"
        msg = (f"Hola, equipo de {nombre}. He entrado en vuestra web un domingo por la "
               f"noche, que es cuando muchas clientas miran tratamientos, y para pedir cita "
               f"hay que llamar o escribir y esperar a que abráis el lunes. ¿Qué parte de "
               f"esos mensajes del fin de semana termina convirtiéndose en cita?")
    elif s.web.hiring:
        angulo = "Están contratando: el volumen supera al equipo"
        msg = (f"Hola, equipo de {nombre}. He visto que estáis buscando incorporar gente "
               f"al equipo, enhorabuena por el crecimiento. Cuando entra más volumen, lo "
               f"primero que se satura es la recepción. ¿Quién se encarga ahora de "
               f"responder WhatsApp e Instagram mientras atendéis en cabina?")
    elif s.web.ok and not s.web.chat_tools:
        angulo = "Nadie responde en la web fuera de horario"
        msg = (f"Hola, equipo de {nombre}. Una consulta que llega a las 22:00 sobre un "
               f"tratamiento de ácido hialurónico se enfría antes de que abráis por la "
               f"mañana; para entonces ya ha escrito a otras dos clínicas. ¿Cuántas "
               f"consultas os entran fuera de horario a la semana?")
    else:
        angulo = "Sin dolor claro detectado: tantear primero"
        msg = (f"Hola, equipo de {nombre}. Estoy hablando con clínicas de estética de "
               f"Sevilla sobre cómo gestionan citas y mensajes en temporada alta. ¿Qué es "
               f"lo que más tiempo os quita ahora mismo en recepción?")
    return angulo, msg
