#!/usr/bin/env python3
"""Analizador de vídeos virales.

Uso:
    python analizar_viral.py URL                 # un vídeo
    python analizar_viral.py URL --cuenta        # compara con los últimos vídeos de la cuenta
    python analizar_viral.py URL --claude        # añade análisis redactado con la API de Claude
    python analizar_viral.py --json datos.json   # re-analiza datos ya extraídos (sin red)

Qué hace:
  1. Extrae métricas y transcripción con yt-dlp (+ youtube-transcript-api / Whisper).
  2. Calcula si el vídeo es viral de verdad (ratio visitas/seguidores, engagement,
     múltiplo sobre la media de la cuenta).
  3. Detecta gancho, mecanismo de viralidad, CTA y estructura.
  4. Puntúa la adaptabilidad al nicho (clínicas de estética de Sevilla).
  5. Guarda un informe en informes/*.md y los datos en informes/*.json.

Debe ejecutarse en el ordenador de Rocío: desde la nube YouTube/TikTok están bloqueados.
"""
import argparse
import datetime as dt
import json
import os
import re
import statistics
import sys
import tempfile
from pathlib import Path

CARPETA_INFORMES = Path(__file__).parent / "informes"

# ----------------------------------------------------------------------------
# 1. Extracción
# ----------------------------------------------------------------------------

def _opts(args, **extra):
    o = {"quiet": True, "no_warnings": True, "skip_download": True}
    if getattr(args, "cookies_navegador", None):
        o["cookiesfrombrowser"] = (args.cookies_navegador,)
    o.update(extra)
    return o


def extraer_info(url, args):
    from yt_dlp import YoutubeDL
    with YoutubeDL(_opts(args)) as y:
        return y.extract_info(url, download=False)


def media_cuenta(info, args, n=15):
    """Visitas de los últimos n vídeos de la cuenta (excluye el analizado)."""
    from yt_dlp import YoutubeDL
    canal = info.get("uploader_url") or info.get("channel_url")
    if not canal:
        return None
    try:
        with YoutubeDL(_opts(args, extract_flat=True, playlistend=n + 1)) as y:
            lista = y.extract_info(canal, download=False)
        vistas = [e.get("view_count") for e in (lista.get("entries") or [])
                  if e.get("view_count") is not None and e.get("id") != info.get("id")]
        return round(statistics.median(vistas)) if len(vistas) >= 3 else None
    except Exception as e:  # noqa: BLE001
        print(f"Aviso: no se pudo leer la cuenta ({e})", file=sys.stderr)
        return None


def transcribir(info, url, args):
    """Devuelve (texto, segmentos[{start,text}]). Intenta subtítulos, luego Whisper."""
    if info.get("extractor_key") == "Youtube":
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            try:
                t = YouTubeTranscriptApi().fetch(info["id"], languages=["es", "en"])
                segs = [{"start": s.start, "text": s.text} for s in t]
            except AttributeError:
                t = YouTubeTranscriptApi.get_transcript(info["id"], languages=["es", "en"])
                segs = [{"start": s["start"], "text": s["text"]} for s in t]
            return " ".join(s["text"] for s in segs), segs
        except Exception:  # noqa: BLE001
            pass
    if args.sin_whisper:
        return None, []
    try:
        import whisper
        from yt_dlp import YoutubeDL
        tmp = tempfile.mkdtemp()
        with YoutubeDL({"quiet": True, "format": "bestaudio/best",
                        "outtmpl": f"{tmp}/a.%(ext)s",
                        **({"cookiesfrombrowser": (args.cookies_navegador,)}
                           if args.cookies_navegador else {})}) as y:
            y.download([url])
        fichero = os.path.join(tmp, os.listdir(tmp)[0])
        r = whisper.load_model(args.modelo).transcribe(fichero)
        return r["text"].strip(), [{"start": s["start"], "text": s["text"].strip()}
                                   for s in r["segments"]]
    except Exception as e:  # noqa: BLE001
        print(f"Aviso: sin transcripción ({e})", file=sys.stderr)
        return None, []


