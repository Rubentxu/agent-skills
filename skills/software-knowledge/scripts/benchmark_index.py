#!/usr/bin/env python3
"""Reproducible synthetic comparison: fresh memory vs cold/warm incremental index."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import tempfile
import time
import tracemalloc

from cache_index import indexed
from model import make_corpus, node, require
from retrieval import Navigator


def fixture(size: int):
    nodes = [node("profile", "profile", "Example runtime", "Synthetic project", level="L3")]
    edges = []
    for i in range(size):
        identity = f"atom-{i:06}"
        text = ("Common runtime words describing a deterministic example. " * 8
                + f" unique_marker_{i}.\n\n# Guarantees\n\nSynthetic evidence and known decisions.")
        nodes.append(node(identity, "invariant", f"Guarantee {i}", "A synthetic guarantee",
                          contexts=["runtime"], body=text))
        edges.append({"from": "profile", "predicate": "contains", "to": identity})
    return make_corpus("benchmark", nodes, edges)


def measure(fn, repeat):
    times = []
    peaks = []
    result = None
    for _ in range(repeat):
        tracemalloc.start()
        start = time.perf_counter()
        try:
            result = fn()
            times.append((time.perf_counter() - start) * 1000)
            peaks.append(tracemalloc.get_traced_memory()[1])
        finally:
            tracemalloc.stop()
    return {"median_ms": round(statistics.median(times), 3),
            "median_python_peak_bytes": int(statistics.median(peaks)), "repeat": repeat}, result


def benchmark(size: int, repeat: int) -> dict:
    require(10 <= size <= 5000 and 1 <= repeat <= 10, "Invalid benchmark size/repeat")
    corpus = fixture(size)
    query = f"unique_marker_{size // 2}"
    expected = f"atom-{size // 2:06}"
    # The synthetic corpus is outside every checkout; the index is under private cache home.
    with tempfile.TemporaryDirectory(prefix="knowledge-benchmark-") as d:
        source = Path(d) / "corpus.json"
        source.write_text(json.dumps(corpus), encoding="utf-8")
        def memory():
            # Include decoding and validation in the baseline, as the normal CLI does.
            nav = Navigator(json.loads(source.read_bytes()))
            return nav.render(nav.search(query))
        def cached():
            with indexed(source, "snapshot", "benchmark") as (nav, stats):
                return nav.render(nav.search(query)), stats

        variants = {}
        variants["memory"], result = measure(memory, repeat)
        assert result["results"][0]["id"] == expected
        variants["cold"], (result, stats) = measure(cached, 1)
        assert result["results"][0]["id"] == expected and stats["nodes_reindexed"] == size + 1
        variants["cold"]["nodes_reindexed"] = stats["nodes_reindexed"]
        variants["warm"], (result, stats) = measure(cached, repeat)
        assert result["results"][0]["id"] == expected and stats["reused"]
        variants["warm"]["nodes_reindexed"] = stats["nodes_reindexed"]
        corpus["nodes"][1]["body"] += "\n\nChanged single atom."
        source.write_text(json.dumps(corpus), encoding="utf-8")
        variants["one_change"], (result, stats) = measure(cached, 1)
        assert result["results"][0]["id"] == expected and stats["nodes_reindexed"] == 1
        variants["one_change"]["nodes_reindexed"] = stats["nodes_reindexed"]
        cache = Path(stats["cache_path"])
        storage = cache.stat().st_size
        # Only remove the index created by this synthetic fixture; never touch user data.
        cache.unlink()
    return {"status": "measured", "synthetic_atoms": size, "query": query,
            "index_bytes": storage, "variants": variants,
            "warning": "Python tracemalloc excludes native SQLite allocation and filesystem cache; timing includes tracing overhead. Not a production SLA or agent-token benchmark."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--size", type=int, default=1000)
    p.add_argument("--repeat", type=int, default=3)
    args = p.parse_args()
    print(json.dumps(benchmark(args.size, args.repeat), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
