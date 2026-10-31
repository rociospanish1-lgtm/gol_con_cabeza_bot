"""Persistencia en SQLite: estado on/off, chats pausados, historial y deduplicado de mensajes."""
import sqlite3
import threading
import time
from pathlib import Path


class Storage:
    def __init__(self, ruta: Path, bot_activo_inicial: bool = True):
        ruta = Path(ruta)
        if str(ruta) != ":memory:":
            ruta.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(ruta), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pausados (telefono TEXT PRIMARY KEY, hasta REAL);
            CREATE TABLE IF NOT EXISTS mensajes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telefono TEXT NOT NULL, rol TEXT NOT NULL, texto TEXT NOT NULL, ts REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_mensajes_tel ON mensajes(telefono, id);
            CREATE TABLE IF NOT EXISTS procesados (wamid TEXT PRIMARY KEY, ts REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS contactos (telefono TEXT PRIMARY KEY, nombre TEXT, ultimo REAL);
            """
        )
        self._db.execute(
            "INSERT OR IGNORE INTO ajustes VALUES ('bot_activo', ?)", ("1" if bot_activo_inicial else "0",)
        )
        self._db.commit()

    # --- on / off global ---
    def bot_activo(self) -> bool:
        with self._lock:
            fila = self._db.execute("SELECT valor FROM ajustes WHERE clave='bot_activo'").fetchone()
        return fila is not None and fila[0] == "1"

    def set_bot_activo(self, activo: bool) -> None:
        with self._lock:
            self._db.execute("UPDATE ajustes SET valor=? WHERE clave='bot_activo'", ("1" if activo else "0",))
            self._db.commit()

    # --- pausa por chat ---
    def pausar(self, telefono: str, horas: float | None = None) -> None:
        hasta = time.time() + horas * 3600 if horas else None
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO pausados VALUES (?, ?)", (telefono, hasta))
            self._db.commit()

    def reanudar(self, telefono: str) -> bool:
        with self._lock:
            cur = self._db.execute("DELETE FROM pausados WHERE telefono=?", (telefono,))
            self._db.commit()
        return cur.rowcount > 0

    def esta_pausado(self, telefono: str) -> bool:
        with self._lock:
            fila = self._db.execute("SELECT hasta FROM pausados WHERE telefono=?", (telefono,)).fetchone()
        if fila is None:
            return False
        if fila[0] is not None and fila[0] < time.time():
            self.reanudar(telefono)
            return False
        return True

    def pausados(self) -> list[tuple[str, float | None]]:
        with self._lock:
            filas = self._db.execute("SELECT telefono, hasta FROM pausados ORDER BY telefono").fetchall()
        ahora = time.time()
        return [(t, h) for t, h in filas if h is None or h >= ahora]

    # --- historial ---
    def guardar_mensaje(self, telefono: str, rol: str, texto: str) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO mensajes (telefono, rol, texto, ts) VALUES (?, ?, ?, ?)",
                (telefono, rol, texto, time.time()),
            )
            self._db.commit()

    def historial(self, telefono: str, limite: int) -> list[dict]:
        with self._lock:
            filas = self._db.execute(
                "SELECT rol, texto FROM mensajes WHERE telefono=? ORDER BY id DESC LIMIT ?", (telefono, limite)
            ).fetchall()
        return [{"rol": r, "texto": t} for r, t in reversed(filas)]

    def respuestas_recientes(self, telefono: str, segundos: float = 3600) -> int:
        with self._lock:
            fila = self._db.execute(
                "SELECT COUNT(*) FROM mensajes WHERE telefono=? AND rol='assistant' AND ts>?",
                (telefono, time.time() - segundos),
            ).fetchone()
        return fila[0]

    # --- deduplicado (Meta reenvía webhooks si tardamos en contestar) ---
    def marcar_procesado(self, wamid: str) -> bool:
        """Devuelve True si es nuevo; False si ya lo habíamos visto."""
        with self._lock:
            try:
                self._db.execute("INSERT INTO procesados VALUES (?, ?)", (wamid, time.time()))
                self._db.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    # --- contactos ---
    def guardar_contacto(self, telefono: str, nombre: str | None) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO contactos VALUES (?, ?, ?) ON CONFLICT(telefono) DO UPDATE SET "
                "nombre=COALESCE(excluded.nombre, contactos.nombre), ultimo=excluded.ultimo",
                (telefono, nombre, time.time()),
            )
            self._db.commit()

    def nombre_contacto(self, telefono: str) -> str | None:
        with self._lock:
            fila = self._db.execute("SELECT nombre FROM contactos WHERE telefono=?", (telefono,)).fetchone()
        return fila[0] if fila else None
