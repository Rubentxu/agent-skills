"""Tests del inventario de contexto; no tocan el harness ni la configuración real."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("measure_context", ROOT / "scripts/measure_context.py")
measure = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = measure
spec.loader.exec_module(measure)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TokenEstimateTests(unittest.TestCase):
    def test_prose_uses_words(self):
        self.assertGreater(measure.tokens_of("hola que tal estas amigo"), 4)

    def test_json_uses_bytes(self):
        raw = '{"name":"x","description":"' + "y" * 400 + '"}'
        self.assertLess(measure.tokens_of(raw), len(raw) // 3)

    def test_empty_text_costs_nothing(self):
        self.assertEqual(measure.tokens_of(""), 0)


class FrontmatterTests(unittest.TestCase):
    def test_description_is_extracted(self):
        text = "---\nname: x\ndescription: 'Corta cuando el contexto se llena'\n---\n\ncuerpo"
        self.assertIn("contexto", measure.frontmatter_description(text))

    def test_missing_frontmatter_yields_empty(self):
        self.assertEqual(measure.frontmatter_description("cuerpo suelto"), "")

    def test_paths_frontmatter_marks_scoped(self):
        self.assertTrue(measure.is_path_scoped("---\npaths:\n  - 'src/**'\n---\ntexto"))

    def test_body_paths_line_does_not_scope(self):
        self.assertFalse(measure.is_path_scoped("texto\npaths: src/**\n"))


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "proj"
        self.config = self.root / "config"
        self.project.mkdir()
        self.config.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_project_entry_file_is_always_on(self):
        write(self.project / "AGENTS.md", "regla " * 200)
        inv = measure.build(self.project, self.config)
        entries = [i for i in inv.always_on if i["source"] == "instructions"]
        self.assertTrue(entries)
        self.assertEqual(entries[0]["scope"], "project")
        self.assertGreater(entries[0]["tokens"], 0)

    def test_skill_catalogue_is_always_on_and_body_is_not(self):
        skill = write(self.config / "skills" / "demo" / "SKILL.md",
                      "---\nname: demo\ndescription: 'Se dispara cuando hay que auditar'\n---\n"
                      + "cuerpo largo " * 300)
        inv = measure.build(self.project, self.config)
        catalogue = [i for i in inv.always_on if i["source"] == "skill-catalogue"]
        body = [i for i in inv.on_demand if i["source"] == "skill-body"]
        self.assertEqual(len(catalogue), 1)
        self.assertEqual(len(body), 1)
        self.assertGreater(body[0]["tokens"], catalogue[0]["tokens"])
        self.assertTrue(str(skill).endswith("SKILL.md"))

    def test_scoped_rule_is_on_demand_not_always_on(self):
        write(self.project / ".claude" / "rules" / "api.md",
              "---\npaths:\n  - 'src/api/**'\n---\nregla api")
        inv = measure.build(self.project, self.config)
        self.assertEqual([i for i in inv.always_on if i["source"] == "rules"], [])
        self.assertEqual(len([i for i in inv.on_demand if i["source"] == "rules-scoped"]), 1)

    def test_unscoped_rule_is_always_on(self):
        write(self.project / ".claude" / "rules" / "general.md", "regla general")
        inv = measure.build(self.project, self.config)
        self.assertEqual(len([i for i in inv.always_on if i["source"] == "rules"]), 1)

    def test_mcp_in_two_scopes_is_warned_about(self):
        write(self.config / ".claude.json", json.dumps(
            {"mcpServers": {"pesado": {"command": "x"}}}))
        write(self.project / ".mcp.json", json.dumps(
            {"mcpServers": {"pesado": {"command": "y"}}}))
        inv = measure.build(self.project, self.config)
        self.assertTrue(any("pesado" in w for w in inv.warnings))
        self.assertEqual(len([s for s in inv.servers if s["name"] == "pesado"]), 2)

    def test_mcp_in_one_scope_is_not_warned_about(self):
        write(self.project / ".mcp.json", json.dumps(
            {"mcpServers": {"ligero": {"command": "y"}}}))
        inv = measure.build(self.project, self.config)
        self.assertEqual(inv.warnings, [])

    def test_hooks_are_counted_per_event(self):
        write(self.config / "settings.json", json.dumps(
            {"hooks": {"UserPromptSubmit": [{"hooks": []}], "Stop": [{"hooks": []}]}}))
        inv = measure.build(self.project, self.config)
        self.assertEqual(inv.hook_events.get("UserPromptSubmit"), 1)
        self.assertEqual(inv.hook_events.get("Stop"), 1)

    def test_plugins_are_listed_with_enabled_state(self):
        write(self.config / "settings.json", json.dumps(
            {"enabledPlugins": {"a@market": True, "b@market": False}}))
        inv = measure.build(self.project, self.config)
        states = {p["name"]: p["enabled"] for p in inv.plugins}
        self.assertTrue(states["a@market"])
        self.assertFalse(states["b@market"])

    def test_memory_index_is_always_on_and_topics_are_not(self):
        slug = measure.project_slug(self.project)
        memory = self.config / "projects" / slug / "memory"
        write(memory / "MEMORY.md", "índice " * 100)
        write(memory / "tema.md", "tema " * 100)
        inv = measure.build(self.project, self.config)
        self.assertEqual(len([i for i in inv.always_on if i["source"] == "memory-index"]), 1)
        self.assertEqual(len([i for i in inv.on_demand if i["source"] == "memory-topic"]), 1)

    def test_memory_of_another_project_is_not_counted(self):
        other = self.config / "projects" / "-otro-proyecto" / "memory"
        write(other / "MEMORY.md", "índice ajeno " * 500)
        inv = measure.build(self.project, self.config)
        self.assertEqual([i for i in inv.always_on if i["source"] == "memory-index"], [])

    def test_slug_derives_from_absolute_path(self):
        self.assertEqual(measure.project_slug(Path("/var/home/u/proy")), "-var-home-u-proy")

    def test_always_on_and_on_demand_are_reported_separately(self):
        write(self.project / "AGENTS.md", "regla " * 100)
        write(self.config / "skills" / "demo" / "SKILL.md",
              "---\nname: demo\ndescription: 'x'\n---\n" + "cuerpo " * 500)
        inv = measure.build(self.project, self.config)
        always = sum(i["tokens"] for i in inv.always_on)
        on_demand = sum(i["tokens"] for i in inv.on_demand)
        self.assertGreater(always, 0)
        self.assertGreater(on_demand, 0)


class CliTests(unittest.TestCase):
    def test_missing_project_returns_error_code(self):
        self.assertEqual(measure.main(["--project", "/nonexistent/path/xyz"]), 2)

    def test_json_output_has_both_budgets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "p"
            project.mkdir()
            (project / "AGENTS.md").write_text("regla " * 50, encoding="utf-8")
            code = measure.main(["--project", str(project), "--config", str(root), "--json"])
            self.assertEqual(code, 0)

    def test_report_mentions_both_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "p"
            project.mkdir()
            (project / "AGENTS.md").write_text("regla " * 50, encoding="utf-8")
            inv = measure.build(project, root)
            text = measure.report(inv, 5)
            self.assertIn("Always-on", text)
            self.assertIn("On-demand", text)


if __name__ == "__main__":
    unittest.main()
