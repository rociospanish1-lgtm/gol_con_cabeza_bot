import pytest

from radar_clientes import config, db
from radar_clientes.analisis import URLNoPermitida, _validar_url, analizar_resenas, auditar_html
from radar_clientes.fuentes.ofertas_empleo import coinciden
from radar_clientes.puntuacion import puntuar


@pytest.fixture(autouse=True)
def bd_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")


def test_detecta_quejas_de_telefono_y_citas():
    q = analizar_resenas(["Genial, pero NO COGEN EL TELÉFONO nunca",
                          "Me cancelaron mi cita sin avisar", "Todo perfecto"])
    assert len(q["telefono"]) == 1 and len(q["citas"]) == 1 and "mensajes" not in q


def test_detecta_whatsapp_lento():
    assert "mensajes" in analizar_resenas(["Tardan días en responder al whatsapp"])


def test_auditoria_web():
    a = auditar_html('<a href="https://wa.me/34600">x</a><form><input></form><p>Pide tu cita</p>')
    assert a.whatsapp and a.formulario and a.pide_cita_manual and not a.reservas
    b = auditar_html('<script src="https://app.koibox.cloud/w.js"></script><script src="//code.tidio.co/x.js"></script>')
    assert b.reservas == ["Koibox"] and b.chatbots == ["Tidio"]


def test_puntuacion_prioriza_oferta_y_quejas():
    caliente = puntuar(auditoria=auditar_html("<p>llámanos</p>"), quejas={"telefono": ["a", "b"]},
                       num_resenas=200, valoracion=4.0,
                       ofertas=[{"titulo": "Recepcionista"}], tiene_web=True)
    frio = puntuar(auditoria=auditar_html('<script src="tidio"></script><script src="booksy"></script>'),
                   quejas={}, num_resenas=5, valoracion=4.9, ofertas=[], tiene_web=True)
    assert caliente["nivel"] == "Caliente" and caliente["gancho"].startswith("He visto vuestra oferta de «Recepcionista»")
    assert frio["nivel"] == "Frío" and frio["puntuacion"] == 0


def test_coincidencia_nombres():
    assert coinciden("Clínica Estética Lumière Sevilla", "LUMIERE SEVILLA S.L.")
    assert not coinciden("Clínica Estética Lumière", "Clínica Dental Sonrisa")


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://localhost:5000", "file:///etc/passwd",
                                 "http://169.254.169.254/latest", "ftp://ejemplo.com"])
def test_bloquea_urls_internas(url):
    with pytest.raises(URLNoPermitida):
        _validar_url(url)


def test_guardar_conserva_seguimiento():
    base = {"clave": "x:1", "nombre": "A", "puntuacion": 50, "nivel": "Templado",
            "fuentes": ["Demo"], "senales": {}, "motivos": []}
    db.guardar(base)
    e = db.listar()[0]
    db.actualizar_seguimiento(e["id"], "contactado", "Llamar el lunes")
    db.guardar({**base, "puntuacion": 70, "nivel": "Caliente"})
    e = db.listar()[0]
    assert (e["estado"], e["notas"], e["puntuacion"]) == ("contactado", "Llamar el lunes", 70)


def test_panel_y_csrf():
    from radar_clientes.app import crear_app
    from radar_clientes.demo import cargar
    cargar()
    c = crear_app().test_client()
    r = c.get("/")
    assert r.status_code == 200 and "[DEMO] Clínica Estética Ejemplo Nervión" in r.text
    assert c.post("/borrar-demo").status_code == 400  # sin token
    with c.session_transaction() as s:
        token = s["csrf"]
    assert c.post("/borrar-demo", data={"csrf": token}).status_code == 302
    assert db.resumen()["total"] == 0


def test_csv_neutraliza_formulas():
    from radar_clientes.__main__ import filas_csv
    fila = next(filas_csv([{"nombre": "=HYPERLINK(\"x\")", "motivos": []}]))
    assert fila["nombre"].startswith("'=")


def _empresa(clave="x:1"):
    db.guardar({"clave": clave, "nombre": "Clínica X", "puntuacion": 50, "nivel": "Templado",
                "fuentes": [], "senales": {}, "motivos": []})
    return next(e for e in db.listar() if e["clave"] == clave)["id"]


