"""Síntesis procedural de sonidos ASMR en estéreo binaural.

Todo se genera con numpy (sin samples externos ni licencias). Cada "capa"
devuelve un array estéreo float32 de forma (n, 2) con valores ~[-1, 1].

Técnicas usadas:
- Ruido de color (blanco/rosa/marrón) generado por bloques en el dominio de
  la frecuencia con solape sqrt-Hann (sin cortes audibles).
- Eventos cortos (gotas, toques, clics) sintetizados y colocados con
  panorama de potencia constante + diferencia interaural de tiempo (ITD),
  que es lo que da la sensación "binaural" con auriculares.
- Todos los movimientos lentos usan periodos que dividen la duración, para
  que el vídeo pueda repetirse en bucle sin salto (clave en Reels/TikTok).
"""

from __future__ import annotations

import wave
from typing import Callable, Dict

import numpy as np

SR = 48_000  # Hz, estándar de vídeo
ITD_MAX = 0.00065  # s, diferencia interaural máxima aproximada en humanos


# ---------------------------------------------------------------------------
# Utilidades de señal
# ---------------------------------------------------------------------------

def _forma_espectral(freqs: np.ndarray, exponente: float, lo: float | None, hi: float | None) -> np.ndarray:
    """Curva de amplitud |H(f)| = f^(-exponente/2) con cortes suaves."""
    f = np.maximum(freqs, 1.0)
    g = f ** (-exponente / 2.0)
    if lo:
        g *= 1.0 / np.sqrt(1.0 + (lo / f) ** 4)  # paso alto 2º orden aprox.
    if hi:
        g *= 1.0 / np.sqrt(1.0 + (f / hi) ** 4)  # paso bajo 2º orden aprox.
    g[0] = 0.0
    return g


def ruido_color(n: int, rng: np.random.Generator, exponente: float = 0.0,
                lo: float | None = None, hi: float | None = None) -> np.ndarray:
    """Ruido mono de longitud n. exponente: 0 blanco, 1 rosa, 2 marrón."""
    bloque = 1 << 17  # ~2.7 s
    salto = bloque // 2
    ventana = np.sqrt(np.hanning(bloque + 1)[:-1]).astype(np.float64)
    freqs = np.fft.rfftfreq(bloque, 1.0 / SR)
    forma = _forma_espectral(freqs, exponente, lo, hi)
    total = n + bloque
    salida = np.zeros(total, dtype=np.float64)
    for ini in range(0, total - bloque + 1, salto):
        espectro = (rng.standard_normal(len(freqs)) + 1j * rng.standard_normal(len(freqs))) * forma
        trozo = np.fft.irfft(espectro, n=bloque) * ventana
        salida[ini:ini + bloque] += trozo
    salida = salida[salto:salto + n]
    rms = np.sqrt(np.mean(salida ** 2)) or 1.0
    return (salida / rms).astype(np.float32)


def filtro_fft(x: np.ndarray, lo: float | None = None, hi: float | None = None) -> np.ndarray:
    """Filtro pasa-banda suave para señales cortas (eventos)."""
    if len(x) < 4:
        return x
    n = 1 << int(np.ceil(np.log2(len(x) * 2)))
    espectro = np.fft.rfft(x, n=n)
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    espectro *= _forma_espectral(freqs, 0.0, lo, hi) * 1.0
    return np.fft.irfft(espectro, n=n)[:len(x)].astype(np.float32)


def panorama(pan: float) -> tuple[float, float]:
    """Ganancias L/R de potencia constante. pan en [-1 (izq), 1 (dcha)]."""
    ang = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    return float(np.cos(ang)), float(np.sin(ang))


def colocar(salida: np.ndarray, muestra: np.ndarray, inicio: int, pan: float, ganancia: float = 1.0) -> None:
    """Suma un evento mono en `salida` (n, 2) con panorama + ITD binaural."""
    gl, gr = panorama(pan)
    retardo = int(round(abs(pan) * ITD_MAX * SR))
    n = salida.shape[0]
    for canal, g, extra in ((0, gl, retardo if pan > 0 else 0), (1, gr, retardo if pan < 0 else 0)):
        ini = inicio + extra
        if ini >= n:
            continue
        fin = min(n, ini + len(muestra))
        if fin <= max(ini, 0):
            continue
        src_ini = max(0, -ini)
        salida[max(ini, 0):fin, canal] += muestra[src_ini:src_ini + fin - max(ini, 0)] * g * ganancia


