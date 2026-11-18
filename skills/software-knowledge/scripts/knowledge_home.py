#!/usr/bin/env python3
"""Private placement of knowledge; explicit binding, never Git init/add/push or Backlog writes."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

from model import MAX_BYTES, digest, identifier, require, validate

MODES = ("home-repo", "user-local", "git-ignored")
PROVIDERS = ("backlog", "markdown")
MAX_DESCRIPTOR = 65536


def absolute(value):
    p = Path(value).expanduser()
    require(p.is_absolute() and ".." not in p.parts, "Use explicit absolute path")
    require(not any(a.is_symlink() for a in (p,*p.parents)), "Symlink location refused")
    return p.resolve()


def checkout(p):
    return any((a/".git").exists() or (a/".git").is_symlink() for a in (p,*p.parents))


def xdg(var, fallback):
    raw=os.environ.get(var)
    p=Path(raw) if raw and Path(raw).is_absolute() else Path.home()/fallback
    p=absolute(absolute(p)/"software-knowledge")
    require(not checkout(p), "User storage must be outside any Git checkout")
    return p


def outside_git(path):
    p=absolute(path)
    require(not checkout(p),"Private data location must be outside every Git checkout")
    return p


def key(project):
    require(identifier(project), "Explicit stable knowledge project ID required")
    return digest(["knowledge-home-v1",project])


def binding_path(project):
    return outside_git(xdg("XDG_CONFIG_HOME",".config")/"bindings-v1"/(key(project)+".json"))


def snapshot_path(project):
    return outside_git(xdg("XDG_STATE_HOME",".local/state")/"snapshots-v1"/(key(project)+".json"))


def data_root(project):
    return outside_git(xdg("XDG_DATA_HOME",".local/share")/"projects"/key(project))


def private_dir(path):
    path=absolute(path)
    if not path.exists():
        # Make only owned application subdirectories private; do not chmod existing paths.
        path.mkdir(mode=0o700,parents=True,exist_ok=True)
    s=path.stat()
    require(stat.S_ISDIR(s.st_mode), "Expected private directory")
    if hasattr(os,"getuid"):
        require(s.st_uid==os.getuid() and not s.st_mode & 0o077,"Expected user-owned private directory (0700)")


def read_private(path, maximum=MAX_DESCRIPTOR):
    path=absolute(path)
    s=path.stat()
    require(stat.S_ISREG(s.st_mode) and s.st_size<=maximum,"Invalid private file")
    if hasattr(os,"getuid"):
        require(s.st_uid==os.getuid() and not s.st_mode & 0o077,"Expected user-owned private file (0600)")
    with path.open("rb") as f:
        raw=f.read(maximum+1)
    require(len(raw)<=maximum,"Private input exceeds limit")
    return json.loads(raw)


def write_private(path, data, *, replace=False, maximum=MAX_DESCRIPTOR):
    raw=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    require(len(raw)<=maximum,"Private output exceeds limit")
    private_dir(path.parent)
    absolute(path)
    if path.exists():
        require(replace,"Refuse to overwrite existing binding")
        read_private(path,maximum)
    fd,tmp=tempfile.mkstemp(prefix=".knowledge-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        if replace:
            os.replace(tmp,path)
        else:
            os.link(tmp,path)  # no-clobber in same directory
    finally:
        Path(tmp).unlink(missing_ok=True)


def git(repo,*args,input=None,ok=(0,)):
    env={k:v for k,v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0",GIT_TERMINAL_PROMPT="0",GIT_LITERAL_PATHSPECS="1")
    try:
        out=subprocess.run(["git","-C",str(repo),*args],input=input,stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,env=env,timeout=10)
    except subprocess.TimeoutExpired:
        raise ValueError("Local Git policy check timed out") from None
    require(out.returncode in ok and len(out.stdout)<=MAX_BYTES,"Local Git inspection failed")
    return out.stdout


def git_root(repo):
    require(repo.is_dir(),"Git root must exist")
    require(Path(os.fsdecode(git(repo,"rev-parse","--show-toplevel").rstrip(b"\n"))).resolve()==repo,
            "Select exact Git root")


def ignored(repo, root):
    git_root(repo)
    rel=root.relative_to(repo).as_posix()
    require(not rel.startswith(":"),"Invalid Git knowledge path")
    require(not git(repo,"ls-files","-z","--",rel),"Knowledge destination has tracked entries")
    probes=[root/".knowledge-home.json",root/"probe.md",root/"backlog"/"docs"/"probe.md"]
    if root.exists():
        for i,p in enumerate(root.rglob("*")):
            require(i<10000,"Ignored destination too large to verify")
            require(not p.is_symlink() and p.name!=".git","Nested Git or symlink refused")
            probes.append(p)
    data=os.fsencode(rel+"/")+b"\0"+b"".join(os.fsencode(x.relative_to(repo).as_posix())+b"\0" for x in probes)
    out=git(repo,"check-ignore","--no-index","-z","--stdin",input=data,ok=(0,1))
    require(set(out.split(b"\0"))==set(data.split(b"\0")),
            "Destination must already be ignored; inspect local Git exclusions")


def backlog_ready(root):
    return any((root/p).is_file() and not (root/p).is_symlink() for p in (
        "backlog.config.yml","backlog.json","backlog/config.yml","backlog/config.yaml",
        ".backlog/config.yml",".backlog/config.yaml"))


def recommend(home=None):
    if home is not None:
        home=absolute(home)
        git_root(home)
        if backlog_ready(home):
            return {"mode":"home-repo","provider":"backlog","reason":"existing-home-backlog"}
        return {"mode":"home-repo","provider":"markdown","reason":"explicit-home-candidate"}
    return {"mode":"user-local","provider":"markdown","reason":"no-home-candidate-supplied"}


def plan(project,repos,mode,provider,home=None,location=None,private_home=False):
    key(project)
    require(mode in MODES and provider in PROVIDERS,"Choose placement and provider explicitly")
    roots=sorted({str(absolute(x)) for x in repos})
    require(roots and len(roots)<=64 and all(Path(x).is_dir() for x in roots),"Select existing code roots")
    h=absolute(home) if home else None
    if mode=="home-repo":
        require(h is not None and private_home,"Confirm Home Repo private or local-only")
        if backlog_ready(h):
            require(provider=="backlog" and (location is None or absolute(location)==h),
                    "Reuse the existing Home Repo Backlog as sole authority")
        root=absolute(location) if location else (h if provider=="backlog" else h/"knowledge"/"projects"/key(project))
    elif mode=="git-ignored":
        require(len(roots)==1 and h is None and not private_home,"Ignored mode requires one code checkout")
        root=absolute(location) if location else Path(roots[0])/".knowledge"
    else:
        require(h is None and location is None and not private_home,"User-local uses XDG data path")
        root=data_root(project)
    b={"schemaVersion":1,"kind":"knowledge-home-binding","project":project,"repos":roots,
       "mode":mode,"provider":provider,"root":str(root),"home":str(h) if h else None,
       "private_home_attested":private_home}
    verify(b)
    return b


def verify(b):
    require(isinstance(b,dict) and set(b)=={"schemaVersion","kind","project","repos","mode","provider","root","home","private_home_attested"}
            and b["schemaVersion"]==1 and b["kind"]=="knowledge-home-binding"
            and b["mode"] in MODES and b["provider"] in PROVIDERS,"Invalid binding")
    key(b["project"])
    require(isinstance(b["repos"],list) and 1<=len(b["repos"])<=64,"Invalid code roots")
    repos=[absolute(x) for x in b["repos"]]
    require(len(set(repos))==len(repos) and all(x.is_dir() for x in repos),"Code root moved or missing; review binding")
    root=absolute(b["root"])
    mode=b["mode"]
    if mode=="home-repo":
        require(b["private_home_attested"] is True and b["home"],"Private Home Repo attestation required")
        home=absolute(b["home"])
        git_root(home)
        if backlog_ready(home):
            require(b["provider"]=="backlog" and root==home,"Existing Home Repo Backlog must remain authority")
        require(root.is_relative_to(home) and (root!=home or b["provider"]=="backlog")
                and ".git" not in root.relative_to(home).parts,"Knowledge must be within selected Home Repo")
        require(all(not root.is_relative_to(x) and not home.is_relative_to(x) for x in repos),
                "Home Repo must be separate from code repos")
        require(not any((a/".git").exists() for a in (root,*root.parents)
                        if a!=home and a.is_relative_to(home)),"Nested repository refused")
    elif mode=="git-ignored":
        require(len(repos)==1 and b["home"] is None and b["private_home_attested"] is False,"Invalid ignored binding")
        repo=repos[0]
        require(root.is_relative_to(repo) and root!=repo and ".git" not in root.relative_to(repo).parts,
                "Ignored destination must be inside code checkout")
        require(not any((a/".git").exists() for a in (root,*root.parents)
                        if a!=repo and a.is_relative_to(repo)),"Nested repository refused")
        ignored(repo,root)
    else:
        require(root==data_root(b["project"]) and not checkout(root) and b["home"] is None
                and b["private_home_attested"] is False and all(not root.is_relative_to(x) for x in repos),
                "Invalid user-local placement")
    if root.exists():
        require(root.is_dir(),"Expected knowledge directory")
    if b["provider"]=="backlog":
        require(backlog_ready(root),"Select existing Backlog root; no automatic init")
    return root


def initialize(b,confirm=False):
    require(confirm,"Explicit confirmation required")
    root=verify(b)
    bp=binding_path(b["project"])
    private_dir(bp.parent)
    lock=bp.parent/".init-lock"
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.close(fd)
    try:
        return _initialize_locked(b,root,bp)
    finally:
        lock.unlink(missing_ok=True)


def _initialize_locked(b,root,bp):
    require(not bp.exists() and not bp.is_symlink(),"Project already initialized; no implicit relocation")
    if bp.parent.exists():
        private_dir(bp.parent)
        for i,p in enumerate(sorted(bp.parent.glob("*.json"))):
            require(i<10000,"Binding inventory too large")
            old=read_private(p)
            old_root=absolute(old["root"])
            require(not root.is_relative_to(old_root) and not old_root.is_relative_to(root),
                    "Overlapping knowledge authority; use existing ecosystem identity")
            require(not set(b["repos"]) & set(old["repos"]),"Code repo already bound to knowledge home")
    if b["provider"]=="markdown":
        # New empty dedicated root only; already populated roots require explicit migration.
        require(not root.exists() or not any(root.iterdir()),"Existing nonempty Markdown root requires explicit adoption review")
        private_dir(root)
    write_private(bp,b)
    return b


def resolve(project):
    p=binding_path(project)
    private_dir_check=p.parent
    require(private_dir_check.is_dir() and p.is_file(),"Knowledge home not initialized")
    private_dir(private_dir_check)
    b=read_private(p)
    require(b["project"]==project,"Binding project mismatch")
    root=verify(b)
    require(root.is_dir(),"Knowledge root missing")
    if b["provider"]=="markdown":
        private_dir(root)
    return b


def locate(repo):
    root=str(absolute(repo))
    directory=binding_path("lookup").parent
    if not directory.exists():
        return {"status":"unbound","placement_required":True}
    private_dir(directory)
    matches=[]
    for i,p in enumerate(sorted(directory.glob("*.json"))):
        require(i<10000,"Binding inventory too large")
        b=read_private(p)
        if root in b["repos"] or root==b["home"]:
            matches.append(b["project"])
    require(len(matches)<=1,"Ambiguous knowledge home; review bindings")
    if not matches:
        return {"status":"unbound","placement_required":True}
    return {"status":"bound","binding":resolve(matches[0])}


def save_snapshot(project,corpus):
    b=resolve(project)
    require(b["provider"]=="backlog","Snapshots are derived from managed Backlog root")
    validate(corpus)
    require(corpus["project"]==project,"Snapshot identity mismatch")
    path=snapshot_path(project)
    write_private(path,{**corpus,"home_binding_digest":digest(b)},replace=True,maximum=MAX_BYTES)
    return path


def read_snapshot(project):
    b=resolve(project)
    require(b["provider"]=="backlog","No managed Backlog snapshot for Markdown")
    data=read_private(snapshot_path(project),MAX_BYTES)
    require(data.pop("home_binding_digest",None)==digest(b),"Snapshot binding changed; recapture")
    c=validate(data)
    require(c["project"]==project,"Snapshot project mismatch")
    return c


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    rec=sub.add_parser("recommend")
    rec.add_argument("--home-repo",type=Path)
    for name in ("plan","init"):
        s=sub.add_parser(name)
        s.add_argument("--project",required=True)
        s.add_argument("--repo",type=Path,action="append",required=True)
        s.add_argument("--mode",choices=MODES,required=True)
        s.add_argument("--provider",choices=PROVIDERS,required=True)
        s.add_argument("--home-repo",type=Path)
        s.add_argument("--location",type=Path)
        s.add_argument("--confirm-private-home",action="store_true")
        if name=="init":
            s.add_argument("--confirm",action="store_true")
    l=sub.add_parser("locate")
    l.add_argument("--repo",type=Path,required=True)
    s=sub.add_parser("resolve")
    s.add_argument("--project",required=True)
    a=p.parse_args()
    try:
        if a.command=="recommend":
            result=recommend(a.home_repo)
        elif a.command=="locate":
            result=locate(a.repo)
        elif a.command=="resolve":
            result=resolve(a.project)
        else:
            result=plan(a.project,a.repo,a.mode,a.provider,a.home_repo,a.location,a.confirm_private_home)
            if a.command=="init":
                initialize(result,a.confirm)
        print(json.dumps(result,ensure_ascii=False,separators=(",",":")))
    except (ValueError,TypeError,KeyError,OSError,subprocess.SubprocessError) as e:
        print(json.dumps({"status":"invalid-home","error":str(e)}),file=sys.stderr)
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
