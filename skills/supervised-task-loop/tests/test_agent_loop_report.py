"""Pruebas del informe: lo que mide y como decide el veredicto.

Sin dependencias de terceros, sin red. El informe se certifica a si mismo (`--self-test`);
aqui se comprueban las piezas que el self-test no puede cubrir solo: como se distingue un
sondeo de una espera legitima, y como se decide el veredicto.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
REPORTE = SCRIPTS / "agent_loop_report.py"

sys.path.insert(0, str(SCRIPTS))
import agent_loop_report as informe  # noqa: E402


class SondeoTests(unittest.TestCase):
    """Un sondeo es un bucle que espera y repite. Una espera suelta no lo es.

    Esta distincion es la que separo la linea base de 2.032 sondeos de los 131 reales: sin
    ella, cualquier `sleep` se cuenta y la guarda de regresion no guarda nada.
    """

    def test_un_bucle_con_sleep_es_sondeo(self):
        self.assertTrue(informe.es_sondeo("until [ -f x ]; do sleep 20; done"))
        self.assertTrue(informe.es_sondeo("while ! gh pr view $n >/dev/null; do sleep 5; done"))

    def test_un_bucle_con_tail_es_sondeo(self):
        self.assertTrue(informe.es_sondeo("until grep -q listo x.log; do tail -f x.log; done"))

    def test_una_espera_suelta_no_es_sondeo(self):
        # Esperar a que un trabajo termine, una vez, no es sondear: es esperar.
        self.assertFalse(informe.es_sondeo("sleep 30"))
        self.assertFalse(informe.es_sondeo("sleep 5 && ./gradlew check"))

    def test_un_bucle_sin_espera_no_es_sondeo(self):
        self.assertFalse(informe.es_sondeo("for f in *.kt; do echo $f; done"))

    def test_un_for_sobre_una_lista_no_es_sondeo(self):
        self.assertFalse(informe.es_sondeo("for repo in a b c; do git -C $repo status; done"))


class ReposDelWorkspaceTests(unittest.TestCase):
    """Los repos del workspace. Un worktree tiene `.git` como fichero, no como carpeta."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_se_ve_el_repositorio_y_el_worktree(self):
        (self.base / "repo").mkdir()
        (self.base / "repo" / ".git").mkdir()
        (self.base / "worktree").mkdir()
        (self.base / "worktree" / ".git").write_text("gitdir: ../repo/.git/worktrees/x\n")
        (self.base / "plano").mkdir()

        repos = informe.repos_del_workspace(str(self.base))
        self.assertEqual(sorted(Path(r).name for r in repos), ["repo", "worktree"])


