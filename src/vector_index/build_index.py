#!/usr/bin/env python3
"""
build_index.py

Loads entities.jsonl / edges.jsonl (produced by extract.mjs) plus the cloned
source in data/raw/, and builds a persistent ChromaDB collection for semantic
search over code entities (Files / Components / Hooks / Screens).

Each entity becomes one document:
  - text: type/name/file + a graph-context sentence (renders/calls/depends_on/
    defines, both directions) + the actual source snippet (startLine..endLine)
  - metadata: id/type/name/file/kindGuess/startLine/endLine/snippet, so answers
    can cite "file path + code snippet" directly from a query hit.

Uses ChromaDB's default local embedding function (all-MiniLM-L6-v2 via ONNX)
- no API key, no network calls at query time.

Usage:
  python3 build_index.py \
      --entities data/processed/entities.jsonl \
      --edges data/processed/edges.jsonl \
      --raw-dir data/raw \
      --chroma-dir data/processed/chroma \
      --collection codeiq_entities
"""
import argparse
import json
from pathlib import Path

import chromadb

RELEVANT_EDGE_TYPES = ("renders", "calls", "depends_on", "defines")
MAX_SNIPPET_LINES = 60
BATCH_SIZE = 500


def load_entities(path: Path) -> dict:
    entities = {}
    with open(path) as f:
        for line in f:
            e = json.loads(line)
            entities[e["id"]] = e
    return entities


def load_adjacency(path: Path) -> tuple[dict, dict]:
    """Returns (outgoing, incoming): id -> edge_type -> [other_id, ...]"""
    outgoing, incoming = {}, {}
    with open(path) as f:
        for line in f:
            e = json.loads(line)
            src, dst, etype = e["from"], e["to"], e["type"]
            if etype not in RELEVANT_EDGE_TYPES:
                continue
            outgoing.setdefault(src, {}).setdefault(etype, []).append(dst)
            incoming.setdefault(dst, {}).setdefault(etype, []).append(src)
    return outgoing, incoming


def pretty(node_id: str, entities: dict) -> str:
    if node_id in entities:
        return entities[node_id]["name"]
    if node_id.startswith("external:"):
        return f"{node_id.split('#')[-1]} (external)"
    if "#" in node_id:
        return node_id.split("#")[-1]
    return node_id


def describe(entity_id: str, entities: dict, outgoing: dict, incoming: dict, cap=8) -> str:
    """Human-readable graph-context sentence for one entity."""
    lines = []

    def fmt(ids, label):
        names = [pretty(i, entities) for i in ids[:cap]]
        extra = f" (+{len(ids) - cap} more)" if len(ids) > cap else ""
        lines.append(f"{label}: {', '.join(names)}{extra}")

    out = outgoing.get(entity_id, {})
    inc = incoming.get(entity_id, {})
    if out.get("renders"):
        fmt(out["renders"], "Renders")
    if out.get("calls"):
        fmt(out["calls"], "Calls")
    if out.get("depends_on"):
        fmt(out["depends_on"], "Depends on")
    if out.get("defines"):
        fmt(out["defines"], "Defines")
    if inc.get("renders"):
        fmt(inc["renders"], "Rendered by")
    if inc.get("calls"):
        fmt(inc["calls"], "Called by")
    if inc.get("depends_on"):
        fmt(inc["depends_on"], "Depended on by")

    return "\n".join(lines)


def read_snippet(raw_dir: Path, file: str, start: int, end: int) -> str:
    path = raw_dir / file
    if not path.exists() or not start or not end:
        return ""
    try:
        all_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    lo, hi = max(1, start), min(len(all_lines), end)
    snippet_lines = all_lines[lo - 1 : hi]
    if len(snippet_lines) > MAX_SNIPPET_LINES:
        snippet_lines = snippet_lines[:MAX_SNIPPET_LINES] + ["# ... truncated ..."]
    return "\n".join(snippet_lines)


def build_documents(entities: dict, outgoing: dict, incoming: dict, raw_dir: Path):
    ids, documents, metadatas = [], [], []

    for eid, e in entities.items():
        etype, name, file = e["type"], e["name"], e.get("file", e.get("path", ""))
        start, end = e.get("startLine"), e.get("endLine")
        kind = e.get("kindGuess", "")

        context = describe(eid, entities, outgoing, incoming)
        snippet = read_snippet(raw_dir, file, start, end) if file else ""

        header = f"{etype} {name}"
        header += f" ({kind})" if kind else ""
        header += f" in {file}" if file else ""

        text = header
        if context:
            text += "\n" + context
        if snippet:
            text += "\n\nSource:\n" + snippet

        ids.append(eid)
        documents.append(text)
        metadatas.append(
            {
                "id": eid,
                "type": etype,
                "name": name,
                "file": file or "",
                "kindGuess": kind,
                "startLine": start or 0,
                "endLine": end or 0,
                "snippet": snippet[:2000],  # keep metadata bounded
            }
        )

    return ids, documents, metadatas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entities", default="data/processed/entities.jsonl")
    ap.add_argument("--edges", default="data/processed/edges.jsonl")
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--chroma-dir", default="data/processed/chroma")
    ap.add_argument("--collection", default="codeiq_entities")
    args = ap.parse_args()

    entities = load_entities(Path(args.entities))
    outgoing, incoming = load_adjacency(Path(args.edges))
    print(f"Loaded {len(entities)} entities")

    ids, documents, metadatas = build_documents(entities, outgoing, incoming, Path(args.raw_dir))
    print(f"Built {len(documents)} documents")

    client = chromadb.PersistentClient(path=args.chroma_dir)
    client.delete_collection(args.collection) if args.collection in [
        c.name for c in client.list_collections()
    ] else None
    collection = client.create_collection(args.collection)

    for i in range(0, len(ids), BATCH_SIZE):
        collection.add(
            ids=ids[i : i + BATCH_SIZE],
            documents=documents[i : i + BATCH_SIZE],
            metadatas=metadatas[i : i + BATCH_SIZE],
        )
        print(f"  indexed {min(i + BATCH_SIZE, len(ids))}/{len(ids)}")

    print(f"\nPersisted collection '{args.collection}' -> {args.chroma_dir}")
    print(f"Total docs in collection: {collection.count()}")


if __name__ == "__main__":
    main()
