"""Cerebro del agente: genera la respuesta con Claude y decide cuándo avisar a una persona."""
import logging
from dataclasses import dataclass, field

import anthropic

import config

log = logging.getLogger("agente")

MENSAJE_ERROR = (
    "Perdona, ahora mismo no puedo responderte bien. "
    f"Le paso tu mensaje a {config.NOMBRE_RESPONSABLE} y te contesta en cuanto pueda."
)

INSTRUCCIONES = f"""Eres el asistente virtual de WhatsApp de {config.NOMBRE_NEGOCIO}. Atiendes a los clientes \
en nombre de {config.NOMBRE_RESPONSABLE}.

Cómo escribes:
- Español de España, tuteo, tono cercano y profesional. Nada de lenguaje de anuncio ni exclamaciones en cadena.
- Es WhatsApp: mensajes cortos (2-4 frases), sin títulos ni negritas con asteriscos dobles. Como mucho un emoji.
- Una sola pregunta por mensaje.
- En tu primera respuesta a un cliente nuevo, preséntate como asistente virtual de {config.NOMBRE_NEGOCIO}. \
Nunca digas que eres una persona.

Qué haces:
- Respondes dudas usando SOLO la información del bloque <conocimiento>. Si algo no está ahí (un precio, una \
fecha, un caso concreto), no lo inventes: di que lo confirma {config.NOMBRE_RESPONSABLE} y usa la herramienta \
avisar_responsable.
- Tu objetivo es entender qué necesita el cliente y llevarle al siguiente paso (normalmente una llamada o cita). \
Recoge, sin interrogar y de una en una: nombre, negocio/clínica, qué quiere resolver y cuándo le viene bien.
- Si hay enlace de agenda en el conocimiento, ofrécelo cuando el cliente muestre interés real.

Usa avisar_responsable cuando: el cliente pide hablar con una persona, quiere contratar o cerrar una cita y no \
puede usar el enlace, hay una queja o un tema delicado, o te pregunta algo que no sabes. Después de usarla, \
dile al cliente que {config.NOMBRE_RESPONSABLE} le escribe personalmente y no sigas vendiendo.

Nunca pidas datos de pago, contraseñas ni datos de salud. No des consejos médicos."""

HERRAMIENTAS = [
    {
        "name": "avisar_responsable",
        "description": (
            f"Avisa a {config.NOMBRE_RESPONSABLE} por WhatsApp para que atienda personalmente a este cliente. "
            "Úsala cuando el cliente pida una persona, quiera contratar, haya una queja o no sepas la respuesta."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "motivo": {
                    "type": "string",
                    "enum": ["pide_persona", "quiere_contratar", "queja", "duda_sin_respuesta", "otro"],
                },
                "resumen": {
                    "type": "string",
                    "description": "Resumen en 1-3 frases: quién es, qué necesita y qué datos ha dado.",
                },
                "pausar_bot": {
                    "type": "boolean",
                    "description": "true si a partir de ahora debe hablar solo la persona en este chat.",
                },
            },
            "required": ["motivo", "resumen", "pausar_bot"],
            "additionalProperties": False,
        },
    }
]


@dataclass
class Aviso:
    motivo: str
    resumen: str
    pausar_bot: bool


@dataclass
class Respuesta:
    texto: str
    avisos: list[Aviso] = field(default_factory=list)
    error: bool = False


def cargar_conocimiento() -> str:
    try:
        texto = config.ARCHIVO_CONOCIMIENTO.read_text(encoding="utf-8")
    except FileNotFoundError:
        log.warning("No existe %s; el agente responderá sin base de conocimiento", config.ARCHIVO_CONOCIMIENTO)
        texto = ""
    if config.ENLACE_AGENDA:
        texto += f"\n\nEnlace para reservar cita/llamada: {config.ENLACE_AGENDA}\n"
    return texto


