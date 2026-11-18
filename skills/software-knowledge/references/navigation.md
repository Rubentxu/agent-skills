# Active navigation

Start from exact ID or task anchor when available; L3 only for orientation, L2 when the scope is unclear, L1 for guarantees, L0 for verification. Python ranks candidates, traverses and bounds output; the host agent chooses when sufficient. Do not infer absence from an incomplete corpus or promote a ranking to truth.

Use search for IDs, aliases and weighted BM25; context additionally follows bounded explicit semantic links, prioritizes direct anchors, conflicts and critical knowledge, and uses RRF for lexical/intent ranked results. Both directions preserve original edge orientation in paths. Unknown anchors fail. No embeddings or training. No guessed edges. Inspect evidence before high-risk decisions.

Quick/normal/deep defaults: 3/5/8 returned items, 1/2/3 hops, 4000/12000/32000 UTF-8 JSON bytes per response. This is a deterministic byte limit, not a tokenizer. Recommended host query budgets 2/4/8 calls; host must enforce cumulative limits across independent invocations. If omitted, narrow scope or request a known ID; never silently truncate a claim. Fingerprints cover node fields and incident edges; pass --known only for content already in the current project's context, not after compaction. Snapshot is explicit full output, not a retrieval operation.

Navigation commands and exact syntax: [README](../README.md). The links in returned JSON are structured suggestions, not shell commands or permissions.
