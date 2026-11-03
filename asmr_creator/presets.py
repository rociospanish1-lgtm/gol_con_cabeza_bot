"""Recetas listas para usar: capas de sonido + estilo visual + paleta."""

PRESETS = {
    "clinica": {
        "descripcion": "Frascos de cristal, brocha facial y gotas de sérum. Pensado para clínicas de estética.",
        "capas": [("cristal", 0.8), ("cepillado", 1.0), ("gotas", 0.6), ("ruido_rosa", 0.12)],
        "estilo": "bokeh", "paleta": "clinica",
    },
    "lluvia": {
        "descripcion": "Lluvia sobre cristal con goterones cercanos.",
        "capas": [("lluvia", 1.0), ("ruido_marron", 0.3)],
        "estilo": "lluvia", "paleta": "noche",
    },
    "chimenea": {
        "descripcion": "Fuego de leña con chasquidos binaurales.",
        "capas": [("fuego", 1.0), ("ruido_marron", 0.2)],
        "estilo": "brasas", "paleta": "calido",
    },
    "mar": {
        "descripcion": "Olas lentas que van de un oído a otro.",
        "capas": [("olas", 1.0)],
        "estilo": "seda", "paleta": "oceano",
    },
    "toques": {
        "descripcion": "Tapping con yemas y uñas alternando izquierda/derecha.",
        "capas": [("toques", 1.0), ("unas", 0.6), ("ruido_rosa", 0.1)],
        "estilo": "bokeh", "paleta": "lavanda",
    },
    "estudio": {
        "descripcion": "Teclado mecánico + lluvia de fondo (para concentración).",
        "capas": [("tecleo", 0.9), ("lluvia", 0.5)],
        "estilo": "lluvia", "paleta": "noche",
    },
    "burbujas": {
        "descripcion": "Burbujas y gotas suaves.",
        "capas": [("burbujas", 1.0), ("gotas", 0.5)],
        "estilo": "seda", "paleta": "lavanda",
    },
    "dormir": {
        "descripcion": "Ruido marrón profundo con olas muy suaves.",
        "capas": [("ruido_marron", 1.0), ("olas", 0.4)],
        "estilo": "seda", "paleta": "noche",
    },
}

FORMATOS = {
    "vertical": (1080, 1920),    # Reels, TikTok, Shorts
    "cuadrado": (1080, 1080),    # feed Instagram
    "horizontal": (1920, 1080),  # YouTube
}


def parsear_capas(texto: str) -> list[tuple[str, float]]:
    """'lluvia:0.8,toques:0.5' -> [('lluvia', 0.8), ('toques', 0.5)]"""
    capas = []
    for trozo in texto.split(","):
        trozo = trozo.strip()
        if not trozo:
            continue
        nombre, _, vol = trozo.partition(":")
        capas.append((nombre.strip(), float(vol) if vol else 1.0))
    return capas
