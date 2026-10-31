"""Uso:
    python -m radar_clientes escanear [--sector "clínica estética"] [--ciudad Sevilla] [--sin-osm]
    python -m radar_clientes panel [--puerto 5000]
    python -m radar_clientes demo          # carga datos ficticios para probar el panel
    python -m radar_clientes borrar-demo
    python -m radar_clientes exportar leads.csv [--minimo 35]
"""
import argparse
import csv
import sys

from . import config, db


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="radar_clientes", description="Radar de clientes potenciales")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("escanear", help="busca y puntúa empresas")
    e.add_argument("--sector", default=config.SECTOR_POR_DEFECTO)
    e.add_argument("--ciudad", default=config.CIUDAD_POR_DEFECTO)
    e.add_argument("--sin-osm", action="store_true", help="no usar OpenStreetMap")
    pn = sub.add_parser("panel", help="abre el panel web en tu ordenador")
    pn.add_argument("--puerto", type=int, default=5000)
    sub.add_parser("demo", help="carga 5 empresas ficticias para probar")
    sub.add_parser("borrar-demo", help="elimina los datos ficticios")
    ex = sub.add_parser("exportar", help="exporta a CSV (abre con Excel)")
    ex.add_argument("archivo")
    ex.add_argument("--minimo", type=int, default=0)
    a = p.parse_args(argv)

    if a.cmd == "escanear":
        from .escaner import escanear
        escanear(a.sector, a.ciudad, usar_osm=not a.sin_osm)
    elif a.cmd == "panel":
        from .app import crear_app
        print(f"Panel en http://127.0.0.1:{a.puerto}")
        crear_app().run(host="127.0.0.1", port=a.puerto)
    elif a.cmd == "demo":
        from .demo import cargar
        print(f"{cargar()} empresas ficticias cargadas. Abre el panel para verlas.")
    elif a.cmd == "borrar-demo":
        print(f"{db.borrar_demo()} empresas ficticias eliminadas.")
    elif a.cmd == "exportar":
        exportar_csv(a.archivo, db.listar(minimo=a.minimo))
    return 0


COLUMNAS_CSV = ["puntuacion", "nivel", "nombre", "telefono", "web", "direccion", "valoracion",
                "num_resenas", "motivos", "gancho", "estado", "contacto_nombre", "contacto_cargo",
                "mejor_horario", "num_contactos", "primer_contacto", "segundo_contacto",
                "ultimo_contacto", "ultimo_resultado", "proximo_seguimiento", "historial",
                "notas", "maps_url"]


def filas_csv(empresas):
    for e in empresas:
        fila = {c: e.get(c, "") for c in COLUMNAS_CSV}
        fila["motivos"] = " | ".join(m["texto"] for m in e["motivos"])
        fila["proximo_seguimiento"] = db.fecha_es(e.get("proximo_seguimiento", ""))
        contactos = e.get("contactos", [])
        cuando = lambda c: f"{db.fecha_es(c['fecha'])} {c['hora']}"  # noqa: E731
        fila["num_contactos"] = len(contactos)
        fila["primer_contacto"] = cuando(contactos[0]) if contactos else ""
        fila["segundo_contacto"] = cuando(contactos[1]) if len(contactos) > 1 else ""
        fila["ultimo_contacto"] = cuando(contactos[-1]) if contactos else ""
        fila["ultimo_resultado"] = contactos[-1]["resultado"] if contactos else ""
        fila["historial"] = " | ".join(
            f"{c['etiqueta']}: {cuando(c)} {c['canal']} - {c['resultado']}"
            f"{' (' + c['persona'] + ')' if c['persona'] else ''}" for c in contactos)
        # Evita inyección de fórmulas al abrir el CSV en Excel
        for c, v in fila.items():
            if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
                fila[c] = "'" + v
        yield fila


def exportar_csv(destino, empresas):
    with open(destino, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS_CSV, delimiter=";")
        w.writeheader()
        w.writerows(filas_csv(empresas))
    print(f"{len(empresas)} empresas exportadas a {destino}")


if __name__ == "__main__":
    sys.exit(main())
