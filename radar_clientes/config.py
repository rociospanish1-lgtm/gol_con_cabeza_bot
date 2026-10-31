"""Configuración del Radar de Clientes.

Las claves de API se leen de variables de entorno. Ninguna es obligatoria:
sin claves, el radar usa OpenStreetMap (gratis) y el análisis de webs.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("RADAR_DB", BASE_DIR / "radar.db"))

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "").strip()
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "").strip()

USER_AGENT = "RadarClientes/1.0 (prospeccion B2B; contacto: ver web de la agencia)"
HTTP_TIMEOUT = 12
MAX_BYTES_WEB = 1_500_000  # no descargamos más de 1,5 MB por web

# Valores por defecto: tu nicho actual
SECTOR_POR_DEFECTO = "clínica estética"
CIUDAD_POR_DEFECTO = "Sevilla"

# Búsquedas en ofertas de empleo: una clínica que contrata a alguien para
# coger el teléfono o gestionar la agenda es una clínica que paga hoy por
# lo que un agente IA hace 24/7.
PUESTOS_SENAL = [
    "recepcionista",
    "atención al cliente",
    "gestión de citas",
    "auxiliar administrativo",
    "coordinadora de clínica",
]