class VeredictoTests(unittest.TestCase):
    """El veredicto usa el vocabulario cerrado: PASS, FAIL, BLOCKED o NOT_RUN."""

    def decidir(self, session, tablero, handoff, arrancada=True):
        return informe.decidir_veredicto(session, tablero, handoff, arrancada)

    def test_el_vocabulario_es_cerrado(self):
        self.assertEqual(
            sorted(
                {informe.PASS, informe.FAIL, informe.BLOCKED, informe.NOT_RUN}
            ),
            ["BLOCKED", "FAIL", "NOT_RUN", "PASS"],
        )

    def test_una_sesion_que_no_arranca_no_corrio(self):
        veredicto, _ = self.decidir({}, {}, {}, arrancada=False)
        self.assertEqual(veredicto, informe.NOT_RUN)

    def test_una_tarea_cerrada_con_handoff_no_es_entrega(self):
        veredicto, _ = self.decidir(
            {"is_error": False, "result": "listo"},
            {"task_closed": "PKH-060"},
            {"updated": True},
        )
        self.assertEqual(veredicto, informe.FAIL)

    def test_una_tarea_cerrada_sin_handoff_falla(self):
        # La guarda: una entrega que la siguiente sesion no puede continuar, falla aunque el
        # codigo de la sesion sea perfecto.
        veredicto, razon = self.decidir(
            {"is_error": False, "result": "listo"},
            {"task_closed": "PKH-060"},
            {"updated": False},
        )
        self.assertEqual(veredicto, informe.FAIL)
        self.assertIn("handoff", razon)

    def test_una_sesion_que_no_cierra_nada_falla(self):
        veredicto, _ = self.decidir(
            {"is_error": False, "result": "he mirado el tablero"},
            {"task_closed": None},
            {"updated": True},
        )
        self.assertEqual(veredicto, informe.FAIL)

    def test_un_agente_que_declara_bloqueo_es_blocked(self):
        veredicto, _ = self.decidir(
            {"is_error": False, "result": "no puedo seguir: falta el credencial"},
            {"task_closed": None},
            {"updated": False},
        )
        self.assertEqual(veredicto, informe.BLOCKED)

    def test_un_error_de_sesion_falla(self):
        veredicto, _ = self.decidir(
            {"is_error": True, "result": "error"},
            {"task_closed": None},
            {"updated": False},
        )
        self.assertEqual(veredicto, informe.FAIL)


    def test_delivery_requires_exact_observed_evidence(self):
        before = {"tasks": [{"id": "HSP-228", "status": "To Do", "acceptanceCriteriaCount": 1, "acceptanceCriteriaCompleted": 0}]}
        after = {"tasks": [{"id": "HSP-228", "status": "Done", "acceptanceCriteriaCount": 1, "acceptanceCriteriaCompleted": 1}]}
        board = informe.diff_del_tabulario(informe.estados_del_tabulario(before), informe.estados_del_tabulario(after), {"Done"})
        session = {"session_id": "s", "is_error": False}
        handoff = {"updated": True}
        good = {"status": "PASS", "evidenceRefs": ["ci:checked-at-revision"]}
        observation = {"schemaVersion": 1, "kind": "delivery-observation",
            "taskId": "HSP-228", "sessionId": "s",
            "beforeDigest": informe.snapshot_digest(before), "afterDigest": informe.snapshot_digest(after),
            "scope": "product-capability", "targetRef": "repo@revision",
            "reviewerRef": "authorized-review", "definitionOfDoneCount": 0,
            "criteria": {"AC:1": good}, "target": good, "consumer": good}
        def verdict(o):
            return informe.decidir_veredicto(session, board, handoff, True, o, before, after, "HSP-228")[0]
        self.assertEqual(verdict(None), informe.NOT_RUN)
        self.assertEqual(verdict(observation), informe.PASS)
        self.assertEqual(verdict(dict(observation, consumer={"status": "FAIL", "evidenceRefs": ["http:400"]})), informe.FAIL)
        self.assertEqual(verdict(dict(observation, consumer={"status": "NOT_RUN", "evidenceRefs": []})), informe.NOT_RUN)
        self.assertEqual(verdict(dict(observation, criteria={})), informe.FAIL)
        self.assertEqual(verdict(dict(observation, sessionId="stale")), informe.FAIL)
        self.assertEqual(verdict(dict(observation, afterDigest="wrong")), informe.FAIL)
        self.assertEqual(verdict(dict(observation, scope="internal", consumer=None)), informe.PASS)
        board["task_closed"]["ac_completados"] = 0
        self.assertEqual(verdict(observation), informe.FAIL)

    def test_task_identity_not_project_specific_or_ambiguous(self):
        self.assertEqual(informe.id_de_tarea_de_la_rama("feat/hsp-228-oci", ["HSP-228", "PKH-001"]), "HSP-228")
        self.assertEqual(informe.id_de_tarea_de_la_rama("feat/idp-0125-fix", ["IDP-0125"]), "IDP-0125")
        self.assertIsNone(informe.id_de_tarea_de_la_rama("feat/hsp-228-idp-0125", ["HSP-228", "IDP-0125"]))
        self.assertIsNone(informe.id_de_tarea_de_la_rama("feat/hsp-2280", ["HSP-228"]))

class SelfTestTests(unittest.TestCase):
    def test_el_informe_se_certifica(self):
        r = subprocess.run(
            [sys.executable, "-I", str(REPORTE), "--self-test"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("certificado", r.stdout)


if __name__ == "__main__":
    unittest.main()