def construir_datos(url, args):
    info = extraer_info(url, args)
    vistas = info.get("view_count") or 0
    likes = info.get("like_count") or 0
    coment = info.get("comment_count") or 0
    seguidores = info.get("channel_follower_count")
    f = info.get("upload_date")
    dias = (dt.date.today() - dt.datetime.strptime(f, "%Y%m%d").date()).days if f else None
    texto, segs = transcribir(info, url, args)
    return {
        "url": info.get("webpage_url", url),
        "plataforma": info.get("extractor_key"),
        "titulo": info.get("title"),
        "cuenta": info.get("uploader"),
        "descripcion": (info.get("description") or "")[:800],
        "hashtags": re.findall(r"#\w+", info.get("description") or ""),
        "duracion_s": info.get("duration"),
        "visitas": vistas, "likes": likes, "comentarios": coment,
        "seguidores": seguidores, "dias_publicado": dias,
        "mediana_cuenta": media_cuenta(info, args) if args.cuenta else None,
        "transcripcion": texto, "segmentos": segs,
    }


# ----------------------------------------------------------------------------
# 2. Análisis
# ----------------------------------------------------------------------------

MECANISMOS = {
    "Error común / mito": r"\b(error|errores|mito|nadie te (dice|cuenta)|dejas de|estás (haciendo )?mal|no (hagas|cometas))\b",
    "Miedo a perder dinero/clientes": r"\b(pierdes?|perdiendo|perdidas?|perdidos|dinero|facturar|cada (mes|día|semana)|se te escapan?|dejas de ganar)\b",
    "Lista / número": r"^\s*(\d+|tres|cuatro|cinco|seis|siete)\b|\b(\d+) (cosas|formas|pasos|errores|razones|herramientas|trucos)\b",
    "Pregunta / curiosidad": r"\?|\b(sabías|te has preguntado|y si te dijera|el secreto|lo que nadie)\b",
    "Antes / después": r"\b(antes|después|resultado|pasé de|de .{1,15} a .{1,15})\b",
    "Demostración / tutorial": r"\b(mira|te enseño|te muestro|paso a paso|así (se )?(hace|funciona)|tutorial|cómo)\b",
    "Historia / POV": r"\b(pov|un día|me pasó|mi (cliente|clienta)|te cuento|historia)\b",
    "Polémica / opinión fuerte": r"\b(opinión|impopular|no (me )?gusta|odio|mentira|estafa|nunca|jamás|todos)\b",
    "Dato sorprendente": r"\b(el \d+ ?%|\d+ ?%|estudio|según|dato|cifras?)\b",
}

CTA = re.compile(
    r"(comenta\s+\w+|escríbeme|mándame|dm\b|mensaje directo|link en (la )?bio|enlace en (la )?bio|"
    r"sígueme|sígueme|sigue la cuenta|guarda este|comparte|suscríbete|agenda (una )?(llamada|demo))",
    re.I)

# Dolor del nicho: clínica de estética → atención, agenda, ausencias, WhatsApp
NICHO = {
    "dolor_clinica": r"\b(clínica|estética|cita|citas|agenda|recepción|recepcionista|paciente|clienta|tratamiento|botox|láser|depilación|no show|no se presenta|llamadas? perdidas?|whatsapp)\b",
    "ia_automatizacion": r"\b(ia|inteligencia artificial|agente|chatbot|automatiza\w*|bot|asistente virtual|chatgpt)\b",
    "dueno_negocio": r"\b(dueñ[oa]|negocio|emprendedor\w*|empresa|autónom[oa]|facturación|ventas|captar|leads?)\b",
}


def num(x, d=2):
    return None if x is None else round(x, d)


