import os
import shutil
import subprocess
import tempfile
import unittest

import numpy as np

from asmr_creator import Config, crear
from asmr_creator import audio as A
from asmr_creator import visuals as V
from asmr_creator.presets import PRESETS, parsear_capas

HAY_FFMPEG = shutil.which("ffmpeg") is not None


class TestAudio(unittest.TestCase):
    def test_todas_las_capas_generan_estereo_sin_saturar(self):
        for nombre in A.CAPAS:
            x = A.mezclar([(nombre, 1.0)], 4, bucle=True)
            self.assertEqual(x.shape, (4 * A.SR, 2), nombre)
            self.assertTrue(np.isfinite(x).all(), nombre)
            self.assertLessEqual(np.abs(x).max(), 0.86, nombre)
            self.assertGreater(np.abs(x).mean(), 1e-4, nombre)

    def test_semilla_reproducible(self):
        a = A.mezclar([("lluvia", 1.0)], 3, semilla=1)
        b = A.mezclar([("lluvia", 1.0)], 3, semilla=1)
        np.testing.assert_array_equal(a, b)

    def test_capa_desconocida(self):
        with self.assertRaises(ValueError):
            A.mezclar([("nada", 1.0)], 3)

    def test_parsear_capas(self):
        self.assertEqual(parsear_capas("lluvia:0.5, toques"), [("lluvia", 0.5), ("toques", 1.0)])


class TestVisual(unittest.TestCase):
    def test_estilos_hacen_bucle_perfecto(self):
        for nombre, cls in V.ESTILOS.items():
            e = cls(1080, 1920, 6, 30, "clinica")
            self.assertLess(np.abs(e.frame(0, 0.5) - e.frame(6, 0.5)).mean(), 1e-4, nombre)

    def test_paleta_hex(self):
        self.assertEqual(len(V.resolver_paleta("#000000,#ffffff,#ff0000")), 3)
        with self.assertRaises(ValueError):
            V.resolver_paleta("#000000,#ffffff")


@unittest.skipUnless(HAY_FFMPEG, "ffmpeg no instalado")
class TestRender(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _probe(self, ruta):
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height",
                              "-of", "csv=p=0", ruta], capture_output=True, text=True, check=True).stdout
        return out

    def test_video_vertical_con_texto(self):
        salida = os.path.join(self.tmp, "v.mp4")
        crear(Config(salida=salida, preset="clinica", duracion=3, texto="Hola: prueba 'comillas'",
                     marca="@test", progreso=lambda m: None))
        info = self._probe(salida)
        self.assertIn("video,1080,1920", info)
        self.assertIn("audio", info)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "v_portada.jpg")))

    def test_todos_los_presets(self):
        for p in PRESETS:
            salida = os.path.join(self.tmp, f"{p}.mp4")
            crear(Config(salida=salida, preset=p, duracion=3, formato="cuadrado", portada=False,
                         progreso=lambda m: None))
            self.assertIn("video,1080,1080", self._probe(salida), p)

    def test_solo_audio(self):
        salida = os.path.join(self.tmp, "a.wav")
        crear(Config(salida=salida, preset="mar", duracion=3, solo_audio=True, progreso=lambda m: None))
        self.assertIn("audio", self._probe(salida))


if __name__ == "__main__":
    unittest.main()
