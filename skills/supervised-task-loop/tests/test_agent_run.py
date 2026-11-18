"""Pruebas de la guarda de slice del lanzador.

El supervisor es un proceso Java de larga vida: si la maquina vigila por slices y el
lanzador corre fuera de la suya, el vigilante lo mata como un build sin sitio. La guarda
comprueba el propio cgroup ANTES de abrir nada.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from agent_run import esta_en_la_slice  # noqa: E402


class SliceTests(unittest.TestCase):
    def test_una_scope_dentro_de_la_slice_se_reconoce(self):
        # systemd-run --slice=dev-jvm.slice crea la unidad DENTRO de la slice.
        contenido = (
            "0::/init.scope\n"
            "0::/user.slice/user-1000.slice/user@1000.service/dev-jvm.slice/"
            "run-r123.service\n"
        )
        self.assertTrue(esta_en_la_slice(contenido, "dev-jvm.slice"))

    def test_una_scope_directa_en_la_slice_se_reconoce(self):
        contenido = "0::/user.slice/user-1000.slice/user@1000.service/dev-jvm.slice"
        self.assertTrue(esta_en_la_slice(contenido, "dev-jvm.slice"))

    def test_fuera_de_la_slice_no_se_deja_pasar(self):
        contenido = (
            "0::/user.slice/user-1000.slice/user@1000.service/app.slice/"
            "terminal.service\n"
        )
        self.assertFalse(esta_en_la_slice(contenido, "dev-jvm.slice"))

    def test_un_nombre_parecido_no_engana(self):
        # `dev-jvmx.slice` no es `dev-jvm.slice`: el tramo tiene que coincidir entero.
        contenido = "0::/user.slice/user-1000.slice/dev-jvmx.slice/run.service\n"
        self.assertFalse(esta_en_la_slice(contenido, "dev-jvm.slice"))

    def test_un_prefijo_de_nombre_no_engana(self):
        contenido = "0::/user.slice/dev-jvm.slice-hermana/run.service\n"
        self.assertFalse(esta_en_la_slice(contenido, "dev-jvm.slice"))

    def test_un_cgroup_vacio_o_ilegible_no_da_verde_por_defecto(self):
        self.assertFalse(esta_en_la_slice("", "dev-jvm.slice"))
        self.assertFalse(esta_en_la_slice("0::\n", "dev-jvm.slice"))


if __name__ == "__main__":
    unittest.main()
