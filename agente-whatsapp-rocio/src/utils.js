// Utilidades: números de teléfono, fechas y textos.

// Deja solo dígitos y añade el prefijo de España a los móviles de 9 cifras.
export function normalizarNumero(entrada) {
  let n = String(entrada || "").replace(/[^\d]/g, "");
  if (n.startsWith("00")) n = n.slice(2);
  if (n.length === 9 && /^[6789]/.test(n)) n = "34" + n;
  return n.length >= 10 && n.length <= 15 ? n : null;
}

// "34600111222@s.whatsapp.net" o "34600111222:12@s.whatsapp.net" -> "34600111222"
export function numeroDeJid(jid) {
  if (!jid) return null;
  const m = String(jid).match(/^(\d+)(?::\d+)?@s\.whatsapp\.net$/);
  return m ? m[1] : null;
}

export function formatearNumero(n) {
  if (n?.startsWith("34") && n.length === 11) {
    const r = n.slice(2);
    return `+34 ${r.slice(0, 3)} ${r.slice(3, 5)} ${r.slice(5, 7)} ${r.slice(7)}`;
  }
  return "+" + n;
}

const ZONA = "Europe/Madrid";

// Marca de tiempo corta para el historial: "mar 04/11 18:05"
export function marcaTiempo(ts) {
  const d = new Date(ts);
  const dia = new Intl.DateTimeFormat("es-ES", { weekday: "short", timeZone: ZONA })
    .format(d)
    .replace(".", "");
  const fecha = new Intl.DateTimeFormat("es-ES", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: ZONA,
  }).format(d);
  return `${dia} ${fecha.replace(",", "")}`;
}

export function fechaLarga(ts = Date.now()) {
  return new Intl.DateTimeFormat("es-ES", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: ZONA,
  }).format(new Date(ts));
}

export function horaCorta(ts) {
  return new Intl.DateTimeFormat("es-ES", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: ZONA,
  }).format(new Date(ts));
}

export const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

// Saca el texto (o una descripción) de cualquier tipo de mensaje de WhatsApp.
export function describirMensaje(message) {
  if (!message) return { texto: null, tipo: "vacio" };
  const m =
    message.ephemeralMessage?.message ||
    message.viewOnceMessage?.message ||
    message.viewOnceMessageV2?.message ||
    message.documentWithCaptionMessage?.message ||
    message.editedMessage?.message?.protocolMessage?.editedMessage ||
    message;

  if (m.conversation) return { texto: m.conversation, tipo: "texto" };
  if (m.extendedTextMessage?.text) return { texto: m.extendedTextMessage.text, tipo: "texto" };
  if (m.imageMessage)
    return { texto: `[Imagen]${m.imageMessage.caption ? " " + m.imageMessage.caption : ""}`, tipo: "imagen" };
  if (m.videoMessage)
    return { texto: `[Vídeo]${m.videoMessage.caption ? " " + m.videoMessage.caption : ""}`, tipo: "video" };
  if (m.audioMessage) return { texto: "[Nota de voz: no puedes escucharla]", tipo: "audio" };
  if (m.documentMessage)
    return {
      texto: `[Documento: ${m.documentMessage.fileName || "sin nombre"}]${m.documentMessage.caption ? " " + m.documentMessage.caption : ""}`,
      tipo: "documento",
    };
  if (m.stickerMessage) return { texto: "[Sticker]", tipo: "sticker" };
  if (m.locationMessage) return { texto: "[Ubicación compartida]", tipo: "ubicacion" };
  if (m.contactMessage) return { texto: `[Contacto compartido: ${m.contactMessage.displayName || ""}]`, tipo: "contacto" };
  if (m.buttonsResponseMessage?.selectedDisplayText)
    return { texto: m.buttonsResponseMessage.selectedDisplayText, tipo: "texto" };
  if (m.listResponseMessage?.title) return { texto: m.listResponseMessage.title, tipo: "texto" };
  // Reacciones, borrados, confirmaciones de lectura, etc.: no son mensajes que contestar.
  return { texto: null, tipo: "ignorar" };
}
