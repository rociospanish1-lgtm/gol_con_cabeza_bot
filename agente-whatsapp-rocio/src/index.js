// Agente IA de WhatsApp de Rocío Pineda.
// Se vincula a tu WhatsApp como un dispositivo más (igual que WhatsApp Web) y
// contesta solo a los números de tu lista de clínicas.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import pino from "pino";
import QRCode from "qrcode";
import makeWASocket, {
  Browsers,
  DisconnectReason,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
  isJidGroup,
  isJidBroadcast,
  isJidNewsletter,
  isLidUser,
  jidNormalizedUser,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";
import { abrirDB } from "./db.js";
import { crearAgente } from "./agente.js";
import { crearComandos } from "./comandos.js";
import {
  describirMensaje,
  esperar,
  formatearNumero,
  normalizarNumero,
  numeroDeJid,
} from "./utils.js";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
if (fs.existsSync(path.join(RAIZ, ".env"))) process.loadEnvFile(path.join(RAIZ, ".env"));

const env = process.env;
const CFG = {
  dataDir: path.resolve(RAIZ, env.DATA_DIR || "data"),
  numeroWhatsapp: normalizarNumero(env.WHATSAPP_NUMERO),
  modelo: env.MODELO || "claude-opus-5-5",
  esfuerzo: env.ESFUERZO || "low",
  activoAlArrancar: (env.ACTIVO_AL_ARRANCAR || "si").toLowerCase() !== "no",
  historialMax: Number(env.HISTORIAL_MAX || 40),
  esperaMs: Number(env.ESPERA_SEGUNDOS || 6) * 1000,
  pausaHumanoHoras: Number(env.PAUSA_HUMANO_HORAS || 12),
  disponibilidadDemos: env.DISPONIBILIDAD_DEMOS || "de lunes a viernes, de 10:00 a 13:00 y de 17:00 a 19:00",
  conocimientoPath: path.join(RAIZ, "conocimiento.md"),
  puerto: Number(env.PORT || 0),
  claveAcceso: env.CLAVE_ACCESO || "",
};

if (!env.ANTHROPIC_API_KEY && !env.ANTHROPIC_AUTH_TOKEN) {
  console.error("Falta ANTHROPIC_API_KEY en el archivo .env o en las variables del servidor.");
  process.exit(1);
}

const log = pino({ level: env.LOG_LEVEL || "info", base: undefined });
const db = abrirDB(CFG.dataDir);
const agente = crearAgente(CFG);
const ejecutarComando = crearComandos(db, CFG);

let sock = null;
let miJid = null; // 346xxxxxxxx@s.whatsapp.net
let miLid = null; // xxxxx@lid
let estadoConexion = "arrancando";
let qrActual = null;
let codigoVinculacion = null;
const idsEnviadosPorAgente = new Set();
const idsProcesados = new Set();
let reintentos = 0;

// ---------------------------------------------------------------------------
// Identificar quién escribe
// ---------------------------------------------------------------------------
async function numeroDelChat(key) {
  const jid = key.remoteJid;
  const directo = numeroDeJid(jid);
  if (directo) return directo;
  const alt = numeroDeJid(key.remoteJidAlt);
  if (alt) return alt;
  if (isLidUser(jid)) {
    try {
      const pn = await sock.signalRepository.lidMapping.getPNForLID(jid);
      return numeroDeJid(pn);
    } catch {
      return null;
    }
  }
  return null;
}

function esMiChat(jid) {
  const n = jidNormalizedUser(jid);
  return n === miJid || (miLid && n === miLid);
}

// ---------------------------------------------------------------------------
// Envío de mensajes
// ---------------------------------------------------------------------------
async function enviar(jid, texto) {
  const r = await sock.sendMessage(jid, { text: texto });
  if (r?.key?.id) {
    idsEnviadosPorAgente.add(r.key.id);
    if (idsEnviadosPorAgente.size > 2000) idsEnviadosPorAgente.delete(idsEnviadosPorAgente.values().next().value);
  }
  return r;
}

async function avisarme(texto) {
  if (!miJid) return;
  try {
    await enviar(miJid, texto);
  } catch (e) {
    log.error({ err: e.message }, "No se pudo enviar el aviso a Rocío");
  }
}

// ---------------------------------------------------------------------------
// Cola por chat: espera unos segundos para juntar mensajes seguidos y
// procesa cada chat de uno en uno.
// ---------------------------------------------------------------------------
const colas = new Map(); // numero -> { jid, nombreWhatsapp, imagenes, timer, ocupado, pendiente }

function encolar(numero, jid, nombreWhatsapp, imagen) {
  const c = colas.get(numero) || { imagenes: [], ocupado: false, pendiente: false };
  c.jid = jid;
  if (nombreWhatsapp) c.nombreWhatsapp = nombreWhatsapp;
  if (imagen) c.imagenes.push(imagen);
  clearTimeout(c.timer);
  c.timer = setTimeout(() => procesar(numero), CFG.esperaMs);
  colas.set(numero, c);
}

async function procesar(numero) {
  const c = colas.get(numero);
  if (!c) return;
  if (c.ocupado) {
    c.pendiente = true;
    return;
  }
  c.ocupado = true;
  c.pendiente = false;
  const imagenes = c.imagenes.splice(0);
  try {
    if (!db.estaActivo(CFG.activoAlArrancar) || db.pausaActiva(numero) || !db.getClinica(numero)) return;

    await sock.sendPresenceUpdate("composing", c.jid).catch(() => {});
    const clinica = db.getClinica(numero);
    const { texto, error } = await agente.responder({
      numero,
      nombreLista: clinica?.nombre,
      nombreWhatsapp: c.nombreWhatsapp,
      historial: db.historial(numero, CFG.historialMax),
      ficha: db.getFicha(numero),
      imagenes,
      acciones: {
        guardarFicha: (datos) => db.guardarFicha(numero, datos),
        avisarRocio: async ({ motivo, resumen, urgente }) => {
          const ficha = db.getFicha(numero);
          const quien = [clinica?.nombre, ficha?.nombre, c.nombreWhatsapp].filter(Boolean).join(" · ");
          await avisarme(
            `🔔 *${motivo.replace(/_/g, " ").toUpperCase()}*${urgente ? " (te toca a ti)" : ""}\n` +
              `${quien || "Contacto"} — ${formatearNumero(numero)}\n` +
              `wa.me/${numero}\n\n${resumen}` +
              (urgente ? `\n\nHe pausado el agente en este chat. Para que vuelva a contestar: #reanudar ${numero}` : ""),
          );
          if (urgente) db.pausar(numero, 0, `urgente: ${motivo}`);
        },
      },
    });

    if (error) {
      log.warn({ numero, error }, "El agente no ha podido responder");
      await avisarme(`⚠️ El agente no ha podido contestar a ${clinica?.nombre || formatearNumero(numero)} (${error}). Contéstale tú: wa.me/${numero}`);
    }
    if (texto) {
      // Pausa breve proporcional al texto para que se vea natural.
      await esperar(Math.min(1500 + texto.length * 25, 7000));
      // Si Rocío ha entrado en el chat mientras tanto, no enviamos.
      const pausa = db.pausaActiva(numero);
      if (pausa && !pausa.motivo?.startsWith("urgente")) return;
      await enviar(c.jid, texto);
      db.guardarMensaje(numero, "assistant", "agente", texto);
      log.info({ numero, texto }, "Respuesta enviada");
    }
  } catch (e) {
    log.error({ numero, err: e.message }, "Error procesando el chat");
    await avisarme(`⚠️ Error del agente con ${formatearNumero(numero)}: ${e.message}. Contéstale tú: wa.me/${numero}`);
  } finally {
    await sock.sendPresenceUpdate("paused", c.jid).catch(() => {});
    c.ocupado = false;
    if (c.pendiente) procesar(numero);
  }
}

// ---------------------------------------------------------------------------
// Mensajes entrantes
// ---------------------------------------------------------------------------
async function alRecibir(msg) {
  const key = msg.key;
  const jid = key?.remoteJid;
  if (!jid || isJidGroup(jid) || isJidBroadcast(jid) || isJidNewsletter(jid)) return;

  const { texto, tipo } = describirMensaje(msg.message);
  if (!texto || tipo === "ignorar") return;

  // Ignorar mensajes antiguos (p. ej. al reconectar tras mucho tiempo).
  const ts = Number(msg.messageTimestamp || 0) * 1000 || Date.now();
  if (Date.now() - ts > 24 * 3600_000) return;

  // 1) Tu chat contigo misma: comandos.
  if (esMiChat(jid)) {
    if (!key.fromMe || idsEnviadosPorAgente.has(key.id)) return;
    if (!texto.trim().startsWith("#")) return;
    const respuesta = await ejecutarComando(texto);
    if (respuesta) await avisarme(respuesta);
    return;
  }

  const numero = await numeroDelChat(key);
  if (!numero || !db.getClinica(numero)) return; // No está en la lista: el agente no hace nada.

  // 2) Mensajes que envías tú desde el móvil en un chat de la lista.
  if (key.fromMe) {
    if (idsEnviadosPorAgente.has(key.id)) return; // lo envió el agente
    db.guardarMensaje(numero, "assistant", "rocio", texto, ts);
    // Si entras en una conversación que estaba llevando el agente, se aparta.
    const ultimaAgente = db.ultimaRespuestaAgente(numero);
    if (CFG.pausaHumanoHoras > 0 && Date.now() - ultimaAgente < 48 * 3600_000 && !db.pausaActiva(numero)) {
      db.pausar(numero, CFG.pausaHumanoHoras, "Rocío ha escrito");
      await avisarme(
        `✋ Has escrito a ${db.getClinica(numero)?.nombre || formatearNumero(numero)}: el agente se aparta de ese chat durante ${CFG.pausaHumanoHoras} h.\nPara que vuelva antes: #reanudar ${numero}`,
      );
    }
    return;
  }

  // 3) Mensaje de una clínica de la lista.
  db.guardarMensaje(numero, "user", "clienta", texto, ts);
  sock.readMessages([key]).catch(() => {});

  let imagen = null;
  if (tipo === "imagen") {
    try {
      const buffer = await downloadMediaMessage(msg, "buffer", {});
      const mime = msg.message?.imageMessage?.mimetype?.split(";")[0] || "image/jpeg";
      if (buffer.length < 4_500_000 && ["image/jpeg", "image/png", "image/webp", "image/gif"].includes(mime)) {
        imagen = { mime, base64: buffer.toString("base64") };
      }
    } catch (e) {
      log.warn({ err: e.message }, "No se pudo descargar la imagen");
    }
  }
  encolar(numero, jid, msg.pushName, imagen);
}

// ---------------------------------------------------------------------------
// Conexión con WhatsApp
// ---------------------------------------------------------------------------
async function conectar() {
  const carpetaSesion = path.join(CFG.dataDir, "sesion-whatsapp");
  const { state, saveCreds } = await useMultiFileAuthState(carpetaSesion);
  const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: undefined }));

  sock = makeWASocket({
    version,
    auth: state,
    logger: pino({ level: "silent" }),
    browser: Browsers.macOS("Desktop"),
    markOnlineOnConnect: false,
    syncFullHistory: false,
  });
  let codigoPedido = false;

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", async (u) => {
    const { connection, lastDisconnect, qr } = u;
    if (qr) {
      qrActual = qr;
      estadoConexion = "esperando vinculación";
      if (CFG.numeroWhatsapp && !codigoPedido && !state.creds.registered) {
        codigoPedido = true;
        try {
          codigoVinculacion = await sock.requestPairingCode(CFG.numeroWhatsapp);
          console.log(
            `\n=====================================================\n` +
              ` CÓDIGO PARA VINCULAR TU WHATSAPP: ${codigoVinculacion}\n` +
              ` En el móvil: WhatsApp > Ajustes > Dispositivos vinculados >\n` +
              ` Vincular un dispositivo > Vincular con número de teléfono\n` +
              `=====================================================\n`,
          );
        } catch (e) {
          log.error({ err: e.message }, "No se pudo pedir el código de vinculación; usa el QR");
        }
      }
      if (!CFG.numeroWhatsapp) {
        console.log("\nEscanea este QR en WhatsApp > Dispositivos vinculados > Vincular un dispositivo:\n");
        console.log(await QRCode.toString(qr, { type: "terminal", small: true }));
      }
    }
    if (connection === "open") {
      qrActual = null;
      codigoVinculacion = null;
      reintentos = 0;
      estadoConexion = "conectado";
      miJid = jidNormalizedUser(sock.user.id);
      miLid = sock.user.lid ? jidNormalizedUser(sock.user.lid) : null;
      log.info({ miJid }, "Conectado a WhatsApp");
      const activo = db.estaActivo(CFG.activoAlArrancar);
      await avisarme(
        `🤖 Agente IA conectado. Estado: *${activo ? "ACTIVADO" : "DESACTIVADO"}*. Clínicas en la lista: ${db.listarClinicas().length}.\nEscribe #ayuda para ver los comandos.`,
      );
    }
    if (connection === "close") {
      const codigo = lastDisconnect?.error?.output?.statusCode;
      estadoConexion = "desconectado";
      if (codigo === DisconnectReason.loggedOut) {
        log.error("Has cerrado la sesión del agente desde el móvil. Borro la sesión y pido vincular de nuevo.");
        fs.rmSync(carpetaSesion, { recursive: true, force: true });
      } else {
        log.warn({ codigo }, "Conexión cerrada, reconectando");
      }
      const espera = Math.min(3000 * 2 ** reintentos++, 60_000);
      setTimeout(() => conectar().catch((e) => log.error(e)), espera);
    }
  });

  sock.ev.on("messages.upsert", async ({ messages }) => {
    // "notify" = en directo; "append" = recibidos mientras el agente estaba desconectado.
    for (const m of messages) {
      const id = m.key?.id;
      if (!id || idsProcesados.has(id)) continue;
      idsProcesados.add(id);
      if (idsProcesados.size > 5000) idsProcesados.delete(idsProcesados.values().next().value);
      try {
        await alRecibir(m);
      } catch (e) {
        log.error({ err: e.message }, "Error leyendo un mensaje");
      }
    }
  });
}

