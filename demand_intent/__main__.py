"""CLI de Demand Intent.

Uso:
  python -m demand_intent buscar "clínica estética Sevilla" -o cuentas.csv
  python -m demand_intent analizar cuentas.csv -o resultados
  python -m demand_intent clinica https://www.ejemplo.es
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from . import collectors, report
from .scoring import Account, account_from_row, score

INPUT_COLUMNS = ["nombre", "web", "telefono", "direccion", "categoria", "valoracion",
                 "num_resenas", "instagram", "notas", "resenas"]


def _read_accounts(path: str) -> list[Account]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        rows = list(csv.DictReader(fh, delimiter=delimiter))
    accounts = [account_from_row({(k or "").strip().lower(): v for k, v in r.items()})
                for r in rows]
    return [a for a in accounts if a.nombre]


def _analyze(account: Account, offline: bool):
    sin_web = account.web.strip().upper() == "NO"
    if offline or not account.web or sin_web:
        if sin_web:
            error = "sin web"
        elif not account.web:
            error = "web sin revisar"
        else:
            error = "modo offline"
        web = collectors.WebSignals(url="" if sin_web else account.web, error=error)
    else:
        web = collectors.scan_website(account.web)
    reviews = collectors.analyze_reviews(account.resenas)
    return score(account, web, reviews)


def _apply_history(results, history_path: str) -> None:
    """Guarda la puntuación de cada ejecución y marca las subidas (el 'surge')."""
    history = {}
    if os.path.exists(history_path):
        with open(history_path, encoding="utf-8") as fh:
            history = json.load(fh)
    now = datetime.now().isoformat(timespec="minutes")
    for r in results:
        key = r.account.nombre.lower()
        prev = history.get(key, [])
        if prev:
            delta = r.total - prev[-1]["total"]
            if delta >= 10:
                r.motivos.insert(0, f"SUBIDA DE INTENCIÓN: +{delta} puntos desde {prev[-1]['fecha']}")
        prev.append({"fecha": now, "total": r.total, "intent": r.intent})
        history[key] = prev[-12:]
    with open(history_path, "w", encoding="utf-8") as fh:
        json.dump(history, fh, ensure_ascii=False, indent=1)


def cmd_analizar(args) -> int:
    accounts = _read_accounts(args.entrada)
    if not accounts:
        print("El CSV no tiene filas con 'nombre'.", file=sys.stderr)
        return 1
    print(f"Analizando {len(accounts)} clínicas…")
    with ThreadPoolExecutor(max_workers=args.hilos) as pool:
        results = list(pool.map(lambda a: _analyze(a, args.offline), accounts))
    results.sort(key=lambda r: (r.total, r.intent), reverse=True)

    os.makedirs(args.salida, exist_ok=True)
    _apply_history(results, os.path.join(args.salida, "historico.json"))
    csv_path = os.path.join(args.salida, "ranking.csv")
    html_path = os.path.join(args.salida, "informe.html")
    report.write_csv(results, csv_path)
    report.write_html(results, html_path)

    print(f"\n{'#':>3}  {'TEMP':9} {'TOTAL':>5}  NOMBRE")
    for i, r in enumerate(results[:15], 1):
        print(f"{i:>3}  {r.temperatura:9} {r.total:>5}  {r.account.nombre}  ->  {r.angulo}")
    print(f"\nRanking: {csv_path}\nInforme: {html_path}")
    return 0


def cmd_buscar(args) -> int:
    rows = collectors.places_search(args.consulta, max_results=args.max)
    with open(args.salida, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=INPUT_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} clínicas guardadas en {args.salida}. "
          f"Ahora: python -m demand_intent analizar {args.salida}")
    return 0


def cmd_clinica(args) -> int:
    account = Account(nombre=args.nombre or args.url, web=args.url,
                      resenas=collectors.split_reviews(args.resenas or ""))
    r = _analyze(account, offline=False)
    print(f"\n{account.nombre}\n{r.temperatura} · {r.total}/100 (FIT {r.fit} · INTENT {r.intent})")
    if r.web.error:
        print(f"Aviso: {r.web.error}")
    print("\nSeñales:")
    for m in r.motivos:
        print(f"  - {m}")
    print(f"\nÁngulo: {r.angulo}\n\nPrimer mensaje:\n{r.mensaje_apertura}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="demand_intent",
                                description="Detecta clínicas con intención de compra de agentes IA.")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analizar", help="Puntúa un CSV de clínicas")
    a.add_argument("entrada")
    a.add_argument("-o", "--salida", default="resultados")
    a.add_argument("--hilos", type=int, default=6)
    a.add_argument("--offline", action="store_true", help="No visitar webs (solo CSV y reseñas)")
    a.set_defaults(func=cmd_analizar)

    b = sub.add_parser("buscar", help="Saca clínicas de Google Maps (necesita GOOGLE_PLACES_API_KEY)")
    b.add_argument("consulta")
    b.add_argument("-o", "--salida", default="cuentas.csv")
    b.add_argument("--max", type=int, default=60)
    b.set_defaults(func=cmd_buscar)

    c = sub.add_parser("clinica", help="Analiza una sola web al momento")
    c.add_argument("url")
    c.add_argument("--nombre")
    c.add_argument("--resenas", help="Reseñas pegadas, separadas por ||")
    c.set_defaults(func=cmd_clinica)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
