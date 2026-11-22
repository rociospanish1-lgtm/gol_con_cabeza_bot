# Analizador de vídeos virales

Le pasas el enlace de un vídeo (TikTok, YouTube Shorts, Instagram) y te dice si es viral de verdad,
por qué ha funcionado y si el mecanismo sirve para captar clínicas de estética en Sevilla.

## Instalación (en tu ordenador, una vez)
    pip install -r requirements.txt
    # ffmpeg (necesario para Whisper): Windows `winget install Gyan.FFmpeg` · Mac `brew install ffmpeg`

## Uso
    python analizar_viral.py "https://www.tiktok.com/@cuenta/video/123"
    python analizar_viral.py URL --cuenta                  # compara con el resto de vídeos de la cuenta
    python analizar_viral.py URL --cookies-navegador chrome # Instagram que pide login
    python analizar_viral.py URL --claude                  # añade análisis + guion con Claude (ANTHROPIC_API_KEY)
    python analizar_viral.py --json ejemplo.json           # prueba sin red

El informe queda en `informes/*.md`.

## Qué mide
- Viral si cumple una: visitas/seguidores ≥ 3, visitas ≥ 10x la mediana de la cuenta, engagement ≥ 5 %.
- Gancho 0-3 s, mecanismo (error común, miedo a perder dinero, lista, demo, POV…), CTA, estructura por tramos.
- Adaptabilidad 0-10 al nicho: HACER ≥ 7.5 · ADAPTAR 5-7.4 · DESCARTAR < 5.

## Límites
- Debe ejecutarse en tu ordenador: desde la nube YouTube/TikTok están bloqueados.
- La detección de mecanismo y la puntuación son por palabras clave sobre la transcripción: es una criba.
  Los motivos de fondo (contexto, momento, elemento visual) salen mejor con `--claude`.
- Instagram suele exigir sesión iniciada; si falla, usa `--cookies-navegador`.
