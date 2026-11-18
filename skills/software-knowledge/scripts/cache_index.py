"""Optional, disposable SQLite/FTS5 projection, exclusively outside source checkouts."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat

from model import MAX_BYTES, digest, identifier, require, validate, v1_to_v2
from providers import markdown_corpus
from retrieval import Navigator, INTENTS, normalize, tokens, fusion
from sections import split_sections

VERSION = 1
APPLICATION = 0x4B4E4F57
CANDIDATES = 512


def checkout_ancestor(path: Path) -> bool:
    return any((p / ".git").exists() or (p / ".git").is_symlink()
               for p in (path, *path.parents))


def cache_path(project: str, source: Path, provider: str) -> Path:
    require(identifier(project), "Explicit project identity required for cache")
    source = source.resolve()
    configured = os.environ.get("XDG_CACHE_HOME")
    root = Path(configured) if configured else Path.home() / ".cache"
    require(root.is_absolute(), "XDG_CACHE_HOME must be absolute")
    root = root.resolve()
    directory = root / "software-knowledge" / f"index-v{VERSION}"
    require(not checkout_ancestor(directory.resolve()), "Cache must be outside every Git checkout")
    if provider == "markdown":
        require(not directory.resolve().is_relative_to(source), "Cache must be outside Markdown root")
    if source.is_file():
        # For a snapshot at the checkout root, never place the cache under that parent.
        require(not checkout_ancestor(source.parent) or not directory.resolve().is_relative_to(source.parent),
                "Cache must be outside source repository")
    for path in (root / "software-knowledge", directory):
        require(not path.is_symlink(), "Cache directories must not be symlinks")
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = path.stat()
        require(path.is_dir(), "Invalid cache directory")
        if hasattr(os, "getuid"):
            require(info.st_uid == os.getuid() and not info.st_mode & 0o077,
                    "Cache directory must be private (0700)")
    key = digest([VERSION, project, provider, str(source)])
    return directory / (key + ".sqlite3")


def source_input(source: Path, provider: str, project: str):
    """Return content fingerprint and lazy validated loader. Never trust mtime."""
    if provider == "markdown":
        data = markdown_corpus(source, project)
        return digest(data), lambda: data
    require(source.is_file(), "Missing corpus source")
    with source.open("rb") as f:
        raw = f.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, "Oversized corpus source")
    def load():
        data = json.loads(raw)
        require(isinstance(data, dict), "Expected JSON corpus object")
        if data.get("schemaVersion") == 1:
            data = v1_to_v2(data, project)
        validate(data)
        require(data["project"] == project, "Project mismatch")
        return data
    return hashlib.sha256(raw).hexdigest(), load


DDL = (
    "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE nodes (id TEXT PRIMARY KEY, hash TEXT NOT NULL, level TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL)",
    "CREATE INDEX nodes_level ON nodes(level, id)",
    "CREATE INDEX nodes_kind ON nodes(kind, id)",
    "CREATE TABLE aliases (alias TEXT NOT NULL, id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE, PRIMARY KEY(alias,id))",
    "CREATE TABLE contexts (context TEXT NOT NULL, id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE, PRIMARY KEY(context,id))",
    "CREATE TABLE edges (src TEXT NOT NULL, predicate TEXT NOT NULL, dst TEXT NOT NULL, hash TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(src,predicate,dst))",
    "CREATE INDEX edges_dst ON edges(dst,src,predicate)",
    "CREATE TABLE sections (node TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE, start INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(node,start))",
    """CREATE VIRTUAL TABLE lexical USING fts5(node UNINDEXED, identity, title, aliases, scope, summary, body, tokenize="unicode61 tokenchars '_'")""",
)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def open_database(path: Path):
    require(not path.is_symlink(), "Cache database must not be a symlink")
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    except FileExistsError:
        pass
    info = path.stat()
    require(stat.S_ISREG(info.st_mode), "Invalid cache database file")
    if hasattr(os, "getuid"):
        require(info.st_uid == os.getuid() and not info.st_mode & 0o077,
                "Cache database must be private (0600)")
    conn = sqlite3.connect(path, timeout=5)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def ensure_schema(conn):
    app = conn.execute("PRAGMA application_id").fetchone()[0]
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if app == APPLICATION and version == VERSION:
        return
    require(app == 0 and version == 0 and not conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone(),
            "Unknown cache format; remove the disposable cache explicitly")
    for stmt in DDL:
        conn.execute(stmt)
    conn.execute(f"PRAGMA application_id={APPLICATION}")
    conn.execute(f"PRAGMA user_version={VERSION}")


def metadata(conn):
    return dict(conn.execute("SELECT key,value FROM meta"))


def delete_node(conn, identity):
    row = conn.execute("SELECT rowid FROM nodes WHERE id=?", (identity,)).fetchone()
    if row is not None:
        conn.execute("DELETE FROM lexical WHERE rowid=?", (row[0],))
        conn.execute("DELETE FROM nodes WHERE id=?", (identity,))


def replace_node(conn, n, h):
    i = n["id"]
    delete_node(conn, i)
    rowid = conn.execute("INSERT INTO nodes VALUES (?,?,?,?,?)",
                         (i, h, n["level"], n["kind"], encode(n))).lastrowid
    aliases = {normalize(x) for x in [i, n["title"], *n.get("aliases", [])]}
    conn.executemany("INSERT INTO aliases VALUES (?,?)", ((a, i) for a in sorted(aliases)))
    conn.executemany("INSERT INTO contexts VALUES (?,?)", ((c, i) for c in sorted(set(n.get("contexts", [])))))
    conn.execute("INSERT INTO lexical(rowid,node,identity,title,aliases,scope,summary,body) VALUES (?,?,?,?,?,?,?,?)",
                 (rowid, i, normalize(i), normalize(n["title"]), normalize(" ".join(n.get("aliases", []))),
                  normalize(" ".join(n.get("tags", []) + n.get("contexts", []))),
                  normalize(n["summary"]), normalize(n.get("body", ""))))
    conn.executemany("INSERT INTO sections VALUES (?,?,?)",
                     ((i, s["start"], encode(s)) for s in split_sections(n.get("body", ""))))


def sync(conn, corpus, fingerprint):
    validate(corpus)
    old_nodes = dict(conn.execute("SELECT id,hash FROM nodes"))
    old_edges = {(a, p, b): h for a, p, b, h in conn.execute("SELECT src,predicate,dst,hash FROM edges")}
    nodes = {n["id"]: (n, digest(n)) for n in corpus["nodes"]}
    edges = {(e["from"], e["predicate"], e["to"]): (e, digest(e)) for e in corpus["edges"]}
    removed = old_nodes.keys() - nodes.keys()
    changed = {i for i, (_, h) in nodes.items() if old_nodes.get(i) != h}
    edge_removed = old_edges.keys() - edges.keys()
    edge_changed = {k for k, (_, h) in edges.items() if old_edges.get(k) != h}
    for i in sorted(removed):
        delete_node(conn, i)
    for i in sorted(changed):
        replace_node(conn, *nodes[i])
    for k in sorted(edge_removed):
        conn.execute("DELETE FROM edges WHERE src=? AND predicate=? AND dst=?", k)
    for k in sorted(edge_changed):
        e, h = edges[k]
        conn.execute("INSERT OR REPLACE INTO edges VALUES (?,?,?,?,?)", (*k, h, encode(e)))
    conn.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)",
                     (("project", corpus["project"]), ("coverage", corpus["coverage"]),
                      ("source_digest", fingerprint)))
    return {"reused": False, "nodes_reindexed": len(changed), "nodes_removed": len(removed),
            "edges_reindexed": len(edge_changed), "edges_removed": len(edge_removed)}


class Nodes(Mapping):
    def __init__(self, conn):
        self.conn = conn
        self._get = lru_cache(maxsize=256)(self._load)

    def __getitem__(self, key):
        return self._get(key)

    def _load(self, key):
        row = self.conn.execute("SELECT payload FROM nodes WHERE id=?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        return json.loads(row[0])

    def __contains__(self, key):
        return self.conn.execute("SELECT 1 FROM nodes WHERE id=?", (key,)).fetchone() is not None

    def __iter__(self):
        return (r[0] for r in self.conn.execute("SELECT id FROM nodes ORDER BY id"))

    def __len__(self):
        return self.conn.execute("SELECT count(*) FROM nodes").fetchone()[0]


class Adjacency:
    def __init__(self, conn, incoming=False):
        self.conn, self.incoming = conn, incoming
        self._get = lru_cache(maxsize=256)(self._load)

    def __getitem__(self, identity):
        return self._get(identity)

    def _load(self, identity):
        column = "dst" if self.incoming else "src"
        return [json.loads(r[0]) for r in self.conn.execute(
            f"SELECT payload FROM edges WHERE {column}=? ORDER BY src,predicate,dst", (identity,))]


class CachedNavigator(Navigator):
    """Reuse graph planning and rendering; access node/edge payloads on demand."""
    def __init__(self, conn, meta):
        self.conn = conn
        self.corpus = {"project": meta["project"], "coverage": meta["coverage"]}
        self.nodes = Nodes(conn)
        self.out, self.inc = Adjacency(conn), Adjacency(conn, True)
        self.search_cut = False

    def sections(self, identity):
        return [json.loads(r[0]) for r in self.conn.execute(
            "SELECT payload FROM sections WHERE node=? ORDER BY start", (identity,))]

    def ids_for_level(self, level):
        return [r[0] for r in self.conn.execute("SELECT id FROM nodes WHERE level=? ORDER BY id", (level,))]

    def search(self, query, *, intent="implement", context=None, kind=None, level=None):
        require(intent in INTENTS, "Unknown retrieval intent")
        self.search_cut = False
        conditions, params = [], []
        for column, value in (("kind", kind), ("level", level)):
            if value:
                conditions.append(f"n.{column}=?")
                params.append(value)
        if context:
            conditions.append("EXISTS (SELECT 1 FROM contexts c WHERE c.id=n.id AND c.context=?)")
            params.append(context)
        where = "".join(" AND " + c for c in conditions)
        exact = [r[0] for r in self.conn.execute(
            "SELECT n.id FROM nodes n WHERE n.id=?" + where, (query, *params))]
        if not exact:
            exact = [r[0] for r in self.conn.execute(
                "SELECT n.id FROM aliases a JOIN nodes n ON n.id=a.id WHERE a.alias=?" + where +
                " ORDER BY n.id LIMIT ?", (normalize(query), *params, CANDIDATES + 1))]
        self.search_cut = len(exact) > CANDIDATES
        exact = exact[:CANDIDATES]
        words = sorted(set(tokens(query)))
        if len(words) > 64:
            self.search_cut = True
            words = words[:64]
        if not words:
            return exact
        match = " OR ".join('"' + w.replace('"', '""') + '"' for w in words)
        rows = list(self.conn.execute(
            "SELECT n.id,n.kind FROM lexical JOIN nodes n ON n.id=lexical.node WHERE lexical MATCH ?" +
            where + " ORDER BY bm25(lexical,0,5,5,4,3,2,1),n.id LIMIT ?",
            (match, *params, CANDIDATES + 1)))
        self.search_cut = self.search_cut or len(rows) > CANDIDATES
        rows = rows[:CANDIDATES]
        lexical = [i for i, _ in rows]
        preferred = [i for i, k in rows if k in INTENTS[intent]]
        ranked = fusion([lexical, preferred])
        exact_ids = set(exact)
        result = exact + [i for i in ranked if i not in exact_ids]
        self.search_cut = self.search_cut or len(result) > CANDIDATES
        return result[:CANDIDATES]


@contextmanager
def indexed(source: Path, provider: str, project: str):
    require(provider in ("snapshot", "markdown"), "Unsupported index source")
    path = cache_path(project, source, provider)
    fingerprint, load = source_input(source, provider, project)
    conn = open_database(path)
    nav = None
    try:
        # One transaction spans sync and query. No stale hit or mixed concurrent projection.
        conn.execute("BEGIN IMMEDIATE")
        ensure_schema(conn)
        meta = metadata(conn)
        require(not meta or meta.get("project") == project, "Cache project mismatch")
        if meta.get("source_digest") == fingerprint:
            stats = {"reused": True, "nodes_reindexed": 0, "nodes_removed": 0,
                     "edges_reindexed": 0, "edges_removed": 0}
        else:
            stats = sync(conn, load(), fingerprint)
            meta = metadata(conn)
        nav = CachedNavigator(conn, meta)
        stats.update({"project": project, "source_digest": fingerprint, "cache_path": str(path),
                      "nodes": len(nav.nodes), "index_version": VERSION})
        yield nav, stats
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        # Per-transaction caches cannot retain or invalidate other connections.
        if nav is not None:
            nav.nodes._get.cache_clear()
            nav.out._get.cache_clear()
            nav.inc._get.cache_clear()
        conn.close()
