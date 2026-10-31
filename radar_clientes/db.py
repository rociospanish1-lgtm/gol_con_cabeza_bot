"""Almacenamiento en SQLite (un único archivo, sin servidor)."""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from . import config

ESTADOS = ["nuevo", "contactado", "reunión", "propuesta", "cliente", "descartado"]
ESTADOS_CERRADOS = ("cliente", "descartado")

CANALES = ["Llamada", "WhatsApp", "Instagram", "LinkedIn", "Visita en persona", "Email"]

# Resultado de cada contacto. El "¿contestaron?" se deduce de aquí para que
# nunca se contradigan las dos cosas.
RESULTADOS = [
    "No contestan",
    "Buzón / mensaje dejado",
    "Contestó recepción: llamar más tarde",
    "Contestó recepción: me pasa con la responsable",
    "Hablé con la responsable: interesada",
    "Hablé con la responsable: pide información",
    "Hablé con la responsable: no interesada",
    "Reunión agendada",
]
SIN_RESPUESTA = {"No contestan", "Buzón / mensaje dejado"}
RESULTADOS_FINALES = {"Hablé con la responsable: no interesada", "Reunión agendada"}
DIAS_HASTA_SEGUIMIENTO = 2  # si no hay respuesta, propone volver a intentarlo en 2 días

