"""Señales, pesos y diccionarios de Demand Intent para clínicas de estética.

Todo lo ajustable vive aquí: si una señal resulta no predecir cierres,
se baja su peso sin tocar el resto del código.
"""

# ---------------------------------------------------------------------------
# 1. Tecnología detectada en la web (huella en el HTML)
# ---------------------------------------------------------------------------

# Software de reservas online. Si la clínica YA lo tiene, el dolor de agenda
# es menor (pero sigue habiendo hueco para el agente que atiende y confirma).
BOOKING_TECH = {
    "Treatwell": ["treatwell"],
    "Booksy": ["booksy.com"],
    "Fresha": ["fresha.com"],
    "Doctoralia": ["doctoralia"],
    "Flowww": ["flowww"],
    "Koibox": ["koibox"],
    "Bookitit": ["bookitit"],
    "Calendly": ["calendly.com"],
    "Reservio": ["reservio"],
    "SimplyBook": ["simplybook"],
    "Timify": ["timify"],
    "Agendapro": ["agendapro"],
    "Clinic Cloud": ["cliniccloud"],
    "Noona": ["noona."],
}

# Chat / agente ya instalado. Si lo tiene, el hueco es más pequeño.
CHAT_TECH = {
    "Tidio": ["tidio"],
    "Intercom": ["intercom"],
    "Crisp": ["crisp.chat"],
    "ManyChat": ["manychat"],
    "Zendesk": ["zdassets", "zendesk"],
    "HubSpot Chat": ["js.hs-scripts", "hubspot"],
    "Landbot": ["landbot"],
    "Tawk.to": ["tawk.to"],
    "Chatwoot": ["chatwoot"],
    "Botpress": ["botpress"],
    "Voiceflow": ["voiceflow"],
}

WHATSAPP_PATTERNS = ["wa.me/", "api.whatsapp.com", "whatsapp://", "web.whatsapp.com"]

# Frases que indican que la cita se pide "a mano" (teléfono/formulario).
MANUAL_BOOKING_PHRASES = [
    "pide tu cita llamando",
    "llámanos para pedir cita",
    "llamanos para pedir cita",
    "solicita tu cita",
    "pide cita por teléfono",
    "pide cita por telefono",
    "reserva tu cita llamando",
    "te llamaremos",
    "nos pondremos en contacto",
    "rellena el formulario",
    "déjanos tus datos",
    "dejanos tus datos",
    "pedir cita",
]

# Señal de crecimiento / contratación (más volumen = más necesidad).
HIRING_PHRASES = [
    "trabaja con nosotros",
    "únete al equipo",
    "unete al equipo",
    "buscamos recepcionista",
    "oferta de empleo",
    "estamos contratando",
    "envía tu cv",
    "envia tu cv",
]

# Tratamientos de alto ticket = más valor por cita perdida.
HIGH_TICKET_TREATMENTS = [
    "ácido hialurónico", "acido hialuronico", "botox", "toxina botulínica",
    "toxina botulinica", "rinomodelación", "rinomodelacion", "hilos tensores",
    "depilación láser", "depilacion laser", "láser", "laser", "mesoterapia",
    "radiofrecuencia", "hifu", "presoterapia", "peeling", "bioestimuladores",
    "carboxiterapia", "lipoláser", "lipolaser", "criolipólisis", "criolipolisis",
    "medicina estética", "medicina estetica", "micropigmentación", "micropigmentacion",
]

# ---------------------------------------------------------------------------
# 2. Reseñas: frases que delatan dolor de atención al cliente / agenda
# ---------------------------------------------------------------------------

REVIEW_PAIN = {
    "telefono_no_atendido": [
        "no cogen el teléfono", "no cogen el telefono", "no coge el teléfono",
        "no coge el telefono", "no contestan", "no contesta", "nadie contesta",
        "imposible contactar", "imposible hablar", "no hay quien", "comunica todo el rato",
        "no responden", "no responde", "nunca contestan",
    ],
    "respuesta_lenta": [
        "tardan en responder", "tardaron días", "tardaron dias", "tardan días",
        "tardan dias", "me respondieron a los", "sin respuesta", "no me han respondido",
        "no me devolvieron la llamada", "no me llamaron", "nunca me llamaron",
        "quedaron en llamarme",
    ],
    "problemas_agenda": [
        "me cambiaron la cita", "anularon la cita", "cancelaron la cita",
        "se olvidaron de mi cita", "no tenían mi cita", "no tenian mi cita",
        "error con la cita", "lista de espera", "no hay citas", "imposible conseguir cita",
        "difícil conseguir cita", "dificil conseguir cita", "me tuvieron esperando",
        "esperando más de", "esperando mas de", "retraso",
    ],
    "whatsapp_mensajes": [
        "whatsapp", "mensaje y no", "mensajes sin", "dejé mensaje", "deje mensaje",
        "instagram y no", "por instagram",
    ],
}

# ---------------------------------------------------------------------------
# 3. Pesos del scoring (0-100 en total)
# ---------------------------------------------------------------------------
# FIT (máx 40): ¿se parece a mi cliente ideal?
# INTENT (máx 60): ¿tiene ahora el dolor que resuelvo?

WEIGHTS = {
    # FIT
    "fit_ciudad_objetivo": 10,
    "fit_categoria_estetica": 10,
    "fit_alto_ticket": 8,
    "fit_volumen_resenas": 7,       # proxy de nº de clientes
    "fit_varias_sedes": 5,
    # INTENT
    "intent_sin_reserva_online": 14,
    "intent_reserva_manual": 6,
    "intent_sin_chat": 8,
    "intent_whatsapp_manual": 5,    # tiene WhatsApp pero lo atiende una persona
    "intent_dolor_resenas": 20,     # escala con nº de reseñas con dolor
    "intent_contratando": 7,
}

MAX_FIT = 40
MAX_INTENT = 60

TARGET_CITIES = ["sevilla", "dos hermanas", "mairena del aljarafe", "tomares",
                 "bormujos", "alcalá de guadaíra", "alcala de guadaira",
                 "san juan de aznalfarache", "camas", "espartinas", "gines",
                 "utrera", "la rinconada", "écija", "ecija"]

AESTHETIC_KEYWORDS = ["estética", "estetica", "medicina estética", "medicina estetica",
                      "belleza", "beauty", "clínica", "clinica", "dermo", "láser", "laser",
                      "facial", "corporal"]

# Umbrales de temperatura
HOT_THRESHOLD = 65
WARM_THRESHOLD = 45