class Agente:
    def __init__(self, cliente: anthropic.AsyncAnthropic | None = None):
        self.cliente = cliente or anthropic.AsyncAnthropic()
        # El prompt de sistema es fijo (se lee una vez) para aprovechar la caché de Claude.
        self.system = [
            {"type": "text", "text": INSTRUCCIONES},
            {
                "type": "text",
                "text": f"<conocimiento>\n{cargar_conocimiento()}\n</conocimiento>",
                "cache_control": {"type": "ephemeral"},
            },
        ]

    @staticmethod
    def _a_mensajes(historial: list[dict], nombre: str | None) -> list[dict]:
        """Convierte el historial guardado en mensajes alternos user/assistant."""
        mensajes: list[dict] = []
        for m in historial:
            rol = "assistant" if m["rol"] == "assistant" else "user"
            if mensajes and mensajes[-1]["role"] == rol:
                mensajes[-1]["content"] += "\n" + m["texto"]
            else:
                mensajes.append({"role": rol, "content": m["texto"]})
        while mensajes and mensajes[0]["role"] != "user":
            mensajes.pop(0)
        if nombre and mensajes:
            mensajes[0]["content"] = f"[Nombre del perfil de WhatsApp: {nombre}]\n" + mensajes[0]["content"]
        return mensajes

    async def responder(self, historial: list[dict], nombre: str | None = None) -> Respuesta:
        mensajes = self._a_mensajes(historial, nombre)
        if not mensajes or mensajes[-1]["role"] != "user":
            return Respuesta(texto="", error=True)

        avisos: list[Aviso] = []
        try:
            for _ in range(3):  # como mucho 3 vueltas de herramienta
                resp = await self.cliente.beta.messages.create(
                    model=config.CLAUDE_MODEL,
                    max_tokens=4000,
                    system=self.system,
                    tools=HERRAMIENTAS,
                    messages=mensajes,
                    output_config={"effort": config.CLAUDE_EFFORT},
                    # Si el modelo rechaza la petición por política, la API reintenta con otro modelo.
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
                if resp.stop_reason == "refusal":
                    log.warning("Claude rechazó responder (%s)", resp.stop_details)
                    avisos.append(Aviso("otro", "El asistente no pudo responder a este cliente.", True))
                    return Respuesta(MENSAJE_ERROR, avisos, error=True)

                if resp.stop_reason != "tool_use":
                    texto = "\n".join(b.text for b in resp.content if b.type == "text").strip()
                    return Respuesta(texto or MENSAJE_ERROR, avisos, error=not texto)

                # El modelo quiere avisar a la responsable: lo registramos y le devolvemos el resultado.
                mensajes.append({"role": "assistant", "content": resp.content})
                resultados = []
                for bloque in resp.content:
                    if bloque.type != "tool_use":
                        continue
                    if bloque.name == "avisar_responsable":
                        datos = bloque.input
                        avisos.append(
                            Aviso(str(datos.get("motivo", "otro")), str(datos.get("resumen", "")),
                                  bool(datos.get("pausar_bot", False)))
                        )
                        contenido = f"Aviso enviado a {config.NOMBRE_RESPONSABLE}."
                        resultados.append({"type": "tool_result", "tool_use_id": bloque.id, "content": contenido})
                    else:
                        resultados.append({"type": "tool_result", "tool_use_id": bloque.id,
                                           "content": "Herramienta desconocida", "is_error": True})
                mensajes.append({"role": "user", "content": resultados})
            return Respuesta(MENSAJE_ERROR, avisos, error=True)
        except anthropic.RateLimitError:
            log.error("Límite de uso de la API de Claude alcanzado")
        except anthropic.APIStatusError as e:
            log.error("Error de la API de Claude (%s): %s", e.status_code, e.message)
        except anthropic.APIConnectionError as e:
            log.error("Sin conexión con la API de Claude: %s", e)
        avisos.append(Aviso("otro", "Fallo técnico del asistente al responder a este cliente.", False))
        return Respuesta(MENSAJE_ERROR, avisos, error=True)