def colocar_movil(salida: np.ndarray, muestra: np.ndarray, inicio: int, pan_ini: float, pan_fin: float,
                  ganancia: float = 1.0) -> None:
    """Evento con panorama que se desplaza (p. ej. brocha de izquierda a derecha)."""
    n = salida.shape[0]
    fin = min(n, inicio + len(muestra))
    if fin <= inicio or inicio < 0:
        return
    m = muestra[:fin - inicio]
    pan = np.linspace(pan_ini, pan_fin, len(m))
    ang = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    salida[inicio:fin, 0] += m * np.cos(ang) * ganancia
    salida[inicio:fin, 1] += m * np.sin(ang) * ganancia


def estereo_ancho(rng: np.random.Generator, n: int, exponente: float, lo=None, hi=None,
                  correlacion: float = 0.3) -> np.ndarray:
    """Lecho de ruido estéreo con anchura controlada (0 = muy ancho, 1 = mono)."""
    comun = ruido_color(n, rng, exponente, lo, hi)
    izq = ruido_color(n, rng, exponente, lo, hi)
    dch = ruido_color(n, rng, exponente, lo, hi)
    a, b = np.sqrt(correlacion), np.sqrt(1 - correlacion)
    return np.stack([a * comun + b * izq, a * comun + b * dch], axis=1)


def lfo(n: int, duracion: float, ciclos: int, fase: float = 0.0) -> np.ndarray:
    """Oscilador lento periódico respecto a la duración total (apto para bucle)."""
    t = np.arange(n, dtype=np.float32) / SR
    return np.sin(2 * np.pi * max(1, ciclos) * t / duracion + fase).astype(np.float32)


def _env_exp(n: int, tau: float, ataque: float = 0.0008) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SR
    env = np.exp(-t / tau)
    na = max(1, int(ataque * SR))
    env[:na] *= np.linspace(0, 1, na)
    return env.astype(np.float32)


# ---------------------------------------------------------------------------
# Eventos sintéticos (mono)
# ---------------------------------------------------------------------------

def ev_gota(rng: np.random.Generator, brillo: float = 1.0) -> np.ndarray:
    """Gota de agua: seno con barrido ascendente de tono (resonancia de burbuja)."""
    f0 = rng.uniform(700, 1600) * brillo
    tau = rng.uniform(0.012, 0.035)
    n = int(tau * 8 * SR)
    t = np.arange(n) / SR
    f = f0 * (1 + rng.uniform(0.6, 1.4) * (1 - np.exp(-t / 0.012)))
    fase = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(fase) * _env_exp(n, tau, 0.0005)).astype(np.float32)


def ev_burbuja(rng: np.random.Generator) -> np.ndarray:
    f0 = rng.uniform(250, 900)
    tau = rng.uniform(0.03, 0.08)
    n = int(tau * 6 * SR)
    t = np.arange(n) / SR
    f = f0 * (1 + 0.25 * t / (tau * 6))
    fase = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(fase) * _env_exp(n, tau, 0.003) * 0.8).astype(np.float32)


def ev_toque(rng: np.random.Generator, material: str = "madera") -> np.ndarray:
    """Toque con la yema/uña. Parciales inarmónicos + transitorio de ruido."""
    if material == "cristal":
        f0, tau, parciales = rng.uniform(2200, 4200), rng.uniform(0.12, 0.3), (1.0, 2.76, 5.40)
    elif material == "una":  # uñas sobre plástico duro
        f0, tau, parciales = rng.uniform(1800, 3200), rng.uniform(0.006, 0.014), (1.0, 1.71, 2.93)
    else:  # madera
        f0, tau, parciales = rng.uniform(350, 900), rng.uniform(0.02, 0.05), (1.0, 2.31, 3.87)
    n = int(max(tau * 6, 0.03) * SR)
    t = np.arange(n) / SR
    s = np.zeros(n, dtype=np.float32)
    for i, p in enumerate(parciales):
        s += (0.6 ** i) * np.sin(2 * np.pi * f0 * p * t + rng.uniform(0, 6.28)) * _env_exp(n, tau / (1 + i * 0.8))
    clic = filtro_fft(rng.standard_normal(int(0.003 * SR)).astype(np.float32), lo=2000, hi=12000)
    s[:len(clic)] += clic * _env_exp(len(clic), 0.0008) * 0.6
    return (s / (np.max(np.abs(s)) + 1e-9)).astype(np.float32)


