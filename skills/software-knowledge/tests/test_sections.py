import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from model import make_corpus, node
from retrieval import Navigator
from sections import split_sections, section_response


class SectionTests(unittest.TestCase):
    def test_roundtrip_unicode_and_fence(self):
        body = "# Identidad\n\nÁrbol\n\n" + "\x60\x60\x60py\n# not heading\n\nx = 1\n\x60\x60\x60\n\n# Recovery\n\nRestart safely.\n"
        parts = split_sections(body)
        self.assertEqual("".join(s["text"] for s in parts), body)
        self.assertTrue(all(body[s["start"]:s["end"]] == s["text"] for s in parts))
        self.assertEqual([s["heading"] for s in parts], ["Identidad", "Recovery"])
        nav = Navigator(make_corpus("demo", [node("a", "contract", "A", "A", body=body)], []))
        result = section_response(nav, "a", query="restart")
        self.assertEqual(len(result["results"]), 1)
        s = result["results"][0]
        self.assertNotIn("text", s)
        full = section_response(nav, "a", section_id=s["id"])
        self.assertEqual(full["results"][0]["text"], body[s["start"]:s["end"]])

    def test_stale_id_and_oversized_block(self):
        body = "x" * 9000
        nav = Navigator(make_corpus("demo", [node("a", "contract", "A", "A", body=body)], []))
        with self.assertRaises(ValueError):
            section_response(nav, "a", section_id="stale")
        r = section_response(nav, "a", section_id=split_sections(body)[0]["id"], budget=1000)
        self.assertEqual(r["results"], [])
        self.assertEqual(r["omitted"], 1)
        self.assertLessEqual(len(json.dumps(r).encode()), 1000)
