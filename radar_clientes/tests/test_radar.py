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
