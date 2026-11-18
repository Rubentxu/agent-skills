import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from knowledge_home import (plan, initialize, resolve, recommend, save_snapshot, read_snapshot,
                            data_root,binding_path,snapshot_path,locate)
from model import make_corpus,node

class HomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{"XDG_DATA_HOME":str(self.root/"data"),
            "XDG_CONFIG_HOME":str(self.root/"config"),"XDG_STATE_HOME":str(self.root/"state")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.repo=self.root/"code"
        self.repo.mkdir()
        self.run_git(self.repo,"init","-q")

    def run_git(self,root,*args):
        subprocess.run(["git","-C",str(root),*args],check=True,capture_output=True)

    def test_user_default_and_no_implicit_relocation(self):
        self.assertEqual(recommend()["mode"],"user-local")
        b=plan("p",[self.repo],"user-local","markdown")
        self.assertFalse(data_root("p").exists())
        with self.assertRaises(ValueError): initialize(b)
        initialize(b,True)
        self.assertEqual(resolve("p"),b)
        self.assertEqual(data_root("p").stat().st_mode & 0o777,0o700)
        self.assertEqual(binding_path("p").stat().st_mode & 0o777,0o600)
        with self.assertRaises(ValueError): initialize(b,True)
        self.assertFalse((self.repo/".knowledge").exists())

    def test_existing_home_backlog_preferred_and_shared_identity(self):
        home=self.root/"home"
        home.mkdir()
        self.run_git(home,"init","-q")
        (home/"backlog").mkdir()
        (home/"backlog/config.yml").write_text("remoteOperations: false\n")
        other=self.root/"other"
        other.mkdir()
        self.assertEqual(recommend(home)["provider"],"backlog")
        with self.assertRaises(ValueError): plan("p",[self.repo],"home-repo","markdown",home,private_home=True)
        with self.assertRaises(ValueError): plan("p",[self.repo],"home-repo","backlog",home)
        b=plan("ecosystem",[self.repo,other],"home-repo","backlog",home,private_home=True)
        initialize(b,True)
        self.assertEqual(resolve("ecosystem")["root"],str(home))
        c=make_corpus("ecosystem",[node("n","term","Term","Summary")],[])
        save_snapshot("ecosystem",c)
        self.assertEqual(read_snapshot("ecosystem"),c)
        self.assertFalse(snapshot_path("ecosystem").is_relative_to(home))
        self.assertEqual(snapshot_path("ecosystem").stat().st_mode & 0o777,0o600)
        colliding=plan("other",[other],"home-repo","backlog",home,private_home=True)
        with self.assertRaises(ValueError): initialize(colliding,True)
        self.assertEqual(list(home.glob("*.json")),[])

    def test_ignored_is_checked_at_init_and_resolution(self):
        with self.assertRaises(ValueError): plan("p",[self.repo],"git-ignored","markdown")
        ex=self.repo/".git/info/exclude"
        ex.write_text("/.knowledge/\n")
        b=plan("p",[self.repo],"git-ignored","markdown")
        initialize(b,True)
        self.assertEqual(resolve("p"),b)
        (self.repo/".knowledge/note.md").write_text("private")
        self.run_git(self.repo,"add","-f",".knowledge/note.md")
        with self.assertRaises(ValueError): resolve("p")

    def test_symlink_and_public_checkout_xdg_refused(self):
        link=self.root/"link"
        link.symlink_to(self.repo,target_is_directory=True)
        with self.assertRaises(ValueError): plan("p",[link],"user-local","markdown")
        with patch.dict(os.environ,{"XDG_DATA_HOME":str(self.repo/"data")}):
            with self.assertRaises(ValueError): plan("p",[self.repo],"user-local","markdown")

    def test_uninitialized_backlog_and_nonempty_markdown_refused(self):
        with self.assertRaises(ValueError): plan("p",[self.repo],"user-local","backlog")
        root=data_root("p")
        root.mkdir(parents=True)
        (root/"existing.md").write_text("existing")
        b=plan("p",[self.repo],"user-local","markdown")
        with self.assertRaises(ValueError): initialize(b,True)


    def test_managed_markdown_navigation(self):
        from knowledge import parser,run
        b=plan("p",[self.repo],"user-local","markdown")
        initialize(b,True)
        self.assertEqual(locate(self.repo)["binding"],b)
        self.assertEqual(locate(self.root)["status"],"unbound")
        result=run(parser().parse_args(["--home","p","overview"]))
        self.assertEqual(result["project"],"p")
        self.assertEqual(result["results"],[])
        with self.assertRaises(ValueError):
            run(parser().parse_args(["--home","p","--project","foreign","overview"]))


    def test_managed_export_refuses_any_git_checkout(self):
        from knowledge import parser,run
        initialize(plan("p",[self.repo],"user-local","markdown"),True)
        with self.assertRaises(ValueError):
            run(parser().parse_args(["--home","p","export",str(self.repo/"bundle")]))
        self.assertFalse((self.repo/"bundle").exists())
