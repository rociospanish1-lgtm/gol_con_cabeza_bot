---
name: crear-video-reels
description: "Produce el vídeo final de un reel/TikTok para la Agencia de Agentes IA de Rocío Pineda (clínicas de estética en Sevilla): guion hablado, escenas, avatar/clon idéntico, paleta de rociopinedaia.es, subtítulos, voz y exportación vertical 9:16. Úsalo siempre que Rocío pida crear, montar, generar o producir un vídeo, reel, TikTok o short, aunque no diga 'skill'; si solo pide ideas, usa ideas-reels-agentes-ia primero y luego esta."
---

# Crear vídeo (reel/TikTok) — Agencia de Agentes IA

## Objetivo
Cada vídeo existe para generar conversaciones por DM con dueñas/os de clínicas de estética en Sevilla, no para sumar vistas. Un vídeo sin CTA con palabra clave no está terminado.

## Entradas
- Idea o guion de `ideas-reels-agentes-ia` (si no hay, pídela o genera una con esa skill; no inventes ideas fuera de las del proyecto).
- Si Rocío no dice formato: avatar/clon hablando a cámara + texto en pantalla + 1 plano de demo (WhatsApp del agente o demo Nova), 20-30 s, 9:16.

## Flujo
1. **Guion hablado** (español de España, directo, sin lenguaje de anuncio). Estructura: gancho 0-3 s con el nicho nombrado ("Si tienes una clínica de estética…") → un único beneficio medible → demo → CTA con palabra clave ("Comenta CITA"). Cifras concretas; si es dato de mercado, márcalo "verificar antes de publicar". Di "agente IA", nunca "bot". Sin jerga (n8n, API, LLM).
2. **Plan de escenas**: tabla con segundo, qué se ve, voz, texto en pantalla (marca qué palabra lleva degradado). Máximo 1 cambio de plano cada 2-3 s.
3. **Producción**. Elige la herramienta por este orden y no ofrezcas alternativas a Rocío, decide tú:
   - Avatar/clon hablando: el avatar guardado de Rocío (ver `references/avatar-y-marca.md`). Nunca cambies cara, ropa, fondo ni voz salvo que lo pida expresamente.
   - Composición con texto/gráficos de marca: HyperFrames (`compose`) o Canva (`create-video`), según cuál esté conectado.
   - Voz en off, música, b-roll o clips: vidIQ (`vidiq_voiceover_generate`, `vidiq_generate_music`, `vidiq_find_broll`).
   - Subtítulos y exportación sobre grabación real: OpusClip (`build_captions`, `start_export`) o Eddie.
   Antes de gastar créditos, di en una línea qué herramienta usarás y cuánto gasta si lo sabes (`get_pricing`, `get_credit_balance`).
4. **Revisión previa a entregar** (checklist de abajo). Corrige antes de mostrar.
5. **Entrega**: enlace/archivo del vídeo, caption, hashtags y la palabra clave del CTA con el texto de la respuesta automática por DM. Termina con UNA recomendación de cuándo publicar.

## Checklist (todo debe cumplirse)
- Nicho nombrado en el primer segundo.
- Un solo beneficio, con cifra.
- Avatar idéntico al de vídeos anteriores.
- Solo colores de la paleta; palabra clave del gancho con degradado cian→violeta.
- Subtítulos legibles, dentro de la zona segura (deja libre ~15 % inferior y ~10 % superior).
- 9:16, 15-35 s, CTA con palabra clave al final y en texto en pantalla.
- Sin promesas médicas ni resultados estéticos garantizados; sin datos de clientas reales.

## Reglas
- Si falta un dato (avatar sin definir, herramienta no conectada), dilo en una línea y propón lo mínimo para avanzar; no inventes.
- No publiques por Rocío: prepara el borrador y que ella confirme.
- Evita 22:00 y tres reels seguidos al recomendar el momento de publicación.

Detalle de marca y avatar: `references/avatar-y-marca.md`.
