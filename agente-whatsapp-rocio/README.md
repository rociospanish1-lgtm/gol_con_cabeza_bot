# Agente IA de WhatsApp — Rocío Pineda

Agente que contesta en **tu propio WhatsApp** a las clínicas de tu lista (clientas y posibles clientas), con la información de la agencia, memoria de cada conversación y un interruptor para activarlo y desactivarlo.

## Qué hace

- Se vincula a tu WhatsApp como un **dispositivo más** (igual que WhatsApp Web). Sigues usando el móvil con normalidad.
- **Solo contesta a los números de tu lista de clínicas.** Familia, amigos, grupos y desconocidos: no los toca.
- **Memoria:** guarda cada conversación y una ficha por contacto (nombre, clínica, si es clienta o posible clienta, en qué punto está, objeciones, acuerdos). Relee los últimos 40 mensajes y la ficha antes de contestar.
- **Te avisa** en tu chat contigo misma cuando alguien quiere una demo, contratar, tiene una incidencia, pregunta algo que no sabe o pide hablar contigo.
- **Se aparta cuando entras tú:** si escribes en un chat que estaba llevando el agente, deja de contestar ahí durante 12 horas (configurable).
- Junta los mensajes seguidos (espera 6 segundos), marca como leído, aparece "escribiendo…" y contesta en formato WhatsApp.
- Se presenta como agente IA de Rocío en su primera respuesta (obligatorio por la ley europea de IA desde agosto de 2026, y además es tu mejor demo).
- Ve imágenes. Las notas de voz no las escucha: pide que se lo escriban.

Lo que sabe está en [`conocimiento.md`](conocimiento.md): servicios, precios de la web (297 € + IVA de alta, 39 €/mes + IVA), condiciones, objeciones y cómo cerrar una demo. Si cambias precios en la web, cámbialos ahí.

## Comandos (en tu chat contigo misma de WhatsApp)

| Comando | Qué hace |
|---|---|
| `#on` / `#off` | Activa o desactiva el agente para todos |
| `#estado` | Si está activo, cuántas clínicas hay y qué chats están en pausa |
| `#añadir 600111222 Clínica Aura` | Añade una clínica a la lista. Puedes pegar varias, una por línea |
| `#quitar 600111222` | La quita de la lista |
| `#lista` | Ver la lista |
| `#pausa 600111222` | El agente deja de contestar en ese chat hasta que lo reanudes |
| `#reanudar 600111222` / `#reanudar todo` | Vuelve a contestar |
| `#ficha 600111222` | Lo que el agente recuerda de ese contacto |
| `#olvidar 600111222` | Borra la memoria de ese contacto |
| `#ayuda` | Lista de comandos |

## Instalación recomendada: Railway (funciona 24 h sin tu ordenador)

Coste aproximado: Railway unos 5 $/mes + consumo de Claude (estimación: 1–2 céntimos por respuesta; con 30 respuestas al día, 10–20 €/mes. Revísalo en la consola de Anthropic la primera semana).

1. **Clave de Claude.** Entra en console.anthropic.com > API Keys > crea una clave y añade saldo (Billing).
2. **Railway.** En railway.com: *New Project* > *Deploy from GitHub repo* > elige `gol_con_cabeza_bot`.
3. En el servicio creado, *Settings*:
   - **Root Directory:** `agente-whatsapp-rocio`
   - **Volumes:** añade un volumen montado en `/data` (ahí se guardan la sesión de WhatsApp y la memoria; sin volumen, cada actualización te obliga a vincular de nuevo y se pierde la memoria).
   - **Networking:** *Generate Domain* (para la página de estado).
4. *Variables*:
   - `ANTHROPIC_API_KEY` = tu clave
   - `WHATSAPP_NUMERO` = `34692431897` (tu número, solo cifras)
   - `CLAVE_ACCESO` = una contraseña larga inventada
   - `PORT` = `8080`
   - `DISPONIBILIDAD_DEMOS` = tu horario para demos, por ejemplo `de lunes a viernes, de 10:00 a 13:00 y de 17:00 a 19:00`
5. **Vincula tu WhatsApp.** Abre `https://TU-DOMINIO.up.railway.app/?clave=TU_CLAVE_ACCESO` (o mira los *Logs*): aparece un código de 8 caracteres. En el móvil: WhatsApp > Ajustes > Dispositivos vinculados > Vincular un dispositivo > **Vincular con número de teléfono** > escribe el código.
6. Te llegará a tu chat contigo misma: *"🤖 Agente IA conectado"*. Añade tus clínicas con `#añadir` y escribe `#estado`.
7. **Prueba real:** añade el número de alguien de confianza con `#añadir` y que te escriba como si fuera una clínica.

## Instalación en tu ordenador (para probar)

Necesitas Node.js 22 o superior. El agente solo funciona mientras el ordenador esté encendido.

```bash
cd agente-whatsapp-rocio
npm install
cp .env.example .env      # y rellena ANTHROPIC_API_KEY (deja WHATSAPP_NUMERO vacío para usar QR)
npm run probar            # chatea con el agente en la terminal, sin WhatsApp
npm start                 # conecta con WhatsApp: escanea el QR que sale en pantalla
```

## Lo que tienes que saber antes de usarlo

- **Método no oficial de WhatsApp.** Funciona como WhatsApp Web, no con la API oficial de Meta. WhatsApp puede bloquear números que usan automatizaciones no oficiales. El riesgo es bajo porque solo contesta a una lista corta de clínicas que te escriben y no envía mensajes masivos, pero no es cero. **No lo uses para enviar mensajes en bloque.** La alternativa oficial (la API de Meta que usas con tus clientas) obliga a sacar el número de la app de WhatsApp o a contratar un proveedor intermedio.
- **El móvil tiene que conectarse al menos cada 14 días**; si no, WhatsApp desvincula los dispositivos.
- **Protección de datos:** las conversaciones con las clínicas se guardan en tu servidor y pasan por Claude (Anthropic) para generar la respuesta. Inclúyelo en tu política de privacidad.
- Si cierras la sesión del agente desde el móvil (Dispositivos vinculados > cerrar sesión), el agente pedirá vincular de nuevo.
- Revisa las conversaciones la primera semana y ajusta `conocimiento.md` con lo que veas.

## Archivos

- `conocimiento.md` — lo que sabe el agente (edítalo tú).
- `src/agente.js` — instrucciones de comportamiento y herramientas (ficha y avisos).
- `src/index.js` — conexión con WhatsApp, lista, pausas y avisos.
- `src/comandos.js` — comandos `#`.
- `src/db.js` — memoria (SQLite en `DATA_DIR`).
- `src/probar.js` — prueba en la terminal.
