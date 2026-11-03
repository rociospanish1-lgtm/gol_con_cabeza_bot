"""Generadores de fotogramas para fondos ASMR.

Los estilos procedurales se calculan a 1/4 de resolución (son imágenes
suaves y desenfocadas) y ffmpeg los escala con lanczos + grano fino, lo que
permite renderizar 1080x1920 a 30 fps en un portátil normal.

Todos los movimientos son periódicos respecto a la duración del vídeo:
el último fotograma enlaza con el primero (bucle perfecto).
"""

from __future__ import annotations

from typing import Iterator

import numpy as np

PALETAS = {
    # fondo oscuro, fondo claro, acentos...
    "clinica": ["#1f1a1c", "#6b4f57", "#f3d5cf", "#e8b4a8", "#c9d6c3", "#fff4ec"],
    "noche": ["#05060f", "#1b2240", "#7fa7ff", "#c9b8ff", "#ffd9a8", "#ffffff"],
    "calido": ["#140805", "#4a1d0e", "#ff9a3c", "#ffcf7a", "#ff5e3a", "#fff1d6"],
    "oceano": ["#03141c", "#0d4a5e", "#7fe3e0", "#bff5ea", "#4fb3d9", "#ffffff"],
    "lavanda": ["#140f1f", "#4b3b6b", "#d8c7ff", "#f6d6ff", "#a9c1ff", "#ffffff"],
}


def hex_a_rgb(h: str) -> np.ndarray:
    h = h.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"Color no válido: #{h} (usa formato #RRGGBB)")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255.0


def resolver_paleta(paleta: str | list[str]) -> list[np.ndarray]:
    if isinstance(paleta, str):
        lista = PALETAS.get(paleta) or [c for c in paleta.split(",") if c.strip()]
    else:
        lista = paleta
    cols = [hex_a_rgb(c) for c in lista]
    if len(cols) < 3:
        raise ValueError("La paleta necesita al menos 3 colores: oscuro, medio y acento")
    return cols


def _mezcla_gradiente(cols: list[np.ndarray], v: np.ndarray) -> np.ndarray:
    """Mapea v∈[0,1] a un degradado continuo entre los colores."""
    v = np.clip(v, 0, 1) * (len(cols) - 1)
    i = np.minimum(v.astype(int), len(cols) - 2)
    f = (v - i)[..., None]
    c = np.stack(cols)
    return c[i] * (1 - f) + c[i + 1] * f


def _parche(W: int, H: int, cx: float, cy: float, rx: float, ry: float):
    """Ventana local (slices + rejillas) alrededor de un punto, para no calcular la imagen entera."""
    x0, x1 = max(0, int(cx - rx)), min(W, int(cx + rx) + 2)
    y0, y1 = max(0, int(cy - ry)), min(H, int(cy + ry) + 2)
    if x0 >= x1 or y0 >= y1:
        return None
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    return (slice(y0, y1), slice(x0, x1)), xx, yy


class Escena:
    """Base: genera fotogramas float32 (h, w, 3) en [0,1]."""

    escala = 4  # factor de submuestreo; 1 = resolución completa

    def __init__(self, ancho: int, alto: int, duracion: float, fps: int, paleta, semilla: int = 7):
        self.W, self.H = ancho // self.escala, alto // self.escala
        self.D, self.fps = duracion, fps
        self.cols = resolver_paleta(paleta)
        self.rng = np.random.default_rng(semilla)
        self.y, self.x = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        self.xn, self.yn = self.x / self.W, self.y / self.H
        fondo_v = (self.yn * 0.85 + 0.15 * (1 - np.abs(self.xn - 0.5) * 2))
        self.fondo = _mezcla_gradiente(self.cols[:2], fondo_v)
        self.w = 2 * np.pi / duracion

    def frame(self, t: float, energia: float) -> np.ndarray:  # pragma: no cover - interfaz
        raise NotImplementedError

    def fotogramas(self, energia: np.ndarray) -> Iterator[bytes]:
        n = len(energia)
        for i in range(n):
            img = self.frame(i / self.fps, float(energia[i]))
            yield (np.clip(img, 0, 1) * 255).astype(np.uint8).tobytes()


