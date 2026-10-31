"""Almacenamiento en SQLite (un único archivo, sin servidor)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from . import config

ESTADOS = ["nuevo", "contactado", "reunión", "propuesta", "cliente", "descartado"]

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
"""

CAMPOS_JSON = ("fuentes", "senales", "motivos")


@contextmanager
def conexion():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(ESQUEMA)
        yield con
        con.commit()
    finally:
        con.close()


def _fila(r: sqlite3.Row) -> dict:
    d = dict(r)
    for c in CAMPOS_JSON:
        d[c] = json.loads(d[c] or ("[]" if c != "senales" else "{}"))
    return d


def guardar(empresa: dict) -> None:
    """Inserta o actualiza por 'clave'. Conserva estado y notas existentes."""
    ahora = datetime.now().isoformat(timespec="seconds")
    datos = {k: (json.dumps(v, ensure_ascii=False) if k in CAMPOS_JSON else v)
             for k, v in empresa.items()}
    datos["actualizado"] = ahora
    columnas = [c for c in datos if c not in ("estado", "notas")]
    with conexion() as con:
        existe = con.execute("SELECT id FROM empresas WHERE clave=?", (datos["clave"],)).fetchone()
        if existe:
            sets = ", ".join(f"{c}=?" for c in columnas if c != "clave")
            con.execute(f"UPDATE empresas SET {sets} WHERE clave=?",
                        [datos[c] for c in columnas if c != "clave"] + [datos["clave"]])
        else:
            datos["creado"] = ahora
            columnas.append("creado")
            con.execute(f"INSERT INTO empresas ({', '.join(columnas)}) VALUES ({', '.join('?' * len(columnas))})",
                        [datos[c] for c in columnas])


def listar(nivel: str = "", ciudad: str = "", estado: str = "", minimo: int = 0,
           texto: str = "") -> list[dict]:
    sql = "SELECT * FROM empresas WHERE puntuacion >= ?"
    args: list = [minimo]
    if nivel:
        sql += " AND nivel = ?"; args.append(nivel)
    if ciudad:
        sql += " AND ciudad LIKE ?"; args.append(f"%{ciudad}%")
    if estado:
        sql += " AND estado = ?"; args.append(estado)
    if texto:
        sql += " AND (nombre LIKE ? OR direccion LIKE ?)"; args += [f"%{texto}%"] * 2
    sql += " ORDER BY puntuacion DESC, num_resenas DESC"
    with conexion() as con:
        return [_fila(r) for r in con.execute(sql, args)]


def obtener(id_: int) -> dict | None:
    with conexion() as con:
        r = con.execute("SELECT * FROM empresas WHERE id=?", (id_,)).fetchone()
        return _fila(r) if r else None


def actualizar_seguimiento(id_: int, estado: str, notas: str) -> None:
    if estado not in ESTADOS:
        raise ValueError("estado no válido")
    with conexion() as con:
        con.execute("UPDATE empresas SET estado=?, notas=?, actualizado=? WHERE id=?",
                    (estado, notas[:2000], datetime.now().isoformat(timespec="seconds"), id_))


def borrar_demo() -> int:
    with conexion() as con:
        return con.execute("DELETE FROM empresas WHERE demo=1").rowcount


def resumen() -> dict:
    with conexion() as con:
        filas = con.execute("SELECT nivel, COUNT(*) n FROM empresas GROUP BY nivel").fetchall()
        hay_demo = con.execute("SELECT COUNT(*) FROM empresas WHERE demo=1").fetchone()[0]
    r = {f["nivel"]: f["n"] for f in filas}
    r["total"] = sum(r.values())
    r["demo"] = hay_demo
    return r