def metricas(d):
    v, s, dias = d["visitas"], d.get("seguidores"), d.get("dias_publicado")
    m = {
        "ratio_visitas_seguidores": num(v / s) if s else None,
        "engagement_pct": num(100 * (d["likes"] + d["comentarios"]) / v) if v else None,
        "comentarios_por_mil_visitas": num(1000 * d["comentarios"] / v) if v else None,
        "visitas_dia": round(v / max(dias, 1)) if dias is not None else None,
        "multiplo_mediana_cuenta": num(v / d["mediana_cuenta"], 1) if d.get("mediana_cuenta") else None,
    }
    razones = []
    if m["ratio_visitas_seguidores"] and m["ratio_visitas_seguidores"] >= 3:
        razones.append(f"ratio visitas/seguidores {m['ratio_visitas_seguidores']} (≥ 3)")
    if m["multiplo_mediana_cuenta"] and m["multiplo_mediana_cuenta"] >= 10:
        razones.append(f"{m['multiplo_mediana_cuenta']}x la mediana de su cuenta (≥ 10x)")
    if m["engagement_pct"] and m["engagement_pct"] >= 5:
        razones.append(f"engagement {m['engagement_pct']} % (≥ 5 %)")
    m["viral"] = bool(razones)
    m["razones_viral"] = razones
    return m


def gancho(d):
    segs = d.get("segmentos") or []
    if segs:
        frase = " ".join(s["text"] for s in segs if s["start"] <= 3.5).strip()
        if frase:
            return frase
    t = d.get("transcripcion") or d.get("titulo") or ""
    return " ".join(t.split()[:15])


def mecanismos(d):
    primeros = gancho(d)
    todo = " ".join(filter(None, [d.get("transcripcion"), d.get("titulo"), d.get("descripcion")])).lower()
    pts = {}
    for nombre, patron in MECANISMOS.items():
        en_gancho = len(re.findall(patron, primeros.lower(), re.I | re.M))
        en_todo = len(re.findall(patron, todo, re.I | re.M))
        puntos = en_gancho * 3 + en_todo
        if puntos:
            pts[nombre] = puntos
    return sorted(pts.items(), key=lambda x: -x[1])


def estructura(d):
    dur = d.get("duracion_s")
    segs = d.get("segmentos") or []
    if not dur or not segs:
        return []
    tramos = [("Gancho", 0, min(3, dur)), ("Desarrollo", 3, dur * 0.7),
              ("Giro / prueba", dur * 0.7, dur * 0.9), ("Cierre / CTA", dur * 0.9, dur + 1)]
    out = []
    for nombre, a, b in tramos:
        texto = " ".join(s["text"] for s in segs if a <= s["start"] < b).strip()
        out.append((nombre, round(a), round(min(b, dur)), texto[:220]))
    return out


def detectar_cta(d):
    txt = " ".join(filter(None, [d.get("transcripcion"), d.get("descripcion")]))
    return sorted({m.group(0).lower() for m in CTA.finditer(txt)})


def adaptabilidad(d, mec, cta):
    txt = " ".join(filter(None, [d.get("transcripcion"), d.get("titulo"), d.get("descripcion")])).lower()
    hits = {k: len(re.findall(p, txt, re.I)) for k, p in NICHO.items()}
    top = {m for m, _ in mec[:2]}
    # 1. Mecanismo trasladable a un dolor real de clínica
    trasladables = {"Error común / mito", "Miedo a perder dinero/clientes", "Lista / número",
                    "Demostración / tutorial", "Antes / después", "Dato sorprendente", "Pregunta / curiosidad"}
    c1 = 2.5 if top & trasladables and (hits["dolor_clinica"] or "Miedo a perder dinero/clientes" in top) \
        else 1.5 if top & trasladables else 0.5
    # 2. Grabable con el avatar (cara a cámara/voz): descarta formatos que dependen de otra persona/escenario
    c2 = 2.5 if (d.get("duracion_s") or 0) <= 75 and not re.search(r"\b(baile|trend|challenge|prank)\b", txt) else 1.0
    # 3. Atrae a dueño/gerente, no a clienta final
    c3 = 2.5 if hits["dueno_negocio"] or hits["ia_automatizacion"] else 1.0 if hits["dolor_clinica"] else 0.5
    # 4. Lleva a conversación/lead
    c4 = 2.5 if cta else 1.0
    total = round(c1 + c2 + c3 + c4, 1)
    decision = "HACER" if total >= 7.5 else "ADAPTAR" if total >= 5 else "DESCARTAR"
    return {"criterios": [c1, c2, c3, c4], "total": total, "decision": decision, "hits": hits}