def test_historial_numera_y_actualiza_estado():
    id_ = _empresa()
    db.anadir_contacto(id_, fecha="2026-11-02", hora="10:00", canal="Llamada", resultado="No contestan")
    e = db.listar()[0]
    assert e["estado"] == "contactado" and e["proximo_seguimiento"] == "2026-11-04"
    db.anadir_contacto(id_, fecha="2026-11-04", hora="17:30", canal="WhatsApp",
                       resultado="Hablé con la responsable: interesada", persona="Ana")
    db.anadir_contacto(id_, fecha="2026-11-06", hora="11:00", canal="Llamada", resultado="Reunión agendada")
    e = db.listar()[0]
    assert [c["etiqueta"] for c in e["contactos"]] == ["1º contacto", "2º contacto", "Seguimiento 1"]
    assert [c["contestaron"] for c in e["contactos"]] == [False, True, True]
    assert e["estado"] == "reunión" and e["proximo_seguimiento"] == ""


@pytest.mark.parametrize("cambio", [{"hora": "25:00"}, {"fecha": "31/12/2026"}, {"canal": "Fax"},
                                    {"resultado": "otro"}, {"fecha": ""}])
def test_contacto_rechaza_datos_invalidos(cambio):
    id_ = _empresa()
    datos = {"fecha": "2026-11-02", "hora": "10:00", "canal": "Llamada", "resultado": "No contestan", **cambio}
    with pytest.raises(ValueError):
        db.anadir_contacto(id_, **datos)


def test_pendientes_de_hoy():
    from datetime import date, timedelta
    a, b = _empresa("x:a"), _empresa("x:b")
    db.actualizar_ficha(a, estado="contactado", proximo_seguimiento=(date.today() - timedelta(days=1)).isoformat())
    db.actualizar_ficha(b, estado="contactado", proximo_seguimiento=(date.today() + timedelta(days=3)).isoformat())
    assert [e["id"] for e in db.listar(pendientes=True)] == [a]
    assert db.resumen()["pendientes"] == 1
    db.actualizar_ficha(a, estado="descartado", proximo_seguimiento=date.today().isoformat())
    assert db.listar(pendientes=True) == []


def test_reescanear_no_borra_ficha():
    id_ = _empresa()
    db.actualizar_ficha(id_, estado="contactado", contacto_nombre="Ana", mejor_horario="mañanas")
    _empresa()
    e = db.obtener(id_)
    assert (e["contacto_nombre"], e["mejor_horario"]) == ("Ana", "mañanas")


def test_migra_base_de_datos_antigua():
    import sqlite3
    con = sqlite3.connect(config.DB_PATH)
    con.execute("CREATE TABLE empresas (id INTEGER PRIMARY KEY AUTOINCREMENT, clave TEXT UNIQUE NOT NULL, "
                "nombre TEXT NOT NULL, sector TEXT, ciudad TEXT, direccion TEXT, telefono TEXT, web TEXT, "
                "maps_url TEXT, valoracion REAL, num_resenas INTEGER, fuentes TEXT DEFAULT '[]', "
                "senales TEXT DEFAULT '{}', motivos TEXT DEFAULT '[]', gancho TEXT DEFAULT '', "
                "puntuacion INTEGER DEFAULT 0, nivel TEXT DEFAULT 'Frío', estado TEXT DEFAULT 'nuevo', "
                "notas TEXT DEFAULT '', demo INTEGER DEFAULT 0, creado TEXT, actualizado TEXT)")
    con.execute("INSERT INTO empresas (clave, nombre) VALUES ('vieja', 'Antigua')")
    con.commit(); con.close()
    assert db.listar()[0]["contacto_nombre"] == ""


def test_panel_registra_contacto_y_exporta():
    from radar_clientes.app import crear_app
    id_ = _empresa()
    c = crear_app().test_client()
    c.get("/")
    with c.session_transaction() as s:
        token = s["csrf"]
    r = c.post(f"/empresa/{id_}/contacto", data={"csrf": token, "fecha": "2026-11-02", "hora": "09:30",
                                                  "canal": "Llamada", "resultado": "No contestan"})
    assert r.status_code == 302 and r.headers["Location"].endswith(f"#empresa-{id_}")
    assert c.post(f"/empresa/{id_}/contacto", data={"csrf": token, "fecha": "x", "hora": "09:30",
                                                     "canal": "Llamada", "resultado": "No contestan"}).status_code == 400
    html = c.get("/").text
    assert "1º contacto" in html and "Añadir contacto" in html and "2º contacto:" in html
    csv_txt = c.get("/exportar.csv").text
    assert "02/11/2026 09:30" in csv_txt and "1º contacto: 02/11/2026 09:30 Llamada - No contestan" in csv_txt
    assert "02/11/2026" in html
