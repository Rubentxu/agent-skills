"""Deterministic, bounded navigation of an explicit corpus."""
from __future__ import annotations

from collections import Counter, defaultdict, deque
import math
import re
import unicodedata

from model import validate, digest, require

PROFILES = {"quick": (3, 1, 4000), "normal": (5, 2, 12000), "deep": (8, 3, 32000)}
INTENTS = {
    "understand": {"profile", "track", "capability", "use-case"},
    "implement": {"invariant", "contract", "decision", "convention", "use-case"},
    "refactor": {"invariant", "contract", "pattern", "decision", "convention"},
    "verify": {"invariant", "contract", "evidence", "test"},
    "debug": {"evidence", "finding", "risk", "hypothesis", "lesson", "failed-experiment"},
    "security": {"invariant", "contract", "risk", "convention", "decision"},
    "architecture": {"track", "decision", "contract", "invariant", "pattern"},
}
CRITICAL = {"invariant", "contract", "convention", "decision"}
SEMANTIC = {"constrains", "requires", "implements", "verified_by", "governs",
            "contradicts", "supersedes", "violates", "motivates", "applies_to",
            "derived_from", "contains", "about", "validates"}


def normalize(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                   if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    return re.findall(r"\w+", normalize(text))


def fusion(rankings: list[list[str]], k: int = 60) -> list[str]:
    scores = defaultdict(float)
    for ranking in rankings:
        for pos, i in enumerate(dict.fromkeys(ranking), 1):
            scores[i] += 1 / (k + pos)
    return sorted(scores, key=lambda i: (-scores[i], i))


class Navigator:
    def __init__(self, corpus: dict):
        self.corpus = validate(corpus)
        self.nodes = {n["id"]: n for n in corpus["nodes"]}
        self.out, self.inc, self.alias = defaultdict(list), defaultdict(list), defaultdict(set)
        self.postings = defaultdict(dict)
        self.length = {}
        for i, n in self.nodes.items():
            for alias in [i, n["title"], *n.get("aliases", [])]:
                self.alias[normalize(alias)].add(i)
            # Weighted field term frequency, BM25 length normalization.
            counts = Counter()
            for weight, field in ((5, i), (5, n["title"]),
                                  (4, " ".join(n.get("aliases", []))),
                                  (3, " ".join(n.get("tags", []) + n.get("contexts", []))),
                                  (2, n["summary"]), (1, n.get("body", ""))):
                for term, amount in Counter(tokens(field)).items():
                    counts[term] += weight * amount
            self.length[i] = sum(counts.values())
            for term, amount in counts.items():
                self.postings[term][i] = amount
        self.avg = sum(self.length.values()) / max(1, len(self.length)) or 1
        for e in sorted(corpus["edges"], key=lambda e: (e["from"], e["predicate"], e["to"])):
            self.out[e["from"]].append(e)
            self.inc[e["to"]].append(e)

    def sections(self, identity: str) -> list[dict]:
        from sections import split_sections
        return split_sections(self.nodes[identity].get("body", ""))

    def ids_for_level(self, level: str) -> list[str]:
        return sorted(i for i, n in self.nodes.items() if n["level"] == level)

    def fingerprint(self, identity: str) -> str:
        return digest({"node": self.nodes[identity], "out": self.out[identity], "in": self.inc[identity]})

    def lexical(self, query: str, eligible: set[str]) -> list[str]:
        scores = defaultdict(float)
        count = len(self.nodes)
        for term in sorted(set(tokens(query))):
            postings = self.postings.get(term, {})
            idf = math.log(1 + (count - len(postings) + 0.5) / (len(postings) + 0.5))
            for i, tf in postings.items():
                if i in eligible:
                    scores[i] += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * self.length[i] / self.avg))
        return sorted(scores, key=lambda i: (-scores[i], i))

    def walk(self, anchors: list[str], depth: int, relations: set[str] | None = None,
             direction: str = "both", max_nodes: int = 200, max_edges: int = 2000) -> tuple[dict, bool]:
        require(0 <= depth <= 3 and 1 <= max_nodes <= 1000 and 1 <= max_edges <= 10000,
                "Traversal budget invalid")
        require(direction in {"both", "out", "in"}, "Invalid direction")
        require(all(i in self.nodes for i in anchors), "Unknown anchor")
        require(len(set(anchors)) <= max_nodes, "Too many anchors")
        visited = {i: (0, []) for i in anchors}
        todo = deque(sorted(visited))
        examined = 0
        while todo:
            i = todo.popleft()
            distance, path = visited[i]
            if distance >= depth:
                continue
            edges = []
            if direction != "in":
                edges.extend((e, e["to"]) for e in self.out[i])
            if direction != "out":
                edges.extend((e, e["from"]) for e in self.inc[i])
            for edge, other in edges:
                examined += 1
                if examined > max_edges:
                    return visited, True
                if relations is not None and edge["predicate"] not in relations:
                    continue
                if other in visited:
                    continue
                if len(visited) >= max_nodes:
                    return visited, True
                visited[other] = (distance + 1, path + [edge])
                todo.append(other)
        return visited, False

    def search(self, query: str, *, intent: str = "implement", context: str | None = None,
               kind: str | None = None, level: str | None = None) -> list[str]:
        require(intent in INTENTS, "Unknown retrieval intent")
        eligible = {i for i, n in self.nodes.items() if
                    (not context or context in n.get("contexts", [])) and
                    (not kind or kind == n["kind"]) and (not level or level == n["level"])}
        exact = ({query} if query in self.nodes else self.alias.get(normalize(query), set())) & eligible
        lexical = self.lexical(query, eligible)
        preferred = [i for i in lexical if self.nodes[i]["kind"] in INTENTS[intent]]
        ranked = fusion([lexical, preferred])
        return sorted(exact) + [i for i in ranked if i not in exact]

    def plan(self, query: str, anchors: list[str], intent: str, depth: int) -> tuple[list[str], dict, bool]:
        """Resolve exact anchors first, then bounded semantic expansion; include conflicting claims."""
        require(intent in INTENTS, "Unknown intent")
        searched = self.search(query, intent=intent) if query else []
        seeds = list(dict.fromkeys(anchors + searched[:3]))
        if not seeds:
            return [], {}, False
        reached, truncated = self.walk(seeds, depth, SEMANTIC)
        exact = set(anchors)
        if query in self.nodes:
            exact.add(query)
        conflict = {i for i, (_, path) in reached.items()
                    if any(e["predicate"] in {"contradicts", "violates", "supersedes"} for e in path)}
        critical = {i for i in reached if self.nodes[i]["kind"] in CRITICAL}
        preferred = {i for i in reached if self.nodes[i]["kind"] in INTENTS[intent]}
        order = sorted(reached, key=lambda i: (i not in exact, i not in conflict,
                                               i not in critical, i not in preferred,
                                               reached[i][0], i))
        return order, reached, truncated

    def render(self, ids: list[str], *, detail: str = "summary", limit: int = 5,
               budget: int = 12000, paths: dict | None = None, cut: bool = False,
               known: set[str] | None = None) -> dict:
        """Bound UTF-8 JSON bytes of the entire response. Never truncate an assertion."""
        import json
        require(detail in {"identity", "summary", "full", "evidence"}, "Invalid detail")
        require(1 <= limit <= 50 and 512 <= budget <= 64000, "Invalid output budget")
        require(len(ids) == len(set(ids)) and all(i in self.nodes for i in ids), "Invalid result identities")
        known = known or set()
        result = {"status": "partial", "project": self.corpus["project"],
                  "coverage": self.corpus["coverage"], "results": [], "omitted": 0,
                  "unchanged": 0, "traversal_cut": cut, "budget_unit": "utf8-json-bytes"}
        def size(obj):
            return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        for i in ids:
            n = self.nodes[i]
            fingerprint = self.fingerprint(i)
            if fingerprint in known:
                result["unchanged"] += 1
                continue
            if len(result["results"]) >= limit:
                result["omitted"] += 1
                continue
            item = {k: n[k] for k in ("id", "level", "kind", "title")}
            item["fingerprint"] = fingerprint
            item["claim_state"] = n.get("claim_state", "unknown")
            if "content_state" in n:
                item["content_state"] = n["content_state"]
            if detail != "identity":
                item["summary"] = n["summary"]
                item["contexts"] = n.get("contexts", [])
            if detail == "full" and n.get("content_state") != "metadata-only":
                item["body"] = n.get("body", "")
            if detail in {"full", "evidence"}:
                item["sources"] = n.get("sources", [])
            if paths and i in paths:
                item["path"] = paths[i][1]
            # Structured affordances are data, not executable shell.
            item["_links"] = [{"action": "trace", "id": i}, {"action": "expand", "id": i}]
            if n.get("content_state") == "metadata-only":
                for source in n.get("sources", []):
                    if source["provider"] == "backlog" and i == "doc:" + source["locator"]:
                        item["_links"].insert(0, {"action": "capture-doc", "id": source["locator"]})
                        break
            else:
                item["_links"].insert(0, {"action": "get", "id": i, "detail": "full"})
                if n.get("body"):
                    item["_links"].append({"action": "sections", "id": i})
            if any(e["predicate"] == "contains" for e in self.out[i]):
                item["_links"].append({"action": "zoom-in", "id": i})
            if any(e["predicate"] == "contains" for e in self.inc[i]):
                item["_links"].append({"action": "zoom-out", "id": i})
            result["results"].append(item)
            if size(result) > budget - 64:
                result["results"].pop()
                result["omitted"] += 1
        result["status"] = ("unknown" if not ids else
                            "partial" if cut or result["omitted"] or self.corpus["coverage"] == "partial"
                            else "returned")
        require(size(result) <= budget, "Envelope exceeds budget")
        return result
