import hashlib
import hmac
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

_tmp = tempfile.mkdtemp()
os.environ.update(
    RUTA_BD=str(Path(_tmp) / "test.db"),
    WHATSAPP_APP_SECRET="secreto",
    WHATSAPP_VERIFY_TOKEN="verifica",
    ADMIN_NUMEROS="+34 600 000 000",
    ADMIN_TOKEN="clave-panel",
    ANTHROPIC_API_KEY="test",
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

import agent  # noqa: E402
import app as servidor  # noqa: E402

ADMIN = "34600000000"
CLIENTE = "34611111111"


class FakeMessages:
    def __init__(self):
        self.respuestas = []
        self.llamadas = []

    async def create(self, **kw):
        self.llamadas.append(kw)
        return self.respuestas.pop(0)


def texto(t):
    return SimpleNamespace(stop_reason="end_turn", stop_details=None, content=[SimpleNamespace(type="text", text=t)])


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    enviados = []

    async def fake_enviar(tel, txt):
        enviados.append((tel, txt))
        return True

    monkeypatch.setattr(servidor.whatsapp, "enviar_texto", fake_enviar)
    fake = FakeMessages()
    servidor._agente = agent.Agente(cliente=SimpleNamespace(beta=SimpleNamespace(messages=fake)))
    servidor.storage.set_bot_activo(True)
    servidor.storage.reanudar(CLIENTE)
    yield SimpleNamespace(enviados=enviados, claude=fake, http=TestClient(servidor.app))


_n = 0


def webhook(http, de, cuerpo_texto, campo="messages"):
    global _n
    _n += 1
    if campo == "messages":
        valor = {"contacts": [{"wa_id": de, "profile": {"name": "Lucía"}}],
                 "messages": [{"id": f"wamid.{_n}", "from": de, "type": "text", "text": {"body": cuerpo_texto}}]}
    else:
        valor = {"message_echoes": [{"id": f"eco.{_n}", "to": de, "type": "text", "text": {"body": cuerpo_texto}}]}
    cuerpo = json.dumps({"entry": [{"changes": [{"field": campo, "value": valor}]}]}).encode()
    firma = "sha256=" + hmac.new(b"secreto", cuerpo, hashlib.sha256).hexdigest()
    return http.post("/webhook", content=cuerpo, headers={"X-Hub-Signature-256": firma,
                                                         "Content-Type": "application/json"})


def test_verificacion_webhook(entorno):
    ok = entorno.http.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verifica",
                                              "hub.challenge": "123"})
    assert ok.status_code == 200 and ok.text == "123"
    mal = entorno.http.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x",
                                               "hub.challenge": "123"})
    assert mal.status_code == 403


def test_rechaza_firma_falsa(entorno):
    r = entorno.http.post("/webhook", content=b"{}", headers={"X-Hub-Signature-256": "sha256=00"})
    assert r.status_code == 401


def test_responde_al_cliente(entorno):
    entorno.claude.respuestas.append(texto("Hola Lucía, soy el asistente virtual."))
    assert webhook(entorno.http, CLIENTE, "Hola, info por favor").status_code == 200
    assert entorno.enviados == [(CLIENTE, "Hola Lucía, soy el asistente virtual.")]
    llamada = entorno.claude.llamadas[0]
    assert llamada["model"] == "claude-opus-5-5"
    assert llamada["messages"][-1]["role"] == "user"
    assert "Hola, info por favor" in llamada["messages"][-1]["content"]


def test_off_y_on_por_whatsapp(entorno):
    webhook(entorno.http, ADMIN, "#off")
    assert "DESACTIVADO" in entorno.enviados[-1][1]
    webhook(entorno.http, CLIENTE, "¿Estáis ahí?")
    assert entorno.claude.llamadas == []  # no se llama a Claude ni se responde
    assert all(tel != CLIENTE for tel, _ in entorno.enviados)
    webhook(entorno.http, ADMIN, "#on")
    assert "ACTIVADO" in entorno.enviados[-1][1]
    entorno.claude.respuestas.append(texto("Sí, dime."))
    webhook(entorno.http, CLIENTE, "Hola de nuevo")
    assert entorno.enviados[-1] == (CLIENTE, "Sí, dime.")
    # el historial incluye el mensaje que llegó con el bot apagado
    assert "¿Estáis ahí?" in entorno.claude.llamadas[0]["messages"][-1]["content"]