def ev_crujido(rng: np.random.Generator) -> np.ndarray:
    """Chasquido de leña: ráfaga de ruido muy corta con cola."""
    n = int(rng.uniform(0.002, 0.012) * SR)
    s = rng.standard_normal(n).astype(np.float32)
    s = filtro_fft(s, lo=rng.uniform(800, 2500), hi=rng.uniform(6000, 14000))
    return (s * _env_exp(n, n / SR / 3, 0.0002)).astype(np.float32)


def ev_tecla(rng: np.random.Generator) -> np.ndarray:
    """Tecla mecánica: clic agudo + golpe grave ("thock")."""
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    thock = np.sin(2 * np.pi * rng.uniform(140, 260) * t) * _env_exp(n, 0.012)
    clic = filtro_fft(rng.standard_normal(n).astype(np.float32), lo=3000, hi=14000) * _env_exp(n, 0.0025, 0.0002)
    s = 0.7 * thock + 0.5 * clic
    return (s / (np.max(np.abs(s)) + 1e-9)).astype(np.float32)


def ev_trazo(rng: np.random.Generator, dur: float, lo=1500, hi=9000) -> np.ndarray:
    """Trazo de brocha/cepillo: ruido filtrado con envolvente de coseno."""
    n = int(dur * SR)
    s = filtro_fft(rng.standard_normal(n).astype(np.float32), lo=lo, hi=hi)
    s /= np.sqrt(np.mean(s ** 2)) + 1e-9
    env = np.sin(np.linspace(0, np.pi, n)) ** 1.5
    textura = 1 + 0.35 * filtro_fft(rng.standard_normal(n).astype(np.float32), hi=40)  # cerdas irregulares
    return (s * env * np.clip(textura, 0.3, 1.7)).astype(np.float32)


# ---------------------------------------------------------------------------
# Capas (estéreo, duración completa)
# ---------------------------------------------------------------------------

def _vacio(n: int) -> np.ndarray:
    return np.zeros((n, 2), dtype=np.float32)


def _tiempos_poisson(rng, duracion: float, tasa: float) -> np.ndarray:
    k = rng.poisson(tasa * duracion)
    return np.sort(rng.uniform(0, duracion, k))


def capa_lluvia(rng, n, duracion, intensidad=1.0):
    base = estereo_ancho(rng, n, 1.0, lo=350, hi=11000, correlacion=0.15) * 0.18 * intensidad
    out = base.copy()
    for t in _tiempos_poisson(rng, duracion, 70 * intensidad):
        colocar(out, ev_gota(rng, brillo=rng.uniform(1.2, 2.4)), int(t * SR), rng.uniform(-1, 1), rng.uniform(0.02, 0.09))
    for t in _tiempos_poisson(rng, duracion, 1.2):  # goterones cercanos
        colocar(out, ev_gota(rng), int(t * SR), rng.uniform(-0.9, 0.9), rng.uniform(0.15, 0.3))
    return out