class Bokeh(Escena):
    """Luces desenfocadas flotando lentamente; laten suavemente con el sonido."""

    def __init__(self, *a, n_luces: int = 22, **k):
        super().__init__(*a, **k)
        r = self.rng
        self.luces = []
        acentos = self.cols[2:]
        for _ in range(n_luces):
            self.luces.append(dict(
                x0=r.uniform(0.05, 0.95), y0=r.uniform(0.05, 0.95),
                ax=r.uniform(0.04, 0.16), ay=r.uniform(0.04, 0.16),
                kx=int(r.integers(1, 3)), ky=int(r.integers(1, 3)),
                fx=r.uniform(0, 6.28), fy=r.uniform(0, 6.28),
                radio=r.uniform(0.04, 0.13) * self.W, int_=r.uniform(0.25, 0.7),
                col=acentos[int(r.integers(0, len(acentos)))], sens=r.uniform(0.2, 1.0),
            ))

    def frame(self, t, energia):
        img = self.fondo.copy()
        luz = np.zeros_like(img)
        for L in self.luces:
            cx = (L["x0"] + L["ax"] * np.sin(L["kx"] * self.w * t + L["fx"])) * self.W
            cy = (L["y0"] + L["ay"] * np.sin(L["ky"] * self.w * t + L["fy"])) * self.H
            p = _parche(self.W, self.H, cx, cy, L["radio"] * 1.9, L["radio"] * 1.9)
            if p is None:
                continue
            sl, xx, yy = p
            d2 = ((xx - cx) ** 2 + (yy - cy) ** 2) / (L["radio"] ** 2)
            disco = np.exp(-d2 ** 2 * 0.6)  # borde suave pero definido (bokeh)
            amp = L["int_"] * (0.75 + 0.4 * energia * L["sens"])
            luz[sl] += disco[..., None] * L["col"] * amp
        return 1 - (1 - img) * (1 - np.clip(luz, 0, 1))  # fusión "trama"


class Seda(Escena):
    """Ondas líquidas tipo seda con el degradado de la paleta."""

    def frame(self, t, energia):
        w, x, y = self.w, self.xn * 6.0, self.yn * 6.0
        v = (np.sin(x * 0.9 + 1.6 * np.sin(y * 0.7 + w * t) + w * 2 * t)
             + np.sin(y * 1.1 + 1.3 * np.sin(x * 0.8 - w * 3 * t))
             + 0.6 * np.sin((x + y) * 0.6 + w * t))
        v = (v / 2.6 + 1) / 2
        brillo = 0.92 + 0.12 * energia
        return _mezcla_gradiente(self.cols, v) * brillo


