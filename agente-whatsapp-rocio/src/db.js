// Memoria del agente: lista de clínicas, conversaciones, fichas y pausas (SQLite).
import Database from "better-sqlite3";
import fs from "node:fs";
import path from "node:path";

export function abrirDB(dataDir) {
  fs.mkdirSync(dataDir, { recursive: true });
  const db = new Database(path.join(dataDir, "agente.db"));
  db.pragma("journal_mode = WAL");
  db.exec(`
    CREATE TABLE IF NOT EXISTS config (clave TEXT PRIMARY KEY, valor TEXT);
    CREATE TABLE IF NOT EXISTS clinicas (
      numero TEXT PRIMARY KEY, nombre TEXT, creada INTEGER
    );
    CREATE TABLE IF NOT EXISTS mensajes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      numero TEXT NOT NULL, rol TEXT NOT NULL, autor TEXT NOT NULL,
      texto TEXT NOT NULL, ts INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_mensajes_numero ON mensajes(numero, id);
    CREATE TABLE IF NOT EXISTS fichas (
      numero TEXT PRIMARY KEY, nombre TEXT, clinica TEXT, tipo TEXT,
      estado TEXT, notas TEXT, actualizada INTEGER
    );
    CREATE TABLE IF NOT EXISTS pausas (
      numero TEXT PRIMARY KEY, hasta INTEGER NOT NULL, motivo TEXT
    );
  `);

  const q = {
    getConfig: db.prepare("SELECT valor FROM config WHERE clave = ?"),
    setConfig: db.prepare(
      "INSERT INTO config (clave, valor) VALUES (?, ?) ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
    ),
    addClinica: db.prepare(
      "INSERT INTO clinicas (numero, nombre, creada) VALUES (?, ?, ?) ON CONFLICT(numero) DO UPDATE SET nombre = excluded.nombre",
    ),
    delClinica: db.prepare("DELETE FROM clinicas WHERE numero = ?"),
    getClinica: db.prepare("SELECT * FROM clinicas WHERE numero = ?"),
    listClinicas: db.prepare("SELECT * FROM clinicas ORDER BY nombre COLLATE NOCASE"),
    addMensaje: db.prepare(
      "INSERT INTO mensajes (numero, rol, autor, texto, ts) VALUES (?, ?, ?, ?, ?)",
    ),
    ultimosMensajes: db.prepare(
      "SELECT * FROM (SELECT * FROM mensajes WHERE numero = ? ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
    ),
    ultimoDelAgente: db.prepare(
      "SELECT ts FROM mensajes WHERE numero = ? AND autor = 'agente' ORDER BY id DESC LIMIT 1",
    ),
    borrarMensajes: db.prepare("DELETE FROM mensajes WHERE numero = ?"),
    getFicha: db.prepare("SELECT * FROM fichas WHERE numero = ?"),
    upsertFicha: db.prepare(`
      INSERT INTO fichas (numero, nombre, clinica, tipo, estado, notas, actualizada)
      VALUES (@numero, @nombre, @clinica, @tipo, @estado, @notas, @actualizada)
      ON CONFLICT(numero) DO UPDATE SET
        nombre = COALESCE(excluded.nombre, fichas.nombre),
        clinica = COALESCE(excluded.clinica, fichas.clinica),
        tipo = COALESCE(excluded.tipo, fichas.tipo),
        estado = COALESCE(excluded.estado, fichas.estado),
        notas = COALESCE(excluded.notas, fichas.notas),
        actualizada = excluded.actualizada
    `),
    borrarFicha: db.prepare("DELETE FROM fichas WHERE numero = ?"),
    setPausa: db.prepare(
      "INSERT INTO pausas (numero, hasta, motivo) VALUES (?, ?, ?) ON CONFLICT(numero) DO UPDATE SET hasta = excluded.hasta, motivo = excluded.motivo",
    ),
    getPausa: db.prepare("SELECT * FROM pausas WHERE numero = ?"),
    delPausa: db.prepare("DELETE FROM pausas WHERE numero = ?"),
    delTodasPausas: db.prepare("DELETE FROM pausas"),
    listPausas: db.prepare("SELECT * FROM pausas WHERE hasta > ?"),
  };

  return {
    // Interruptor general
    estaActivo(porDefecto) {
      const fila = q.getConfig.get("activo");
      return fila ? fila.valor === "1" : porDefecto;
    },
    setActivo(on) {
      q.setConfig.run("activo", on ? "1" : "0");
    },

    // Lista de clínicas (solo a estos números contesta el agente)
    anadirClinica(numero, nombre) {
      q.addClinica.run(numero, nombre || null, Date.now());
    },
    quitarClinica(numero) {
      return q.delClinica.run(numero).changes > 0;
    },
    getClinica(numero) {
      return q.getClinica.get(numero);
    },
    listarClinicas() {
      return q.listClinicas.all();
    },

    // Conversaciones
    guardarMensaje(numero, rol, autor, texto, ts = Date.now()) {
      q.addMensaje.run(numero, rol, autor, texto, ts);
    },
    historial(numero, max) {
      return q.ultimosMensajes.all(numero, max);
    },
    ultimaRespuestaAgente(numero) {
      return q.ultimoDelAgente.get(numero)?.ts ?? 0;
    },
    olvidar(numero) {
      q.borrarMensajes.run(numero);
      q.borrarFicha.run(numero);
    },

    // Ficha de cada contacto (memoria resumida)
    getFicha(numero) {
      return q.getFicha.get(numero);
    },
    guardarFicha(numero, datos) {
      q.upsertFicha.run({
        numero,
        nombre: datos.nombre ?? null,
        clinica: datos.clinica ?? null,
        tipo: datos.tipo ?? null,
        estado: datos.estado ?? null,
        notas: datos.notas ?? null,
        actualizada: Date.now(),
      });
    },

    // Pausas por chat (cuando Rocío lleva la conversación)
    pausar(numero, horas, motivo) {
      const hasta = horas > 0 ? Date.now() + horas * 3600_000 : 8_640_000_000_000_000;
      q.setPausa.run(numero, hasta, motivo || null);
    },
    reanudar(numero) {
      return q.delPausa.run(numero).changes > 0;
    },
    reanudarTodo() {
      q.delTodasPausas.run();
    },
    pausaActiva(numero) {
      const p = q.getPausa.get(numero);
      if (!p) return null;
      if (p.hasta <= Date.now()) {
        q.delPausa.run(numero);
        return null;
      }
      return p;
    },
    pausasActivas() {
      return q.listPausas.all(Date.now());
    },
  };
}