def test_cliente_no_puede_usar_comandos(entorno):
    entorno.claude.respuestas.append(texto("No entiendo, ¿en qué te ayudo?"))
    webhook(entorno.http, CLIENTE, "#off")
    assert servidor.storage.bot_activo() is True


def test_pausar_y_reanudar_un_chat(entorno):
    webhook(entorno.http, ADMIN, f"#pausar {CLIENTE}")
    webhook(entorno.http, CLIENTE, "Hola")
    assert entorno.claude.llamadas == []
    webhook(entorno.http, ADMIN, f"#reanudar {CLIENTE}")
    assert not servidor.storage.esta_pausado(CLIENTE)


def test_derivacion_a_humano_pausa_y_avisa(entorno):
    tool = SimpleNamespace(type="tool_use", id="tu_1", name="avisar_responsable",
                           input={"motivo": "quiere_contratar", "resumen": "Clínica en Triana, quiere demo.",
                                  "pausar_bot": True})
    entorno.claude.respuestas += [SimpleNamespace(stop_reason="tool_use", stop_details=None, content=[tool]),
                                  texto("Perfecto, Rocío te escribe personalmente hoy.")]
    webhook(entorno.http, CLIENTE, "Quiero contratarlo ya")
    assert (CLIENTE, "Perfecto, Rocío te escribe personalmente hoy.") in entorno.enviados
    aviso = [t for tel, t in entorno.enviados if tel == ADMIN][-1]
    assert "Clínica en Triana" in aviso and f"#reanudar {CLIENTE}" in aviso
    assert servidor.storage.esta_pausado(CLIENTE)


def test_respuesta_manual_pausa_el_bot(entorno):
    webhook(entorno.http, CLIENTE, "Te contesto yo, Lucía", campo="smb_message_echoes")
    assert servidor.storage.esta_pausado(CLIENTE)


def test_mensaje_duplicado_se_ignora(entorno):
    entorno.claude.respuestas.append(texto("Hola"))
    cuerpo = json.dumps({"entry": [{"changes": [{"field": "messages", "value": {"messages": [
        {"id": "wamid.dup", "from": CLIENTE, "type": "text", "text": {"body": "hola"}}]}}]}]}).encode()
    firma = "sha256=" + hmac.new(b"secreto", cuerpo, hashlib.sha256).hexdigest()
    for _ in range(2):
        entorno.http.post("/webhook", content=cuerpo, headers={"X-Hub-Signature-256": firma})
    assert len(entorno.claude.llamadas) == 1


def test_panel(entorno):
    assert entorno.http.get("/panel", params={"token": "mala"}).status_code == 403
    r = entorno.http.get("/panel", params={"token": "clave-panel"})
    assert r.status_code == 200 and "ACTIVO" in r.text
    entorno.http.post("/panel", data={"token": "clave-panel", "accion": "off"})
    assert servidor.storage.bot_activo() is False
    assert entorno.http.post("/panel", data={"token": "mala", "accion": "on"}).status_code == 403
    assert servidor.storage.bot_activo() is False


def test_limite_por_hora(entorno, monkeypatch):
    monkeypatch.setattr(servidor.config, "MAX_RESPUESTAS_HORA", 1)
    otro = "34622222222"
    entorno.claude.respuestas.append(texto("Hola"))
    webhook(entorno.http, otro, "uno")
    webhook(entorno.http, otro, "dos")
    assert len(entorno.claude.llamadas) == 1
    assert servidor.storage.esta_pausado(otro)
    assert any(tel == ADMIN and "superado" in t for tel, t in entorno.enviados)