CAMPOS_SEGUIMIENTO = ("estado", "notas", "contacto_nombre", "contacto_cargo",
                      "mejor_horario", "proximo_seguimiento")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS empresas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clave TEXT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    sector TEXT, ciudad TEXT, direccion TEXT,
    telefono TEXT, web TEXT, maps_url TEXT,
    valoracion REAL, num_resenas INTEGER,
    fuentes TEXT DEFAULT '[]',
    senales TEXT DEFAULT '{}',
    motivos TEXT DEFAULT '[]',
    gancho TEXT DEFAULT '',
    puntuacion INTEGER DEFAULT 0,
    nivel TEXT DEFAULT 'Frío',
    estado TEXT DEFAULT 'nuevo',
    notas TEXT DEFAULT '',
    demo INTEGER DEFAULT 0,
    creado TEXT, actualizado TEXT
);
CREATE INDEX IF NOT EXISTS idx_puntuacion ON empresas(puntuacion DESC);
CREATE TABLE IF NOT EXISTS contactos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    fecha TEXT NOT NULL,
    hora TEXT NOT NULL,
    canal TEXT NOT NULL,
    resultado TEXT NOT NULL,
    persona TEXT DEFAULT '',
    notas TEXT DEFAULT '',
    creado TEXT
);
CREATE INDEX IF NOT EXISTS idx_contactos_empresa ON contactos(empresa_id, fecha, hora);
"""

# Columnas añadidas después de la primera versión: se crean solas en bases antiguas.
COLUMNAS_NUEVAS = {
    "contacto_nombre": "TEXT DEFAULT ''",
    "contacto_cargo": "TEXT DEFAULT ''",
    "mejor_horario": "TEXT DEFAULT ''",
    "proximo_seguimiento": "TEXT DEFAULT ''",
}

CAMPOS_JSON = ("fuentes", "senales", "motivos")


@contextmanager
def conexion():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(ESQUEMA)
        existentes = {r["name"] for r in con.execute("PRAGMA table_info(empresas)")}
        for col, tipo in COLUMNAS_NUEVAS.items():
            if col not in existentes:
                con.execute(f"ALTER TABLE empresas ADD COLUMN {col} {tipo}")
        yield con
        con.commit()
    finally:
        con.close()


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fila(r: sqlite3.Row) -> dict:
    d = dict(r)
    for c in CAMPOS_JSON:
        d[c] = json.loads(d[c] or ("[]" if c != "senales" else "{}"))
    return d


def fecha_es(valor: str) -> str:
    """'2026-10-31' -> '31/10/2026' (formato de España). Vacío si no hay fecha."""
    try:
        return date.fromisoformat(valor).strftime("%d/%m/%Y") if valor else ""
    except ValueError:
        return valor


def _etiqueta(n: int) -> str:
    """1º contacto, 2º contacto, y a partir del tercero, Seguimiento 1, 2…"""
    return f"{n}º contacto" if n <= 2 else f"Seguimiento {n - 2}"


def _contacto(r: sqlite3.Row, n: int) -> dict:
    d = dict(r)
    d["numero"] = n
    d["etiqueta"] = _etiqueta(n)
    d["contestaron"] = d["resultado"] not in SIN_RESPUESTA
    return d


# ---------------------------------------------------------------------------
# Empresas
# ---------------------------------------------------------------------------
def guardar(empresa: dict) -> None:
    """Inserta o actualiza por 'clave'. Nunca pisa tu seguimiento comercial."""
    datos = {k: (json.dumps(v, ensure_ascii=False) if k in CAMPOS_JSON else v)
             for k, v in empresa.items() if k not in CAMPOS_SEGUIMIENTO}
    datos["actualizado"] = _ahora()
    columnas = list(datos)
    with conexion() as con:
        existe = con.execute("SELECT id FROM empresas WHERE clave=?", (datos["clave"],)).fetchone()
        if existe:
            sets = ", ".join(f"{c}=?" for c in columnas if c != "clave")
            con.execute(f"UPDATE empresas SET {sets} WHERE clave=?",
                        [datos[c] for c in columnas if c != "clave"] + [datos["clave"]])
        else:
            datos["creado"] = datos["actualizado"]
            columnas.append("creado")
            con.execute(f"INSERT INTO empresas ({', '.join(columnas)}) VALUES ({', '.join('?' * len(columnas))})",
                        [datos[c] for c in columnas])


def listar(nivel: str = "", ciudad: str = "", estado: str = "", minimo: int = 0,
           texto: str = "", pendientes: bool = False) -> list[dict]:
    sql = "SELECT * FROM empresas WHERE puntuacion >= ?"
    args: list = [minimo]
    if nivel:
        sql += " AND nivel = ?"; args.append(nivel)
    if ciudad:
        sql += " AND ciudad LIKE ?"; args.append(f"%{ciudad}%")
    if estado:
        sql += " AND estado = ?"; args.append(estado)
    if texto:
        sql += " AND (nombre LIKE ? OR direccion LIKE ? OR contacto_nombre LIKE ?)"; args += [f"%{texto}%"] * 3
    if pendientes:
        sql += (" AND proximo_seguimiento != '' AND proximo_seguimiento <= ?"
                f" AND estado NOT IN {ESTADOS_CERRADOS}")
        args.append(date.today().isoformat())
        sql += " ORDER BY proximo_seguimiento, puntuacion DESC"
    else:
        sql += " ORDER BY puntuacion DESC, num_resenas DESC"
    with conexion() as con:
        empresas = [_fila(r) for r in con.execute(sql, args)]
        historial: dict[int, list[dict]] = {}
        for r in con.execute("SELECT * FROM contactos ORDER BY empresa_id, fecha, hora, id"):
            lista = historial.setdefault(r["empresa_id"], [])
            lista.append(_contacto(r, len(lista) + 1))
    for e in empresas:
        e["contactos"] = historial.get(e["id"], [])
        e["seguimiento_vencido"] = bool(e["proximo_seguimiento"]) and \
            e["proximo_seguimiento"] <= date.today().isoformat() and e["estado"] not in ESTADOS_CERRADOS
    return empresas


def obtener(id_: int) -> dict | None:
    with conexion() as con:
        r = con.execute("SELECT * FROM empresas WHERE id=?", (id_,)).fetchone()
        return _fila(r) if r else None


def _validar_fecha(valor: str, obligatoria: bool = False) -> str:
    valor = (valor or "").strip()
    if not valor:
        if obligatoria:
            raise ValueError("falta la fecha")
        return ""
    return date.fromisoformat(valor).isoformat()  # lanza ValueError si no es AAAA-MM-DD


def actualizar_ficha(id_: int, *, estado: str, notas: str = "", contacto_nombre: str = "",
                     contacto_cargo: str = "", mejor_horario: str = "",
                     proximo_seguimiento: str = "") -> None:
    if estado not in ESTADOS:
        raise ValueError("estado no válido")
    with conexion() as con:
        con.execute(
            "UPDATE empresas SET estado=?, notas=?, contacto_nombre=?, contacto_cargo=?, "
            "mejor_horario=?, proximo_seguimiento=?, actualizado=? WHERE id=?",
            (estado, notas[:2000], contacto_nombre[:100], contacto_cargo[:100], mejor_horario[:100],
             _validar_fecha(proximo_seguimiento), _ahora(), id_))


def actualizar_seguimiento(id_: int, estado: str, notas: str) -> None:
    """Compatibilidad: cambia solo estado y notas."""
    e = obtener(id_)
    if not e:
        raise ValueError("empresa no encontrada")
    actualizar_ficha(id_, estado=estado, notas=notas, contacto_nombre=e["contacto_nombre"],
                     contacto_cargo=e["contacto_cargo"], mejor_horario=e["mejor_horario"],
                     proximo_seguimiento=e["proximo_seguimiento"])


# ---------------------------------------------------------------------------
# Historial de contactos
# ---------------------------------------------------------------------------
def anadir_contacto(empresa_id: int, *, fecha: str, hora: str, canal: str, resultado: str,
                    persona: str = "", notas: str = "", proximo_seguimiento: str = "") -> None:
    """Registra un intento de contacto y actualiza estado y próximo seguimiento."""
    fecha = _validar_fecha(fecha, obligatoria=True)
    hora = (hora or "").strip()
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", hora):
        raise ValueError("hora no válida (usa HH:MM)")
    if canal not in CANALES or resultado not in RESULTADOS:
        raise ValueError("canal o resultado no válido")
    proximo = _validar_fecha(proximo_seguimiento)
    if not proximo and resultado not in RESULTADOS_FINALES:
        proximo = (date.fromisoformat(fecha) + timedelta(days=DIAS_HASTA_SEGUIMIENTO)).isoformat()

    with conexion() as con:
        fila = con.execute("SELECT estado FROM empresas WHERE id=?", (empresa_id,)).fetchone()
        if not fila:
            raise ValueError("empresa no encontrada")
        estado = fila["estado"]
        if resultado == "Reunión agendada" and estado in ("nuevo", "contactado"):
            estado = "reunión"
        elif estado == "nuevo":
            estado = "contactado"
        con.execute("INSERT INTO contactos (empresa_id, fecha, hora, canal, resultado, persona, notas, creado) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (empresa_id, fecha, hora, canal, resultado, persona[:100], notas[:1000], _ahora()))
        con.execute("UPDATE empresas SET estado=?, proximo_seguimiento=?, actualizado=? WHERE id=?",
                    (estado, proximo, _ahora(), empresa_id))


def borrar_contacto(contacto_id: int) -> None:
    with conexion() as con:
        con.execute("DELETE FROM contactos WHERE id=?", (contacto_id,))


# ---------------------------------------------------------------------------
# Otros
# ---------------------------------------------------------------------------
def borrar_demo() -> int:
    with conexion() as con:
        return con.execute("DELETE FROM empresas WHERE demo=1").rowcount


def resumen() -> dict:
    hoy = date.today().isoformat()
    with conexion() as con:
        filas = con.execute("SELECT nivel, COUNT(*) n FROM empresas GROUP BY nivel").fetchall()
        hay_demo = con.execute("SELECT COUNT(*) FROM empresas WHERE demo=1").fetchone()[0]
        pendientes = con.execute(
            "SELECT COUNT(*) FROM empresas WHERE proximo_seguimiento != '' AND proximo_seguimiento <= ? "
            f"AND estado NOT IN {ESTADOS_CERRADOS}", (hoy,)).fetchone()[0]
    r = {f["nivel"]: f["n"] for f in filas}
    r["total"] = sum(r.values())
    r["demo"] = hay_demo
    r["pendientes"] = pendientes
    return r
