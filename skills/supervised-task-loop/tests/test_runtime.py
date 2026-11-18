"""Pruebas del runtime: los scripts tienen que ser correctos y demostrarse a si mismos.

Sin dependencias de terceros, sin red. Las pruebas que necesitan la CLI del tablero se
saltan si no esta, en vez de fallar: lo que se prueba aqui es el runtime, no la herramienta.
"""
from __future__ import annotations

import dataclasses
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
ASSETS = SKILL / "assets"

sys.path.insert(0, str(SCRIPTS))
import agent_config  # noqa: E402
import agent_handoff  # noqa: E402

SCRIPTS_ESPERADOS = [
    "agent_config.py",
    "agent_handoff.py",
    "agent_iteration.py",
    "agent_loop_report.py",
    "agent_preflight.py",
    "agent_run.py",
    "await_verdict.py",
]


class InventarioTests(unittest.TestCase):
    def test_los_scripts_existen(self):
        # El runtime son estos scripts y ni uno mas.
        self.assertEqual(sorted(p.name for p in SCRIPTS.glob("*.py")), SCRIPTS_ESPERADOS)

    def test_todo_script_compila(self):
        for nombre in SCRIPTS_ESPERADOS:
            with self.subTest(script=nombre):
                r = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(SCRIPTS / nombre)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_todo_script_ejecutable(self):
        for nombre in SCRIPTS_ESPERADOS:
            with self.subTest(script=nombre):
                self.assertTrue(os.access(SCRIPTS / nombre, os.X_OK), nombre)

    def test_no_quedan_scripts_de_shell(self):
        # El runtime es python: un `.sh` a la vuelta es un resto de otra version.
        self.assertEqual(sorted(p.name for p in SCRIPTS.glob("*.sh")), [])

    def test_los_assets_estan(self):
        for nombre in ("agent-loop.env", "agent-prompt.md", "handoff-template.md",
                       "pipeline.agent.kts"):
            with self.subTest(asset=nombre):
                self.assertTrue((ASSETS / nombre).is_file(), nombre)


class SelfTestTests(unittest.TestCase):
    """Los scripts que pueden demostrarse a si mismos, se demuestran."""

    def test_el_informe_se_certifica(self):
        r = subprocess.run(
            [sys.executable, "-I", str(SCRIPTS / "agent_loop_report.py"), "--self-test"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("certificado", r.stdout)

    def test_la_espera_se_certifica(self):
        r = subprocess.run(
            [sys.executable, "-I", str(SCRIPTS / "await_verdict.py"), "--self-test"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("certificado", r.stdout)

    def test_el_preflight_se_certifica(self):
        r = subprocess.run(
            [sys.executable, "-I", str(SCRIPTS / "agent_preflight.py"), "--self-test"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("certificado", r.stdout)


class AwaitVerdictTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.estado = Path(self.temp.name) / "v.verdict"

    def esperar(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-I", str(SCRIPTS / "await_verdict.py"),
             str(self.estado), "--timeout", "10", *extra],
            capture_output=True,
            text=True,
        )

    def test_un_veredicto_pass_da_cero(self):
        self.estado.write_text("PASS rc=0\n", encoding="utf-8")
        r = self.esperar()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_un_veredicto_fail_da_tres(self):
        self.estado.write_text("FAIL rc=1\n", encoding="utf-8")
        r = self.esperar()
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)

    def test_un_veredicto_ilegible_da_dos(self):
        self.estado.write_text("lo que sea\n", encoding="utf-8")
        r = self.esperar()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_sin_veredicto_da_dos(self):
        # Nunca un verde por timeout: un 2 es "no pude medir".
        r = self.esperar()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


class RenderTests(unittest.TestCase):
    """El prompt se renderiza con los marcadores sustituidos."""

    def runtime_de_prueba(self, base: Path) -> agent_config.Runtime:
        return agent_config.Runtime(
            script_dir=SCRIPTS,
            cwd=base,
            run_dir=base,
            workspace=base,
            home_repo=base / "home-repo",
            board_dir=base / "home-repo" / "backlog",
            runtime_dir=SCRIPTS,
            assets=ASSETS,
            pipeline_file=ASSETS / "pipeline.agent.kts",
            state=base / "estado",
            config_file=None,
            profile="cuenta-6",
            bare=False,
            max_tasks=3,
            task_timeout_min=90,
            slice="dev-jvm.slice",
            skills=("/a/SKILL.md",),
        )

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_el_prompt_se_renderiza_sin_marcadores(self):
        rt = self.runtime_de_prueba(self.base)
        rt.state.mkdir(parents=True, exist_ok=True)
        destino = agent_handoff.renderizar_prompt(rt, "doc-001", "backlog/docs/h.md", "  - nada")
        prompt = destino.read_text(encoding="utf-8")
        self.assertNotIn("{{", prompt, "quedaron marcadores sin sustituir")
        self.assertIn("OBJETIVO", prompt)
        self.assertIn(str(rt.workspace), prompt)
        self.assertIn(str(rt.home_repo), prompt)
        self.assertIn("/a/SKILL.md", prompt)

    def test_las_skills_sin_configuracion_se_nombran(self):
        rt = self.runtime_de_prueba(self.base)
        rt.state.mkdir(parents=True, exist_ok=True)
        texto = agent_handoff.texto_de_las_skills(dataclasses.replace(rt, skills=()))
        self.assertIn("backlog-agile-workflow", texto)


@unittest.skipUnless(shutil.which("backlog"), "la CLI del tablero no esta instalada")
class HandoffTests(unittest.TestCase):
    """El handoff se crea, se resuelve y el prompt sale de verdad."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / "workspace"
        (self.base / "backlog").mkdir(parents=True)
        (self.base / "backlog" / "config.yml").write_text(
            "statuses:\n  - name: Done\n", encoding="utf-8"
        )
        self.estado = Path(self.temp.name) / "state"

    def test_el_handoff_se_crea_y_el_prompt_se_renderiza(self):
        env = dict(os.environ)
        for clave in ("AGENT_BOARD", "AGENT_STATE", "AGENT_LOOP_ENV", "AGENT_ASSETS"):
            env.pop(clave, None)
        env["AGENT_STATE"] = str(self.estado)
        env["HOME"] = self.temp.name
        cuerpo = (
            "import sys\n"
            f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
            "import agent_config as c, agent_handoff as h\n"
            "rt = c.init_runtime()\n"
            "datos = h.preparar(rt)\n"
            "print(datos['doc_id'])\n"
        )
        r = subprocess.run(
            [sys.executable, "-I", "-c", cuerpo],
            cwd=self.base,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.strip().startswith("doc-"), r.stdout)
        prompt = (self.estado / "prompt.md").read_text(encoding="utf-8")
        self.assertNotIn("{{", prompt, "quedaron marcadores sin sustituir")


if __name__ == "__main__":
    unittest.main()
