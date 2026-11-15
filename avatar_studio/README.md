# Avatar Studio

Clon sencillo de un generador de vídeos con avatar hablando (tipo HeyGen).
Subes una foto, escribes el guion, eliges voz → vídeo MP4 vertical 9:16 con subtítulos.

## Arrancar
    cd avatar_studio
    pip install -r requirements.txt     # requiere ffmpeg instalado
    uvicorn app:app --port 8000         # abre http://localhost:8000

## Variables de entorno
| Variable | Efecto |
|---|---|
| `DID_API_KEY` | Activa sincronía labial real vía D-ID (sin ella, modo local) |
| `TTS_PROVIDER` | `edge` (por defecto, voces neuronales gratis) o `mock` (pruebas sin red) |
| `DATA_DIR` | Carpeta de salida (por defecto `./data`) |

## Qué hace cada modo
- **Local (por defecto):** foto con zoom lento + voz + subtítulos palabra a palabra. **No mueve los labios.**
- **D-ID:** el avatar habla con sincronía labial. Ruta `render_did` en `pipeline.py`; no probada contra la API real.

## Limitaciones
- Los trabajos se guardan en memoria: reiniciar el servidor pierde el historial.
- Sin autenticación ni límites por usuario: no exponer a internet tal cual.
