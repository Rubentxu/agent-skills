import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from publication_audit import audit
def sample():
    old={"refs/heads/main":"a"*40}
    return dict(schemaVersion=1,kind="publication-audit-input",repositories=[dict(id="repo",baseline=dict(local=old,remote=old),after=dict(local=old,remote=old|{"refs/heads/unauthorized":"b"*40}),allowedLocalRefs=[],allowedRemoteRefs=[],evidenceRef="snapshot:1")])
class PublicationTests(unittest.TestCase):
    def test_unexpected_remote_not_attributed(self):
        r=audit(sample());self.assertEqual(r["status"],"INVESTIGATE");self.assertEqual(r["findings"][0]["attribution"],"UNKNOWN")
    def test_remote_missing_not_clean(self):
        v=sample();v["repositories"][0]["after"]["remote"]=None
        self.assertEqual(audit(v)["status"],"UNKNOWN")
