# Agente de WhatsApp con IA

Atiende a tus clientes por WhatsApp, recoge sus datos, les ofrece la cita y te avisa a ti cuando hace falta
una persona. Lo enciendes y lo apagas cuando quieras.

## Cómo se controla

**Desde tu WhatsApp personal** (el número de `ADMIN_NUMEROS`), escribiendo al número del negocio:

| Comando | Qué hace |
|---|---|
| `#on` | Activa el bot |
| `#off` | Lo desactiva: no responde a nadie (los mensajes se guardan) |
| `#estado` | Te dice si está activo y qué chats están pausados |
| `#pausar 34611222333` | El bot deja de responder solo a ese cliente (`#pausar 34611222333 24` = 24 horas) |
| `#reanudar 34611222333` | El bot vuelve a atender a ese cliente |

**Desde el navegador del móvil**: `https://TU-SERVIDOR/panel?token=TU_ADMIN_TOKEN`. Un botón para activar
o desactivar y la lista de chats pausados. Guárdalo en la pantalla de inicio.

**Automático**:
- Si el cliente pide una persona, quiere contratar o se queja, el bot te manda un aviso con un resumen y el
  enlace al chat, y se calla en esa conversación hasta que mandes `#reanudar`.
- Si contestas tú a mano desde la app WhatsApp Business (modo coexistencia), el bot se calla en ese chat
  durante `HORAS_PAUSA_MANUAL` horas (12 por defecto).

## Puesta en marcha (unos 60-90 minutos la primera vez)

### 1. Número de WhatsApp
Recomendado: **coexistencia**, que conecta tu número actual de WhatsApp Business a la API sin dejar de usar
la app. Así sigues viendo y contestando todo desde el móvil cuando el bot está apagado. Comprueba al
darlo de alta que tu número lo admite; si no, usa un número nuevo solo para el agente.

1. Entra en <https://developers.facebook.com>, crea una app de tipo **Empresa** y añade el producto **WhatsApp**.
2. Vincula tu cuenta de Meta Business y tu número.
3. Apunta: **Identificador del número de teléfono** (`WHATSAPP_PHONE_NUMBER_ID`) y genera un **token
   permanente** con un usuario del sistema en business.facebook.com (`WHATSAPP_TOKEN`). El token
   temporal caduca en 24 h.
4. En Configuración de la app > Básica, copia la **clave secreta** (`WHATSAPP_APP_SECRET`).

### 2. Clave de Claude
En <https://console.anthropic.com> > API Keys crea una clave (`ANTHROPIC_API_KEY`) y añade saldo.

### 3. Rellena la base de conocimiento
Edita `conocimiento.md` y sustituye cada `[RELLENAR]`. El agente solo responde con lo que hay ahí; lo que
no esté, te lo pasa a ti en lugar de inventarlo.

### 4. Despliega el servidor
Necesita una URL pública con HTTPS. Opción sencilla: Railway o Render.
1. Sube este repositorio y configura el directorio raíz del servicio en `whatsapp_agent`
   (usa el `Dockerfile` de esta carpeta).
2. Copia las variables de `.env.example` en el panel de variables del servicio y rellénalas.
3. Monta un volumen persistente en `/app/data` (ahí se guarda el estado on/off y el historial).
4. Comprueba que `https://TU-SERVIDOR/salud` responde `{"ok": true, ...}`.

### 5. Conecta el webhook en Meta
En tu app > WhatsApp > Configuración:
- URL de devolución de llamada: `https://TU-SERVIDOR/webhook`
- Token de verificación: el mismo valor que pusiste en `WHATSAPP_VERIFY_TOKEN`
- Suscríbete al campo **messages** (y a **smb_message_echoes** si usas coexistencia).

### 6. Prueba
1. Desde tu móvil personal manda `#estado` al número del negocio: debe contestarte.
2. Pide a otra persona que escriba como si fuera un cliente.
3. Manda `#off`, que te vuelva a escribir y comprueba que el bot no responde. Después, `#on`.

## Avisos importantes
- **Ventana de 24 horas de WhatsApp**: el bot solo puede escribirte avisos a tu móvil personal si tú le has
  escrito al número del negocio en las últimas 24 horas. Manda `#estado` cada mañana para mantenerla abierta.
- El bot se presenta siempre como asistente virtual. No lo cambies: la normativa europea (AI Act) obliga a
  informar de que se habla con una IA.
- Audios e imágenes: el bot no los escucha ni los ve. Pide al cliente que lo escriba.
- Protección de saldo: si alguien supera `MAX_RESPUESTAS_HORA` (30 por defecto), el bot se pausa 1 hora en
  ese chat y te avisa.

## Coste orientativo
- WhatsApp: las respuestas a clientes que te escriben primero (dentro de 24 h) no tienen coste de Meta.
- Claude (`claude-opus-5-5` con esfuerzo `low`): del orden de 1-2 céntimos por respuesta. Para gastar menos,
  cambia `CLAUDE_MODEL=claude-sonnet-5-5`.
- Servidor: 5-10 €/mes en Railway o Render.

## Desarrollo
```bash
pip install -r requirements.txt pytest
pytest -q tests
uvicorn app:app --reload
```
