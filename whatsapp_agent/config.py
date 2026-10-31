"""Configuración del agente. Todo se lee de variables de entorno (ver .env.example)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "si", "sí", "yes"}


def normalizar_telefono(numero: str) -> str:
    """Deja solo dígitos y quita el prefijo internacional 00 / +. Ej: '+34 600 11 22 33' -> '34600112233'."""
    digitos = "".join(c for c in (numero or "") if c.isdigit())
    return digitos[2:] if digitos.startswith("00") else digitos


# --- WhatsApp Cloud API (Meta) ---
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v23.0")
# Solo para pruebas locales: acepta webhooks sin firma de Meta. Nunca en producción.
PERMITIR_SIN_FIRMA = _bool("PERMITIR_SIN_FIRMA", False)

# --- Claude ---
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
CLAUDE_EFFORT = os.getenv("CLAUDE_EFFORT", "low")  # low | medium | high
MAX_HISTORIAL = int(os.getenv("MAX_HISTORIAL", "30"))  # mensajes de contexto por cliente

# --- Control ---
# Números (con prefijo de país, sin +) que pueden mandar comandos #on / #off por WhatsApp.
ADMIN_NUMEROS = {normalizar_telefono(n) for n in os.getenv("ADMIN_NUMEROS", "").split(",") if n.strip()}
# Clave del panel web /panel. Si está vacía, el panel queda desactivado.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
# Horas que el bot se calla en un chat cuando tú respondes a mano desde la app (modo coexistencia).
HORAS_PAUSA_MANUAL = float(os.getenv("HORAS_PAUSA_MANUAL", "12"))
# Máximo de respuestas del bot por cliente y hora (protege tu saldo de Claude ante abusos).
MAX_RESPUESTAS_HORA = int(os.getenv("MAX_RESPUESTAS_HORA", "30"))
# Estado con el que arranca la primera vez (luego manda lo guardado en la base de datos).
BOT_ACTIVO_INICIAL = _bool("BOT_ACTIVO_INICIAL", True)

# --- Negocio ---
NOMBRE_NEGOCIO = os.getenv("NOMBRE_NEGOCIO", "Agencia de Agentes IA")
NOMBRE_RESPONSABLE = os.getenv("NOMBRE_RESPONSABLE", "Rocío")
ENLACE_AGENDA = os.getenv("ENLACE_AGENDA", "")
ARCHIVO_CONOCIMIENTO = Path(os.getenv("ARCHIVO_CONOCIMIENTO", str(BASE_DIR / "conocimiento.md")))
RUTA_BD = Path(os.getenv("RUTA_BD", str(BASE_DIR / "data" / "agente.db")))
