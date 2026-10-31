"""Panel web local: lista de leads, filtros, seguimiento y exportación."""
from __future__ import annotations

import csv
import io
import secrets
import threading
from datetime import datetime

from flask import Flask, Response, abort, jsonify, redirect, render_template, request, session, url_for

from . import config, db

_escaneo = {"activo": False, "log": []}
_cerrojo = threading.Lock()


def crear_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    app.add_template_filter(db.fecha_es, "fecha_es")

    @app.before_request
    def proteger_formularios():
        session.setdefault("csrf", secrets.token_hex(16))
        if request.method == "POST":
            enviado = request.form.get("csrf") or request.headers.get("X-CSRF", "")
            if not secrets.compare_digest(enviado, session["csrf"]):
                abort(400, "Token CSRF no válido")

    @app.get("/")
    def inicio():
        f = {k: request.args.get(k, "") for k in ("nivel", "estado", "texto", "ciudad")}
        minimo = request.args.get("minimo", "0")
        pendientes = request.args.get("pendientes") == "1"
        empresas = db.listar(minimo=int(minimo) if minimo.isdigit() else 0, pendientes=pendientes, **f)
        ahora = datetime.now()
        return render_template("panel.html", empresas=empresas, filtros=f, minimo=minimo,
                               pendientes=pendientes, hoy=ahora.date().isoformat(),
                               hora=ahora.strftime("%H:%M"), canales=db.CANALES,
                               resultados=db.RESULTADOS,
                               estados=db.ESTADOS, resumen=db.resumen(), csrf=session["csrf"],
                               claves={"google": bool(config.GOOGLE_PLACES_API_KEY),
                                       "adzuna": bool(config.ADZUNA_APP_ID)},
                               sector=config.SECTOR_POR_DEFECTO, ciudad=config.CIUDAD_POR_DEFECTO)

    @app.post("/empresa/<int:id_>")
    def seguimiento(id_: int):
        if not db.obtener(id_):
            abort(404)
        campos = ("estado", "notas", "contacto_nombre", "contacto_cargo", "mejor_horario",
                  "proximo_seguimiento")
        try:
            db.actualizar_ficha(id_, **{c: request.form.get(c, "") for c in campos})
        except ValueError as e:
            abort(400, str(e))
        return _volver(id_)

    @app.post("/empresa/<int:id_>/contacto")
    def nuevo_contacto(id_: int):
        campos = ("fecha", "hora", "canal", "resultado", "persona", "notas", "proximo_seguimiento")
        try:
            db.anadir_contacto(id_, **{c: request.form.get(c, "") for c in campos})
        except ValueError as e:
            abort(400, str(e))
        return _volver(id_)

    @app.post("/contacto/<int:contacto_id>/borrar")
    def borrar_contacto(contacto_id: int):
        db.borrar_contacto(contacto_id)
        return _volver(request.form.get("empresa", type=int))

    def _volver(id_: int | None):
        """Vuelve al panel con los mismos filtros y a la altura de la empresa."""
        destino = request.referrer or url_for("inicio")
        if not destino.startswith(request.host_url):
            destino = url_for("inicio")
        return redirect(destino.split("#")[0] + (f"#empresa-{id_}" if id_ else ""))

    @app.post("/escanear")
    def lanzar_escaneo():
        sector = request.form.get("sector", config.SECTOR_POR_DEFECTO).strip()[:60]
        ciudad = request.form.get("ciudad", config.CIUDAD_POR_DEFECTO).strip()[:60]
        with _cerrojo:
            if _escaneo["activo"]:
                return jsonify(ok=False, mensaje="Ya hay un escaneo en marcha"), 409
            _escaneo.update(activo=True, log=[])

        def trabajo():
            from .escaner import escanear
            try:
                escanear(sector, ciudad, progreso=_escaneo["log"].append)
            except Exception as e:  # noqa: BLE001 — se muestra al usuario en el panel
                _escaneo["log"].append(f"Error: {e}")
            finally:
                _escaneo["activo"] = False

        threading.Thread(target=trabajo, daemon=True).start()
        return jsonify(ok=True)

    @app.get("/escaneo")
    def estado_escaneo():
        return jsonify(activo=_escaneo["activo"], log=_escaneo["log"][-30:])

    @app.post("/borrar-demo")
    def borrar_demo():
        db.borrar_demo()
        return redirect(url_for("inicio"))

    @app.get("/exportar.csv")
    def exportar():
        from .__main__ import COLUMNAS_CSV, filas_csv
        buf = io.StringIO()
        buf.write("﻿")
        w = csv.DictWriter(buf, fieldnames=COLUMNAS_CSV, delimiter=";")
        w.writeheader()
        w.writerows(filas_csv(db.listar()))
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=leads_radar.csv"})

    return app
