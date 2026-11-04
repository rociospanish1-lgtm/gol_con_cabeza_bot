// Comandos que escribes en tu chat contigo misma en WhatsApp.
import { formatearNumero, horaCorta, normalizarNumero } from "./utils.js";

// ---------------------------------------------------------------------------
// Comandos (los escribes en "Tú" / tu chat contigo misma en WhatsApp)
// ---------------------------------------------------------------------------
const AYUDA = `*Comandos del agente* (escríbelos en tu chat contigo misma)

#on — activa el agente
#off — desactiva el agente (no contesta a nadie)
#estado — cómo está y cuántas clínicas tiene
#añadir 600111222 Clínica Aura — añade una clínica a la lista (puedes poner varias, una por línea)
#quitar 600111222 — la quita de la lista
#lista — ver la lista de clínicas
#pausa 600111222 — el agente deja de contestar en ese chat (tú llevas la conversación)
#reanudar 600111222 — vuelve a contestar en ese chat (#reanudar todo para todos)
#ficha 600111222 — lo que el agente recuerda de ese contacto
#olvidar 600111222 — borra la memoria de ese contacto
#ayuda — esta lista`;

export function crearComandos(db, CFG) {
  return function ejecutarComando(texto) {
    const lineas = texto.trim().split("\n");
    const [cmdRaw, ...resto] = lineas[0].trim().split(/\s+/);
    const cmd = cmdRaw.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    const arg = resto.join(" ");
    const num = normalizarNumero(resto[0]);

    switch (cmd) {
      case "#on":
      case "#activar":
        db.setActivo(true);
        return "✅ Agente *activado*. Contesta a las clínicas de tu lista.";
      case "#off":
      case "#desactivar":
        db.setActivo(false);
        return "⏸️ Agente *desactivado*. No contestará a nadie hasta que escribas #on.";
      case "#estado": {
        const pausas = db.pausasActivas();
        return (
          `Agente: *${db.estaActivo(CFG.activoAlArrancar) ? "ACTIVADO" : "DESACTIVADO"}*\n` +
          `Clínicas en la lista: ${db.listarClinicas().length}\n` +
          `Chats en pausa: ${pausas.length}` +
          (pausas.length
            ? "\n" +
              pausas
                .map((p) => {
                  const cl = db.getClinica(p.numero);
                  const hasta = p.hasta > Date.now() + 365 * 86400_000 ? "hasta que la reanudes" : `hasta ${horaCorta(p.hasta)}`;
                  return `- ${cl?.nombre || formatearNumero(p.numero)} (${hasta})`;
                })
                .join("\n")
            : "")
        );
      }
      case "#anadir":
      case "#agregar": {
        const entradas = [lineas[0].trim().split(/\s+/).slice(1).join(" "), ...lineas.slice(1)]
          .map((l) => l.trim())
          .filter(Boolean);
        const ok = [];
        const mal = [];
        for (const e of entradas) {
          const m = e.match(/^([+\d\s().-]{9,})\s*(.*)$/);
          const n = m && normalizarNumero(m[1]);
          if (n) {
            db.anadirClinica(n, m[2] || null);
            ok.push(`${m[2] || "(sin nombre)"} — ${formatearNumero(n)}`);
          } else mal.push(e);
        }
        return (
          (ok.length ? `✅ Añadidas a la lista:\n${ok.join("\n")}` : "") +
          (mal.length ? `\n❌ No entiendo estos números:\n${mal.join("\n")}` : "") || "Escribe: #añadir 600111222 Clínica Aura"
        );
      }
      case "#quitar":
        if (!num) return "Escribe: #quitar 600111222";
        return db.quitarClinica(num) ? `🗑️ Quitada de la lista: ${formatearNumero(num)}` : "Ese número no estaba en la lista.";
      case "#lista": {
        const l = db.listarClinicas();
        if (!l.length) return "La lista está vacía. Añade clínicas con: #añadir 600111222 Clínica Aura";
        return `*Clínicas en la lista (${l.length})*\n` + l.map((c) => `- ${c.nombre || "(sin nombre)"} — ${formatearNumero(c.numero)}`).join("\n");
      }
      case "#pausa":
      case "#pausar":
        if (!num) return "Escribe: #pausa 600111222";
        db.pausar(num, 0, "manual");
        return `⏸️ El agente no contestará a ${formatearNumero(num)} hasta que escribas #reanudar ${num}`;
      case "#reanudar":
        if (arg.toLowerCase() === "todo") {
          db.reanudarTodo();
          return "▶️ El agente vuelve a contestar en todos los chats.";
        }
        if (!num) return "Escribe: #reanudar 600111222 (o #reanudar todo)";
        db.reanudar(num);
        return `▶️ El agente vuelve a contestar a ${formatearNumero(num)}.`;
      case "#ficha": {
        if (!num) return "Escribe: #ficha 600111222";
        const f = db.getFicha(num);
        const cl = db.getClinica(num);
        if (!f) return `No hay ficha de ${cl?.nombre || formatearNumero(num)} todavía.`;
        return (
          `*Ficha de ${cl?.nombre || formatearNumero(num)}*\n` +
          `Nombre: ${f.nombre || "?"}\nClínica: ${f.clinica || "?"}\nTipo: ${f.tipo || "?"}\nEstado: ${f.estado || "?"}\n` +
          `Notas: ${f.notas || "-"}\nActualizada: ${horaCorta(f.actualizada)}`
        );
      }
      case "#olvidar":
        if (!num) return "Escribe: #olvidar 600111222";
        db.olvidar(num);
        return `🧹 Memoria borrada de ${formatearNumero(num)}.`;
      case "#ayuda":
      case "#comandos":
      case "#agente":
        return AYUDA;
      default:
        return null;
    }
  }
}