# ----------------------------------------------------------------------------
# 3. Informe
# ----------------------------------------------------------------------------

def fmt(x, suf=""):
    return "n/d" if x is None else f"{x:,}{suf}".replace(",", ".") if isinstance(x, int) else f"{x}{suf}"


def informe(d):
    m = metricas(d)
    mec = mecanismos(d)
    cta = detectar_cta(d)
    ad = adaptabilidad(d, mec, cta)
    L = []
    L.append(f"# Análisis viral · {d.get('cuenta') or '?'}\n")
    L.append(f"{d['url']}\n")
    L.append("## Datos\n")
    L.append("| Visitas | Likes | Comentarios | Seguidores | Días | Duración |")
    L.append("|---|---|---|---|---|---|")
    L.append(f"| {fmt(d['visitas'])} | {fmt(d['likes'])} | {fmt(d['comentarios'])} | "
             f"{fmt(d.get('seguidores'))} | {fmt(d.get('dias_publicado'))} | {fmt(d.get('duracion_s'), ' s')} |\n")
    L.append("| Ratio visitas/seguidores | Engagement | Comentarios/1000 visitas | Visitas/día | x mediana cuenta |")
    L.append("|---|---|---|---|---|")
    L.append(f"| {fmt(m['ratio_visitas_seguidores'])} | {fmt(m['engagement_pct'], ' %')} | "
             f"{fmt(m['comentarios_por_mil_visitas'])} | {fmt(m['visitas_dia'])} | "
             f"{fmt(m['multiplo_mediana_cuenta'], 'x')} |\n")
    if m["viral"]:
        L.append("**Veredicto: viral.** Cumple: " + "; ".join(m["razones_viral"]) + ".\n")
    else:
        L.append("**Veredicto: no se puede afirmar que sea viral** con estos datos "
                 "(ninguna de las tres señales llega al umbral). "
                 + ("" if d.get("seguidores") else "Falta el nº de seguidores, así que el ratio no se puede calcular. ")
                 + ("" if d.get("mediana_cuenta") else "Usa --cuenta para comparar con el resto de vídeos de la cuenta.")
                 + "\n")
    L.append("## Por qué ha funcionado\n")
    L.append(f"- **Gancho (0-3 s):** «{gancho(d) or 'sin transcripción'}»")
    if mec:
        L.append("- **Mecanismo principal:** " + mec[0][0]
                 + (f" (secundario: {mec[1][0]})" if len(mec) > 1 else ""))
    else:
        L.append("- **Mecanismo principal:** no detectado por texto; revisa el vídeo (puede ser visual).")
    L.append(f"- **CTA:** {', '.join(cta) if cta else 'no se detecta CTA explícito'}")
    if m["comentarios_por_mil_visitas"] is not None:
        c = m["comentarios_por_mil_visitas"]
        L.append(f"- **Conversación:** {c} comentarios por cada 1.000 visitas "
                 + ("(alto: el vídeo provoca respuesta)." if c >= 5 else "(normal o bajo)."))
    if d.get("hashtags"):
        L.append("- **Hashtags:** " + " ".join(d["hashtags"][:10]))
    est = estructura(d)
    if est:
        L.append("\n## Estructura\n")
        for n, a, b, t in est:
            L.append(f"- **{n} ({a}-{b} s):** {t or '—'}")
    L.append("\n## Adaptabilidad a clínicas de estética (Sevilla)\n")
    c = ad["criterios"]
    L.append(f"| Mecanismo → dolor de clínica | Grabable con tu avatar | Atrae al dueño | Lleva a lead | **Total** |")
    L.append("|---|---|---|---|---|")
    L.append(f"| {c[0]} | {c[1]} | {c[2]} | {c[3]} | **{ad['total']}/10** |\n")
    L.append(f"**Decisión: {ad['decision']}.**")
    L.append("_Puntuación automática por palabras clave; es una primera criba, no sustituye a verlo._\n")
    L.append("> Se copia el mecanismo, no las frases. Mismo avatar, paleta y tono en todo.")
    return "\n".join(L), {"metricas": m, "mecanismos": mec, "cta": cta, "adaptabilidad": ad}


