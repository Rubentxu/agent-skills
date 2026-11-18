import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate import evaluate, metrics
from model import load_json


class EvaluationTests(unittest.TestCase):
    def test_metrics_and_abstention(self):
        m = metrics(["wrong", "right"], {"right"}, 2)
        self.assertEqual(m["recall_at_k"], 1)
        self.assertEqual(m["precision_at_k"], 0.5)
        self.assertEqual(m["mrr"], 0.5)
        self.assertTrue(metrics([], set(), 2)["correct_abstention"])
        self.assertFalse(metrics(["wrong"], set(), 2)["correct_abstention"])

    def test_fixture_and_determinism(self):
        corpus = load_json(ROOT / "examples" / "corpus.json")
        questions = load_json(ROOT / "examples" / "questions.json")
        report = evaluate(corpus, questions)
        self.assertEqual(report, evaluate(corpus, questions))
        self.assertEqual(report["questions"], 4)
        self.assertEqual(report["aggregate"]["active"]["correct_abstention"], 1)
        self.assertEqual(set(report["aggregate"]), {"bm25", "ranked", "active", "adaptive"})