class Lluvia(Escena):
    """Gotas cayendo sobre cristal con luces de ciudad desenfocadas al fondo."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        r = self.rng
        self.bokeh = Bokeh(*a, n_luces=14, **k)
        self.bokeh.fondo = self.fondo * 0.7
        n = 70
        self.gx = r.uniform(0, self.W, n)
        self.gy = r.uniform(0, 1, n)
        self.gm = r.integers(int(self.D / 1.4) + 1, int(self.D / 0.7) + 2, n)  # vueltas por bucle
        self.glen = r.uniform(4, 12, n)
        self.gint = r.uniform(0.08, 0.25, n)

    def frame(self, t, energia):
        img = self.bokeh.frame(t, energia) * 0.85
        capa = np.zeros((self.H, self.W), dtype=np.float32)
        for gx, gy, gm, gl, gi in zip(self.gx, self.gy, self.gm, self.glen, self.gint):
            cy = ((gy + gm * t / self.D) % 1.0) * (self.H + 20) - 10
            p = _parche(self.W, self.H, gx, cy, 3, gl / 2 + 5)
            if p is None:
                continue
            sl, xx, yy = p
            dx = (xx - gx) ** 2
            dy = np.clip(np.abs(yy - cy) - gl / 2, 0, None) ** 2
            capa[sl] += np.exp(-(dx / 0.6 + dy / 2.0)) * gi
        return np.clip(img + capa[..., None] * self.cols[-1], 0, 1)


class Brasas(Escena):
    """Chispas que ascienden y parpadean sobre un fondo cálido."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        r = self.rng
        n = 60
        self.ex = r.uniform(0, 1, n)
        self.ey = r.uniform(0, 1, n)
        self.em = r.integers(max(1, int(self.D / 12)), int(self.D / 5) + 2, n)
        self.ew = r.uniform(0.01, 0.05, n)
        self.ek = r.integers(1, 4, n)
        self.ef = r.uniform(0, 6.28, n)
        self.er = r.uniform(0.8, 2.2, n)
        self.ec = r.integers(2, len(self.cols), n)
        self.brillo_base = np.exp(-((self.yn - 1.1) ** 2) / 0.25)[..., None] * self.cols[2] * 0.5

    def frame(self, t, energia):
        img = self.fondo + self.brillo_base * (0.8 + 0.3 * energia)
        luz = np.zeros_like(img)
        for i in range(len(self.ex)):
            cy = (1.05 - 1.1 * ((self.ey[i] + self.em[i] * t / self.D) % 1.0)) * self.H
            cx = (self.ex[i] + self.ew[i] * np.sin(self.ek[i] * self.w * t * 6 + self.ef[i])) * self.W
            parpadeo = 0.55 + 0.45 * np.sin(self.w * t * 40 * self.ek[i] + self.ef[i])
            p = _parche(self.W, self.H, cx, cy, self.er[i] * 3.5, self.er[i] * 3.5)
            if p is None:
                continue
            sl, xx, yy = p
            d2 = ((xx - cx) ** 2 + (yy - cy) ** 2) / self.er[i] ** 2
            luz[sl] += np.exp(-d2)[..., None] * self.cols[self.ec[i]] * parpadeo
        return 1 - (1 - np.clip(img, 0, 1)) * (1 - np.clip(luz, 0, 1))


class Imagen(Escena):
    """Foto propia con zoom/paneo lento (Ken Burns) en bucle y viñeta suave."""

    escala = 1

    def __init__(self, ancho, alto, duracion, fps, paleta, semilla=7, ruta: str = ""):
        from PIL import Image  # import diferido: solo necesario con foto

        self.W, self.H, self.D, self.fps = ancho, alto, duracion, fps
        self.w = 2 * np.pi / duracion
        img = Image.open(ruta).convert("RGB")
        # recorte al formato de salida + margen para el movimiento
        objetivo = ancho / alto
        iw, ih = img.size
        if iw / ih > objetivo:
            nw = int(ih * objetivo)
            img = img.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
        else:
            nh = int(iw / objetivo)
            img = img.crop((0, (ih - nh) // 2, iw, (ih - nh) // 2 + nh))
        factor = max(1.0, (ancho * 1.25) / img.size[0])
        self.img = img.resize((int(img.size[0] * factor), int(img.size[1] * factor)), Image.LANCZOS)
        self.Image = Image
        yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
        r = np.sqrt(((xx / ancho) - 0.5) ** 2 + ((yy / alto) - 0.5) ** 2)
        self.vineta = (1 - 0.35 * np.clip((r - 0.35) / 0.4, 0, 1) ** 2)[..., None]

    def frame(self, t, energia):
        iw, ih = self.img.size
        zoom = 1.08 + 0.06 * np.sin(self.w * t)  # 1.02 .. 1.14
        cw, ch = iw / zoom, ih / zoom
        cx = iw / 2 + (iw - cw) / 2 * 0.6 * np.sin(self.w * t + 1.3)
        cy = ih / 2 + (ih - ch) / 2 * 0.6 * np.cos(self.w * t)
        caja = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        fr = self.img.resize((self.W, self.H), self.Image.BICUBIC, box=caja)
        return np.asarray(fr, dtype=np.float32) / 255.0 * self.vineta


ESTILOS = {"bokeh": Bokeh, "seda": Seda, "lluvia": Lluvia, "brasas": Brasas}
