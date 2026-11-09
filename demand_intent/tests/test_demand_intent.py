import os
import tempfile
import unittest

from demand_intent import collectors, report
from demand_intent.__main__ import main
from demand_intent.scoring import Account, score

SIN_HERRAMIENTAS = """<html><body>
<h1>Clínica de Medicina Estética en Sevilla</h1>
<p>Ácido hialurónico, botox y depilación láser. Nuestros centros en Nervión y Triana.</p>
<p>Pide tu cita llamando al 954 000 000</p>
<a href="https://wa.me/34600000000">WhatsApp</a>
<a href="/trabaja-con-nosotros">Empleo</a>
</body></html>"""

EMPLEO = "<html><body><h2>Trabaja con nosotros</h2><p>Buscamos recepcionista</p></body></html>"

DIGITALIZADA = """<html><head><script src="https://code.tidio.co/abc.js"></script></head>
<body><h1>Centro de estética Sevilla</h1>
<iframe src="https://www.treatwell.es/widget/123"></iframe></body></html>"""


def fake_fetcher(pages):
    def _fetch(url):
        for key, html in pages.items():
            if url.rstrip("/").endswith(key):
                return html
        raise OSError("404")
    return _fetch


class TestWeb(unittest.TestCase):
    def test_clinica_sin_herramientas(self):
        w = collectors.scan_website("clinica.test", fetcher=fake_fetcher(
            {"clinica.test": SIN_HERRAMIENTAS, "/trabaja-con-nosotros": EMPLEO}))
        self.assertTrue(w.ok)
        self.assertEqual(w.pages_scanned, 2)
        self.assertEqual(w.booking_tools, [])
        self.assertEqual(w.chat_tools, [])
        self.assertTrue(w.has_whatsapp and w.manual_booking and w.hiring and w.multi_location)
        self.assertIn("sevilla", w.city_mentions)

    def test_clinica_digitalizada(self):
        w = collectors.scan_website("https://digital.test",
                                    fetcher=fake_fetcher({"digital.test": DIGITALIZADA}))
        self.assertEqual(w.booking_tools, ["Treatwell"])
        self.assertEqual(w.chat_tools, ["Tidio"])

    def test_web_caida(self):
        w = collectors.scan_website("https://caida.test", fetcher=fake_fetcher({}))
        self.assertFalse(w.ok)
        self.assertIn("no se pudo abrir", w.error)


class TestReviews(unittest.TestCase):
    def test_detecta_dolor(self):
        r = collectors.analyze_reviews([
            "Genial, pero no cogen el teléfono",
            "Me cambiaron la cita sin avisar",
            "Les escribí por WhatsApp",          # WhatsApp solo, no es queja
            "Todo perfecto",
        ])
        self.assertEqual(r.pain_reviews, 2)
        self.assertEqual(r.pain_by_type["telefono_no_atendido"], 1)
        self.assertEqual(r.pain_by_type["problemas_agenda"], 1)
        self.assertEqual(len(r.evidence), 2)


class TestScoring(unittest.TestCase):
    def test_caliente_vs_fria(self):
        web_hot = collectors.scan_website("clinica.test", fetcher=fake_fetcher(
            {"clinica.test": SIN_HERRAMIENTAS, "/trabaja-con-nosotros": EMPLEO}))
        hot = score(Account(nombre="Hot", direccion="Sevilla", num_resenas=400), web_hot,
                    collectors.analyze_reviews(["no contestan nunca", "tardan días en responder",
                                                "imposible contactar"]))
        web_cold = collectors.scan_website("https://digital.test",
                                           fetcher=fake_fetcher({"digital.test": DIGITALIZADA}))
        cold = score(Account(nombre="Cold", direccion="Madrid", num_resenas=10), web_cold,
                     collectors.analyze_reviews(["todo perfecto"]))
        self.assertEqual(hot.temperatura, "CALIENTE")
        self.assertLessEqual(hot.total, 100)
        self.assertEqual(hot.fit, 40)
        self.assertGreater(hot.total, cold.total)
        self.assertIn("teléfono", hot.mensaje_apertura)
        self.assertEqual(cold.temperatura, "FRÍA")


class TestCLI(unittest.TestCase):
    def test_analizar_offline_y_surge(self):
        csv_path = os.path.join(os.path.dirname(__file__), "..", "ejemplo_clinicas.csv")
        with tempfile.TemporaryDirectory() as out:
            self.assertEqual(main(["analizar", csv_path, "-o", out, "--offline"]), 0)
            for f in ("ranking.csv", "informe.html", "historico.json"):
                self.assertTrue(os.path.exists(os.path.join(out, f)))
            with open(os.path.join(out, "ranking.csv"), encoding="utf-8-sig") as fh:
                lines = fh.read().splitlines()
            self.assertIn("Nervión", lines[1])   # la de más dolor, primera
            self.assertIn("Beauty", lines[-1])  # fuera de Sevilla, la última


if __name__ == "__main__":
    unittest.main()