def capa_olas(rng, n, duracion, ciclos=None):
    ciclos = ciclos or max(1, round(duracion / 9))  # una ola cada ~9 s
    grave = estereo_ancho(rng, n, 2.0, lo=40, hi=900, correlacion=0.5)
    espuma = estereo_ancho(rng, n, 0.6, lo=600, hi=9000, correlacion=0.2)
    env = (lfo(n, duracion, ciclos, -np.pi / 2) + 1) / 2  # 0..1
    env2 = env ** 2.5
    pan = lfo(n, duracion, max(1, ciclos // 2)) * 0.35
    out = grave * (0.12 + 0.25 * env)[:, None] + espuma * (0.02 + 0.22 * env2)[:, None]
    out[:, 0] *= (1 - pan)
    out[:, 1] *= (1 + pan)
    return out.astype(np.float32)


def capa_fuego(rng, n, duracion):
    out = estereo_ancho(rng, n, 2.0, lo=30, hi=350, correlacion=0.6) * 0.22
    siseo = estereo_ancho(rng, n, 1.0, lo=2000, hi=8000, correlacion=0.3) * 0.015
    out += siseo
    tiempos = _tiempos_poisson(rng, duracion, 9)
    for t in tiempos:
        pan = rng.uniform(-0.8, 0.8)
        for k in range(rng.integers(1, 4)):  # chasquidos en racimo
            colocar(out, ev_crujido(rng), int((t + k * rng.uniform(0.005, 0.05)) * SR), pan + rng.normal(0, 0.05),
                    rng.pareto(2.5) * 0.12 + 0.05)
    return out


def capa_ruido(rng, n, duracion, color="marron"):
    exp = {"blanco": 0.0, "rosa": 1.0, "marron": 2.0}.get(color, 2.0)
    hi = {"blanco": 12000, "rosa": 14000, "marron": 2500}.get(color, 2500)
    return estereo_ancho(rng, n, exp, lo=25, hi=hi, correlacion=0.4) * 0.2


def capa_toques(rng, n, duracion, material="madera", ritmo=3.2):
    """Patrones de toques que se alternan entre oídos (efecto binaural clásico)."""
    out = _vacio(n)
    t = 0.4
    lado = -1
    while t < duracion - 0.3:
        rafaga = rng.integers(3, 9)
        pan_base = lado * rng.uniform(0.55, 0.95)
        intervalo = 1.0 / (ritmo * rng.uniform(1.4, 2.6))
        for _ in range(rafaga):
            if t >= duracion - 0.2:
                break
            colocar(out, ev_toque(rng, material), int(t * SR), pan_base + rng.normal(0, 0.06), rng.uniform(0.18, 0.32))
            t += intervalo * rng.uniform(0.8, 1.2)
        t += rng.uniform(0.35, 1.1)
        lado = -lado
    return out


def capa_cepillado(rng, n, duracion):
    """Brocha suave que barre de oído a oído."""
    out = _vacio(n)
    t, lado = 0.3, -1
    while t < duracion - 0.5:
        dur = rng.uniform(0.45, 0.9)
        colocar_movil(out, ev_trazo(rng, dur), int(t * SR), lado * 0.95, -lado * 0.95, rng.uniform(0.05, 0.08))
        t += dur * rng.uniform(0.55, 0.85)
        lado = -lado
    return out


def capa_tecleo(rng, n, duracion):
    out = _vacio(n)
    t = 0.3
    while t < duracion - 0.2:
        for _ in range(rng.integers(3, 8)):  # una "palabra"
            if t >= duracion - 0.1:
                break
            colocar(out, ev_tecla(rng), int(t * SR), rng.uniform(-0.45, 0.45), rng.uniform(0.12, 0.22))
            t += rng.uniform(0.07, 0.16)
        t += rng.uniform(0.18, 0.6)
    return out


def capa_gotas(rng, n, duracion, tasa=1.6):
    """Gotas espaciadas (sérum, grifo) en posiciones fijas distintas."""
    out = _vacio(n)
    for t in _tiempos_poisson(rng, duracion, tasa):
        colocar(out, ev_gota(rng), int(t * SR), rng.choice([-0.8, -0.3, 0.3, 0.8]) + rng.normal(0, 0.05),
                rng.uniform(0.18, 0.3))
    return out


def capa_burbujas(rng, n, duracion, tasa=6.0):
    out = estereo_ancho(rng, n, 1.0, lo=200, hi=3000, correlacion=0.5) * 0.02
    for t in _tiempos_poisson(rng, duracion, tasa):
        colocar(out, ev_burbuja(rng), int(t * SR), rng.uniform(-0.7, 0.7), rng.uniform(0.06, 0.16))
    return out


def capa_cristal(rng, n, duracion):
    """Toques sobre frascos de cristal (muy usado en ASMR de cosmética)."""
    return capa_toques(rng, n, duracion, material="cristal", ritmo=1.6)


def capa_unas(rng, n, duracion):
    return capa_toques(rng, n, duracion, material="una", ritmo=4.0)


CAPAS: Dict[str, Callable] = {
    "lluvia": capa_lluvia,
    "olas": capa_olas,
    "fuego": capa_fuego,
    "ruido_marron": lambda rng, n, d: capa_ruido(rng, n, d, "marron"),
    "ruido_rosa": lambda rng, n, d: capa_ruido(rng, n, d, "rosa"),
    "ruido_blanco": lambda rng, n, d: capa_ruido(rng, n, d, "blanco"),
    "toques": capa_toques,
    "unas": capa_unas,
    "cristal": capa_cristal,
    "cepillado": capa_cepillado,
    "tecleo": capa_tecleo,
    "gotas": capa_gotas,
    "burbujas": capa_burbujas,
}


# ---------------------------------------------------------------------------
# Mezcla final
# ---------------------------------------------------------------------------

def _bucle(x: np.ndarray, cruce: int) -> np.ndarray:
    """Funde el final con el principio para que el audio se repita sin salto."""
    if cruce <= 0 or len(x) <= 2 * cruce:
        return x
    cuerpo = x[:-cruce].copy()
    cola = x[-cruce:]
    w = np.sin(np.linspace(0, np.pi / 2, cruce))[:, None].astype(np.float32)
    cuerpo[:cruce] = cuerpo[:cruce] * w + cola * np.cos(np.linspace(0, np.pi / 2, cruce))[:, None]
    return cuerpo


def cargar_wav(ruta: str) -> np.ndarray:
    """Carga un WAV PCM16 estéreo/mono a 48 kHz (usa ffmpeg antes para convertir)."""
    with wave.open(ruta, "rb") as w:
        canales = w.getnchannels()
        datos = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    datos = datos.reshape(-1, canales)
    if canales == 1:
        datos = np.repeat(datos, 2, axis=1)
    return datos[:, :2]


def mezclar(capas: list[tuple[str, float]], duracion: float, semilla: int = 7, bucle: bool = True,
            voz: np.ndarray | None = None, volumen_voz: float = 1.0) -> np.ndarray:
    """Genera y mezcla las capas. Devuelve float32 (n, 2) normalizado con margen."""
    rng = np.random.default_rng(semilla)
    cruce = int(1.5 * SR) if bucle else 0
    n = int(duracion * SR) + cruce
    mezcla = _vacio(n)
    for nombre, vol in capas:
        if nombre not in CAPAS:
            raise ValueError(f"Capa desconocida: '{nombre}'. Disponibles: {', '.join(sorted(CAPAS))}")
        mezcla += CAPAS[nombre](rng, n, n / SR) * float(vol)
    mezcla = _bucle(mezcla, cruce)
    if voz is not None:
        v = voz[: len(mezcla)] * volumen_voz
        # La voz va encima del ambiente: bajamos el fondo ~6 dB donde hay voz (ducking).
        env = np.convolve(np.abs(v).mean(axis=1), np.ones(4800) / 4800, mode="same")
        duck = 1 - 0.5 * np.clip(env / (env.max() + 1e-9) * 3, 0, 1)
        mezcla[: len(v)] *= duck[:, None]
        mezcla[: len(v)] += v
    pico = np.max(np.abs(mezcla)) + 1e-9
    mezcla = np.tanh(mezcla / pico * 1.2) * 0.85  # limitador suave
    return mezcla.astype(np.float32)


def guardar_wav(ruta: str, audio: np.ndarray) -> None:
    datos = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(datos.tobytes())


def envolvente(audio: np.ndarray, fps: int, n_frames: int) -> np.ndarray:
    """Energía por fotograma (0..1) para que el vídeo reaccione al sonido."""
    mono = np.abs(audio).mean(axis=1)
    por_frame = SR / fps
    idx = (np.arange(n_frames) * por_frame).astype(int)
    vals = np.array([mono[i:i + int(por_frame)].mean() if i < len(mono) else 0 for i in idx])
    vals = vals / (np.percentile(vals, 98) + 1e-9)
    # suavizado ataque rápido / caída lenta
    sal = np.zeros_like(vals)
    acc = 0.0
    for i, v in enumerate(vals):
        acc = v if v > acc else acc * 0.9 + v * 0.1
        sal[i] = acc
    return np.clip(sal, 0, 1.5)
