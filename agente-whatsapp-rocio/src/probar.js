// Prueba el agente en la terminal, sin WhatsApp: escribes como si fueras una clínica.
// Uso: npm run probar
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import readline from "node:readline/promises";
import { fileURLToPath } from "node:url";
import { abrirDB } from "./db.js";
import { crearAgente } from "./agente.js";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
if (fs.existsSync(path.join(RAIZ, ".env"))) process.loadEnvFile(path.join(RAIZ, ".env"));

const dir = fs.mkdtempSync(path.join(os.tmpdir(), "agente-prueba-"));
const db = abrirDB(dir);
const agente = crearAgente({
  modelo: process.env.MODELO || "claude-opus-5-5",
  esfuerzo: process.env.ESFUERZO || "low",
  disponibilidadDemos: process.env.DISPONIBILIDAD_DEMOS || "de lunes a viernes, de 10:00 a 13:00 y de 17:00 a 19:00",
  conocimientoPath: path.join(RAIZ, "conocimiento.md"),
});

const NUMERO = "34600000000";
db.anadirClinica(NUMERO, process.argv[2] || "Clínica de prueba");
const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
console.log("Escribe como si fueras una clínica. Ctrl+C para salir.\n");

for (;;) {
  const texto = await rl.question("Clínica > ");
  if (!texto.trim()) continue;
  db.guardarMensaje(NUMERO, "user", "clienta", texto);
  const r = await agente.responder({
    numero: NUMERO,
    nombreLista: db.getClinica(NUMERO).nombre,
    historial: db.historial(NUMERO, 40),
    ficha: db.getFicha(NUMERO),
    acciones: {
      guardarFicha: (d) => {
        db.guardarFicha(NUMERO, d);
        console.log(`   (ficha guardada: ${JSON.stringify(d)})`);
      },
      avisarRocio: async (a) => console.log(`   (AVISO A ROCÍO: ${JSON.stringify(a)})`),
    },
  });
  if (r.error) console.log(`   (error: ${r.error})`);
  if (r.texto) {
    db.guardarMensaje(NUMERO, "assistant", "agente", r.texto);
    console.log(`\nAgente > ${r.texto}\n`);
  } else console.log("   (el agente no contesta)\n");
}