// ---------------------------------------------------------------------------
// Página de estado (opcional, para vincular desde un servidor en la nube)
// ---------------------------------------------------------------------------
function servidorEstado() {
  if (!CFG.puerto) return;
  http
    .createServer(async (req, res) => {
      const url = new URL(req.url, "http://x");
      if (url.pathname === "/salud") {
        res.writeHead(200, { "content-type": "text/plain" }).end(estadoConexion);
        return;
      }
      if (!CFG.claveAcceso || url.searchParams.get("clave") !== CFG.claveAcceso) {
        res.writeHead(401, { "content-type": "text/plain; charset=utf-8" }).end("Acceso restringido.");
        return;
      }
      let cuerpo = `<p>Estado: <b>${estadoConexion}</b></p>`;
      if (codigoVinculacion) {
        cuerpo += `<p>Código para vincular: <b style="font-size:2em;letter-spacing:4px">${codigoVinculacion}</b></p>
          <p>WhatsApp &gt; Dispositivos vinculados &gt; Vincular un dispositivo &gt; Vincular con número de teléfono.</p>`;
      } else if (qrActual) {
        cuerpo += `<p>Escanea con WhatsApp &gt; Dispositivos vinculados &gt; Vincular un dispositivo:</p>
          <img src="${await QRCode.toDataURL(qrActual)}" width="300">`;
      }
      res
        .writeHead(200, { "content-type": "text/html; charset=utf-8" })
        .end(
          `<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="15"><title>Agente IA</title><body style="font-family:sans-serif;background:#0A0F1E;color:#fff;padding:2em">${cuerpo}</body>`,
        );
    })
    .listen(CFG.puerto, () => log.info(`Página de estado en el puerto ${CFG.puerto}`));
}

servidorEstado();
conectar().catch((e) => {
  log.error(e);
  process.exit(1);
});
