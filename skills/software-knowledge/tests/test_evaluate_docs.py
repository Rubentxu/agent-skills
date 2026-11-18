import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from evaluate_docs import build


class EvaluationDocsTests(unittest.TestCase):
    def test_selected_document_bytes_and_no_source_inspection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"policy.md").write_text("# Policy\nExact documentation.\n")
            (root/"secret.py").write_text("UNSELECTED")
            m={"schemaVersion":1,"kind":"documentation-evaluation","project":"demo",
               "documents":[{"id":"policy","kind":"contract","title":"Policy","summary":"Rules","path":"policy.md"}]}
            c=build(root,m)
            self.assertEqual(c["nodes"][0]["body"],(root/"policy.md").read_text())
            self.assertEqual(c["nodes"][0]["claim_state"],"unknown")
            self.assertNotIn("UNSELECTED",str(c))
            m["documents"][0]["path"]="secret.py"
            with self.assertRaises(ValueError):
                build(root,m)
            m["documents"][0]["path"]="../else.md"
            with self.assertRaises(ValueError):
                build(root,m)
