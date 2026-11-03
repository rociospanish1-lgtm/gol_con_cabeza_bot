"""CLI: python -m asmr_creator --preset clinica --duracion 30 --texto "..." -o video.mp4"""

import argparse
import sys

from .audio import CAPAS
from .presets import FORMATOS, PRESETS
from .render import Config, crear
from .visuals import ESTILOS, PALETAS


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="asmr_creator",
        description="Crea vídeos ASMR (audio binaural sintetizado + visual en bucle) listos para Reels/TikTok.")
    ap.add_argument("-o", "--salida", default="asmr.mp4", help="archivo de salida (.mp4, o .wav/.mp3 con --solo-audio)")
    ap.add_argument("-p", "--preset", default="clinica", choices=list(PRESETS))
    ap.add_argument("-d", "--duracion", type=float, default=30, help="segundos (3-3600). Por defecto 30")
    ap.add_argument("-f", "--formato", default="vertical", choices=list(FORMATOS))
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--capas", help="mezcla propia, p. ej. 'lluvia:0.8,cristal:0.5'")
    ap.add_argument("--estilo", choices=list(ESTILOS), help="estilo visual procedural")
    ap.add_argument("--paleta", help=f"nombre ({', '.join(PALETAS)}) o colores '#1f1a1c,#6b4f57,#f3d5cf'")
    ap.add_argument("--fondo", help="foto (.jpg/.png) o vídeo (.mp4/.mov) propio de fondo")
    ap.add_argument("--voz", help="audio con tu voz/susurro (cualquier formato que lea ffmpeg)")
    ap.add_argument("--volumen-voz", type=float, default=1.0)
    ap.add_argument("--texto", help="texto gancho en pantalla (usa \\n para salto de línea)")
    ap.add_argument("--texto-seg", type=float, default=0, help="segundos que se ve el texto (0 = siempre)")
    ap.add_argument("--marca", help="firma pequeña, p. ej. @tuagencia")
    ap.add_argument("--fuente", help="ruta a .ttf/.otf para el texto")
    ap.add_argument("--semilla", type=int, default=7, help="cambia el número para otra variación")
    ap.add_argument("--sin-bucle", action="store_true", help="fundidos de entrada/salida en vez de bucle perfecto")
    ap.add_argument("--sin-portada", action="store_true", help="no exportar la portada .jpg")
    ap.add_argument("--calidad", type=int, default=20, help="CRF x264, 18 (mejor) – 28 (más ligero)")
    ap.add_argument("--lufs", type=float, default=-16.0, help="volumen integrado objetivo")
    ap.add_argument("--solo-audio", action="store_true", help="exportar solo el audio")
    ap.add_argument("--lista", action="store_true", help="mostrar presets, capas y estilos")
    a = ap.parse_args(argv)

    if a.lista:
        print("PRESETS")
        for k, v in PRESETS.items():
            print(f"  {k:<10} {v['descripcion']}")
        print("\nCAPAS DE SONIDO\n  " + ", ".join(CAPAS))
        print("\nESTILOS VISUALES\n  " + ", ".join(ESTILOS))
        print("\nPALETAS\n  " + "\n  ".join(f"{k:<8} {' '.join(v)}" for k, v in PALETAS.items()))
        return 0

    cfg = Config(
        salida=a.salida, preset=a.preset, duracion=a.duracion, formato=a.formato, fps=a.fps, capas=a.capas,
        estilo=a.estilo, paleta=a.paleta, fondo=a.fondo, voz=a.voz, volumen_voz=a.volumen_voz, texto=a.texto,
        texto_seg=a.texto_seg, marca=a.marca, fuente=a.fuente, semilla=a.semilla, bucle=not a.sin_bucle,
        portada=not a.sin_portada, calidad=a.calidad, lufs=a.lufs, solo_audio=a.solo_audio,
    )
    try:
        crear(cfg)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
