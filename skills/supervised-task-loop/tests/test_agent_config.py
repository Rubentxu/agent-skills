"""Pruebas de la configuracion: como se resuelve el fichero, los tres sitios y el tablero.

Sin dependencias de terceros, sin red y sin tocar nada fuera de un directorio temporal.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

# Las variables que la maquina puede tener puestas y que estarian en medio de las pruebas.
VARIABLES_A_LIMPIAR = (
    "AGENT_ASSETS",
    "AGENT_BOARD",
    "AGENT_LOOP_ENV",
    "AGENT_MAX_TASKS",
    "AGENT_PROFILE",
    "AGENT_SKILLS",
    "AGENT_STATE",
    "AGENT_WORKSPACE",
)


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "workspace"
        self.workspace.mkdir()

    def escribir(self, relative: str, contenido: str) -> Path:
        destino = self.workspace / relative
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")
        return destino

    def tablero(self, relative: str = "backlog") -> None:
        self.escribir(f"{relative}/config.yml", "statuses:\n  - name: Done\n")

    def correr(self, expresion: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
        """Evalua una expresion sobre el runtime, en el workspace temporal."""
        env = dict(os.environ)
        # El entorno se limpia: las pruebas no dependen de como este la maquina.
        for clave in VARIABLES_A_LIMPIAR:
            env.pop(clave, None)
        env["HOME"] = self.temp.name
        env.update(env_extra or {})
        cuerpo = (
            "import sys\n"
            f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
            "import agent_config as c\n"
            "try:\n"
            "    rt = c.init_runtime()\n"
            f"    print(eval({expresion!r}))\n"
            "except c.ErrorDeConfig as exc:\n"
            "    print('ERROR:', exc, file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
        )
        return subprocess.run(
            [sys.executable, "-I", "-c", cuerpo],
            cwd=self.workspace,
            env=env,
            capture_output=True,
            text=True,
        )

    # --- el tablero -------------------------------------------------------------------

    def test_tablero_en_la_raiz_del_workspace(self):
        self.tablero()
        r = self.correr('str(rt.board_dir)')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), str(self.workspace / "backlog"))

    def test_tablero_en_un_unico_subdirectorio(self):
        # El patron home repo: el tablero esta en un hijo, y el workspace es el padre.
        self.tablero("proyecto/backlog")
        r = self.correr('str(rt.board_dir)')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), str(self.workspace / "proyecto" / "backlog"))

    def test_sin_tablero_falla_y_dice_como_resolverlo(self):
        r = self.correr('str(rt.board_dir)')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("AGENT_BOARD", r.stderr)

    def test_varios_tableros_fallan_y_los_dicen(self):
        self.tablero("uno/backlog")
        self.tablero("dos/backlog")
        r = self.correr('str(rt.board_dir)')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("mas de un tablero", r.stderr)
        self.assertIn("uno", r.stderr)
        self.assertIn("dos", r.stderr)

    def test_el_home_repo_es_el_padre_del_tablero(self):
        self.tablero("proyecto/backlog")
        r = self.correr('str(rt.home_repo)')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), str(self.workspace / "proyecto"))

    # --- el workspace agéntico --------------------------------------------------------

    def test_el_workspace_agentico_por_defecto_es_el_directorio_de_ejecucion(self):
        self.tablero()
        r = self.correr('str(rt.workspace)')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), str(self.workspace))

    def test_el_workspace_agentico_puede_ser_el_padre_de_varios_repos(self):
        self.tablero("home-repo/backlog")
        padre = Path(self.temp.name) / "padre"
        padre.mkdir()
        for nombre in ("repo-a", "repo-b"):
            (padre / nombre / ".git").mkdir(parents=True)
        r = self.correr('str(rt.workspace)', {"AGENT_WORKSPACE": str(padre)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), str(padre))

    def test_un_workspace_agentico_relativo_se_resuelve_contra_el_directorio(self):
        self.tablero()
        (self.workspace / "padre").mkdir()
        r = self.correr('str(rt.workspace)', {"AGENT_WORKSPACE": "padre"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), str(self.workspace / "padre"))

    def test_los_repos_de_producto_no_incluyen_el_home_repo(self):
        self.tablero("home-repo/backlog")
        (self.workspace / "home-repo" / ".git").mkdir(parents=True)
        (self.workspace / "repo-a" / ".git").mkdir(parents=True)
        r = self.correr('[p.name for p in c.repos_de_producto(rt.workspace, rt.home_repo)]')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "['repo-a']")

    # --- el fichero de configuracion --------------------------------------------------

    def test_el_fichero_carga_los_valores(self):
        self.tablero()
        self.escribir("agent-loop.env", "AGENT_PROFILE=cuenta-9\nAGENT_MAX_TASKS=7\n")
        r = self.correr('f"{rt.profile}|{rt.max_tasks}"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "cuenta-9|7")

    def test_el_entorno_gana_al_fichero(self):
        self.tablero()
        self.escribir("agent-loop.env", "AGENT_PROFILE=cuenta-9\n")
        r = self.correr('rt.profile', {"AGENT_PROFILE": "cuenta-6"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "cuenta-6")

    def test_el_fichero_no_se_ejecuta(self):
        # Un fichero de configuracion no es un programa: sus lineas se leen, no se corren.
        self.tablero()
        marca = self.workspace / "NO-DEBISTE-CREAR-ESTO"
        self.escribir("agent-loop.env", f"AGENT_PROFILE=cuenta-6\ntouch {marca}\n")
        r = self.correr('rt.profile')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(marca.exists(), "el fichero de configuracion se ejecutó")

    def test_los_comentarios_y_las_lineas_vacias_se_ignoran(self):
        self.tablero()
        self.escribir("agent-loop.env", "# un comentario\n\nAGENT_PROFILE=cuenta-6\n")
        r = self.correr('rt.profile')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "cuenta-6")

    def test_las_comillas_se_quitan(self):
        self.tablero()
        self.escribir("agent-loop.env", 'AGENT_PROFILE="cuenta-9"\n')
        r = self.correr('rt.profile')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "cuenta-9")

    def test_el_fichero_se_busca_por_si_mismo(self):
        self.tablero()
        otro = self.escribir("otro.env", "AGENT_PROFILE=cuenta-7\n")
        r = self.correr('rt.profile', {"AGENT_LOOP_ENV": str(otro)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "cuenta-7")

    def test_las_skills_se_leen_del_fichero(self):
        self.tablero()
        self.escribir("agent-loop.env", "AGENT_SKILLS=/a/SKILL.md:/b/SKILL.md\n")
        r = self.correr('"|".join(rt.skills)')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "/a/SKILL.md|/b/SKILL.md")

    # --- los assets y el estado -------------------------------------------------------

    def test_los_assets_se_resuelven_desde_el_skill(self):
        self.tablero()
        r = self.correr('str(rt.assets)')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip().endswith("/assets"), r.stdout)
        self.assertTrue(Path(r.stdout.strip(), "agent-prompt.md").is_file())

    def test_el_estado_fuera_del_repo(self):
        self.tablero()
        r = self.correr('str(rt.state)')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(str(self.workspace), r.stdout.strip())

    # --- el directorio del run ---------------------------------------------------------

    def test_el_directorio_del_run_es_donde_vive_el_runtime(self):
        # Un proyecto real lleva sus scripts y su pipeline; ahi corre la pipeline.
        self.tablero()
        proyecto = Path(self.temp.name) / "proyecto"
        (proyecto / "scripts").mkdir(parents=True)
        (proyecto / "pipeline.agent.kts").write_text("// vacia\n", encoding="utf-8")
        (proyecto / "backlog").mkdir()
        (proyecto / "backlog" / "config.yml").write_text(
            "statuses:\n  - name: Done\n", encoding="utf-8"
        )
        for nombre in ("agent_config.py", "agent_handoff.py", "agent_iteration.py",
                       "agent_loop_report.py", "agent_preflight.py", "agent_run.py",
                       "await_verdict.py"):
            shutil.copy2(SCRIPTS / nombre, proyecto / "scripts" / nombre)
        # Una instalacion copia tambien los assets: el prompt es de la skill.
        shutil.copytree(SCRIPTS.parent / "assets", proyecto / "assets")

        env = dict(os.environ)
        for clave in VARIABLES_A_LIMPIAR:
            env.pop(clave, None)
        env["HOME"] = self.temp.name
        cuerpo = (
            "import sys\n"
            f"sys.path.insert(0, {str(proyecto / 'scripts')!r})\n"
            "import agent_config as c\n"
            "rt = c.init_runtime()\n"
            "print(rt.run_dir)\n"
        )
        r = subprocess.run(
            [sys.executable, "-I", "-c", cuerpo],
            cwd=proyecto,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), str(proyecto))


if __name__ == "__main__":
    unittest.main()
