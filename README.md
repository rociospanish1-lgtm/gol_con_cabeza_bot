# gol_con_cabeza_bot

Bot de Telegram + **creador de vídeos ASMR** (`asmr_creator/`).

---

## Creador de vídeos ASMR

Genera vídeos ASMR completos —audio binaural + visual + texto— listos para Reels, TikTok o YouTube.
Todo el sonido se **sintetiza por código** (sin bancos de sonido ni derechos de autor) y el vídeo
**se repite en bucle sin salto**, lo que aumenta el tiempo de visionado en Reels/TikTok.

### Qué incluye

| Parte | Detalle |
|---|---|
| 13 capas de sonido | lluvia, olas, fuego, ruido blanco/rosa/marrón, toques (madera), uñas, cristal, cepillado, tecleo, gotas, burbujas |
| Audio binaural | panorama de potencia constante + retardo interaural (hasta 0,65 ms): con auriculares los sonidos se oyen a izquierda/derecha |
| 4 estilos visuales | `bokeh`, `seda`, `lluvia`, `brasas` — reaccionan al volumen del audio |
| Fondo propio | foto (zoom lento tipo Ken Burns) o vídeo (en bucle) |
| Voz propia | tu susurro grabado en el móvil; el fondo baja ~6 dB cuando hablas |
| Texto | gancho arriba + firma (`@usuario`), con sombra para leerse sobre cualquier fondo |
| Formatos | vertical 1080×1920, cuadrado 1080×1080, horizontal 1920×1080 |
| Volumen | normalizado a −16 LUFS, pico real ≤ −1,5 dBTP |
| Portada | exporta `nombre_portada.jpg` automáticamente |

### Instalación

Requisitos: Python 3.10+ y [ffmpeg](https://ffmpeg.org/download.html).

```bash
# macOS:   brew install ffmpeg
# Ubuntu:  sudo apt install ffmpeg
pip install -r requirements.txt
```

### Uso (línea de comandos)

```bash
# Ver presets, capas, estilos y paletas
python -m asmr_creator --lista

# Vídeo de 30 s para clínica estética, vertical
python -m asmr_creator -p clinica -d 30 \
  --texto "Así suena tu primera limpieza facial" \
  --marca "@tuagencia" -o clinica.mp4

# Con tu foto de fondo y tus colores de marca
python -m asmr_creator -p clinica -d 30 --fondo cabina.jpg \
  --paleta "#1f1a1c,#6b4f57,#f3d5cf,#e8b4a8" -o cabina.mp4

# Con tu voz susurrada (grabada en el móvil)
python -m asmr_creator -p toques -d 45 --voz susurro.m4a -o voz.mp4

# Mezcla propia de sonidos
python -m asmr_creator --capas "lluvia:0.6,cristal:0.8,cepillado:1" -d 60 -o mezcla.mp4

# Solo audio (para Spotify/YouTube Music o para montar en CapCut)
python -m asmr_creator -p dormir -d 600 --solo-audio -o dormir.mp3

# Otra variación del mismo preset
python -m asmr_creator -p clinica --semilla 42 -o variante.mp4
```

### Presets

| Preset | Sonido | Visual |
|---|---|---|
| `clinica` | frascos de cristal, brocha facial, gotas de sérum | bokeh nude/rosa |
| `lluvia` | lluvia sobre cristal | lluvia + luces |
| `chimenea` | fuego con chasquidos | brasas |
| `mar` | olas de oído a oído | seda azul |
| `toques` | tapping yemas + uñas | bokeh lavanda |
| `estudio` | teclado mecánico + lluvia | lluvia |
| `burbujas` | burbujas + gotas | seda lavanda |
| `dormir` | ruido marrón + olas suaves | seda noche |

### Uso desde Telegram

El bot incluye los comandos:

- `/asmr [preset] [segundos] [texto]` → ej. `/asmr clinica 30 Así suena tu primera sesión`
- Enviar una **foto** con el pie `/asmr clinica 20 texto` → usa la foto como fondo.
- `/asmr_ayuda` → lista de presets.

Variables de entorno opcionales: `ASMR_MAX_SEG` (límite de segundos, por defecto 60) y
`ASMR_MARCA` (firma que se añade a todos los vídeos, p. ej. `@tuagencia`).

### Rendimiento

En un portátil de 4 núcleos: ~1,5 s de render por cada segundo de vídeo 1080×1920 (30 s ≈ 45 s).
Un vídeo de 30 s ocupa ~7-8 MB (límite de subida de bots de Telegram: 50 MB).

### Tests

```bash
python -m unittest tests.test_asmr -v
```