def analisis_claude(d, resumen, modelo):
    """Opcional: redacta el análisis completo y un guion adaptado con la API de Claude."""
    import anthropic
    cliente = anthropic.Anthropic()
    prompt = (
        "Eres experta en marketing de contenido corto con 20 años de experiencia. Español de España, "
        "sin lenguaje de anuncio, datos concretos antes que adjetivos.\n"
        "Cliente: Rocío Pineda, Agencia de Agentes IA. Objetivo único: captar dueños de clínicas de "
        "estética en Sevilla (atención al cliente, agendar citas, automatizar tareas con agentes IA).\n\n"
        "Analiza por qué se ha hecho viral este vídeo y si el mecanismo se puede trasladar a ese nicho. "
        "Estructura: 1) Por qué se hizo viral (mecanismo único principal, con datos), 2) Contexto "
        "(por qué ese tema/formato/momento), 3) Qué se copia y qué NO, 4) Decisión HACER/ADAPTAR/DESCARTAR "
        "con una sola recomendación, 5) si no es DESCARTAR: guion adaptado por tramos de segundos con CTA a "
        "lead (comenta una palabra clave). Mismo avatar y tono de Rocío. Si falta un dato, dilo.\n\n"
        f"DATOS:\n{json.dumps({k: v for k, v in d.items() if k != 'segmentos'}, ensure_ascii=False)[:9000]}\n\n"
        f"ANÁLISIS AUTOMÁTICO PREVIO:\n{json.dumps(resumen, ensure_ascii=False, default=str)[:3000]}"
    )
    r = cliente.messages.create(model=modelo, max_tokens=2500,
                                messages=[{"role": "user", "content": prompt}])
    return r.content[0].text


# ----------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Analiza por qué un vídeo se ha hecho viral.")
    p.add_argument("url", nargs="?")
    p.add_argument("--json", help="usar datos ya extraídos (sin red)")
    p.add_argument("--cuenta", action="store_true", help="comparar con los últimos vídeos de la cuenta")
    p.add_argument("--claude", action="store_true", help="análisis redactado con API de Claude (ANTHROPIC_API_KEY)")
    p.add_argument("--modelo-claude", default="claude-sonnet-5-5")
    p.add_argument("--modelo", default="small", help="modelo Whisper: base (rápido) o small (mejor)")
    p.add_argument("--sin-whisper", action="store_true", help="no transcribir con Whisper")
    p.add_argument("--cookies-navegador", help="chrome|firefox|edge — necesario para Instagram privado/con login")
    a = p.parse_args()
    if not a.url and not a.json:
        p.error("pasa una URL o --json")

    if a.json:
        d = json.load(open(a.json, encoding="utf-8"))
    else:
        try:
            d = construir_datos(a.url, a)
        except Exception as e:  # noqa: BLE001
            sys.exit(f"ERROR extrayendo el vídeo: {e}\n"
                     "· Actualiza yt-dlp: pip install -U yt-dlp\n"
                     "· Instagram pide login: añade --cookies-navegador chrome (con la sesión abierta)\n"
                     "· Si no hay forma, sube el vídeo y pásalo a Claude para el análisis.")

    texto, resumen = informe(d)
    if a.claude:
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("Aviso: falta ANTHROPIC_API_KEY, se omite --claude", file=sys.stderr)
        else:
            texto += "\n\n---\n\n## Análisis redactado (Claude)\n\n" + analisis_claude(d, resumen, a.modelo_claude)

    CARPETA_INFORMES.mkdir(exist_ok=True)
    base = f"{dt.datetime.now():%Y%m%d_%H%M}_{re.sub(r'\\W+', '_', str(d.get('cuenta') or 'video'))[:30]}"
    (CARPETA_INFORMES / f"{base}.md").write_text(texto, encoding="utf-8")
    (CARPETA_INFORMES / f"{base}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(texto)
    print(f"\nGuardado en {CARPETA_INFORMES / (base + '.md')}")


if __name__ == "__main__":
    main()
