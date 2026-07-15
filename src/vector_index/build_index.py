#!/usr/bin/env python3
"""
build_index.py

Loads entities.jsonl (or entities_with_desc.jsonl, the same entities annotated
with an LLM-generated one-line "description" field by
src/ts_extract/add_descriptions_stepped.py) / edges.jsonl (produced by
extract.mjs) plus the cloned source in data/raw/, and builds a persistent
ChromaDB collection for semantic search over code entities (Files /
Components / Hooks / Screens).

Each entity becomes one document:
  - text: type/name/file + one-line description (if present) + a graph-context
    sentence (renders/calls/depends_on/defines, both directions) + the actual
    source snippet (startLine..endLine)
  - metadata: id/type/name/file/kindGuess/startLine/endLine/description/
    snippet, so answers can cite "file path + code snippet" directly from a
    query hit, plus a JSON "edges" field (direction/type/id/name/external/
    lines per edge) for exact call/render-site lookups without re-parsing the
    graph-context sentence.

Uses ChromaDB's default local embedding function (all-MiniLM-L6-v2 via ONNX)
- no API key, no network calls at query time.

Usage:
  python3 build_index.py \
      --entities data/processed/<tag>/entities_with_desc.jsonl \
      --edges data/processed/<tag>/edges.jsonl \
      --raw-dir data/raw/<tag> \
      --chroma-dir data/processed/<tag>/chroma \
      --collection codeiq_entities
"""
import argparse
import json
import sys
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.clone_raw.clone_raw import TAG  # noqa: E402

RELEVANT_EDGE_TYPES = ("renders", "calls", "depends_on", "defines")
MAX_SNIPPET_LINES = 60
BATCH_SIZE = 500
CONTEXT_CAP = 8  # edges shown per label in the embedded context sentence
METADATA_EDGE_CAP = 50  # edges kept in structured metadata (not embedded)


def load_entities(path: Path) -> dict:
    entities = {}
    with open(path) as f:
        for line in f:
            e = json.loads(line)
            entities[e["id"]] = e
    return entities


def load_adjacency(path: Path) -> tuple[dict, dict]:
    """Returns (outgoing, incoming): id -> edge_type -> [edge_info, ...]

    Each edge_info is {"other": other_id, "external": bool, "lines": [int, ...]},
    carrying through the call/render-site line numbers and the external-package
    flag from extract.mjs so they can be surfaced later, not just the bare id.
    """
    outgoing, incoming = {}, {}
    with open(path) as f:
        for line in f:
            e = json.loads(line)
            src, dst, etype = e["from"], e["to"], e["type"]
            if etype not in RELEVANT_EDGE_TYPES:
                continue
            external = e.get("external", False)
            edge_lines = e.get("lines", [])
            outgoing.setdefault(src, {}).setdefault(etype, []).append(
                {"other": dst, "external": external, "lines": edge_lines}
            )
            incoming.setdefault(dst, {}).setdefault(etype, []).append(
                {"other": src, "external": external, "lines": edge_lines}
            )
    return outgoing, incoming


def pretty(node_id: str, entities: dict) -> str:
    if node_id in entities:
        return entities[node_id]["name"]
    if "#" in node_id:
        return node_id.split("#")[-1]
    return node_id


def fmt_edge(info: dict, entities: dict) -> str:
    """One edge as 'name (external, L12,34)' -- tags only appear when present."""
    name = pretty(info["other"], entities)
    tags = []
    if info.get("external"):
        tags.append("external")
    if info.get("lines"):
        line_str = ",".join(str(n) for n in info["lines"][:3])
        if len(info["lines"]) > 3:
            line_str += ",…"
        tags.append(f"L{line_str}")
    return f"{name} ({', '.join(tags)})" if tags else name


def describe(entity_id: str, entities: dict, outgoing: dict, incoming: dict, cap=CONTEXT_CAP) -> str:
    """Human-readable graph-context sentence for one entity."""
    lines = []

    def fmt(edge_infos, label):
        shown = [fmt_edge(info, entities) for info in edge_infos[:cap]]
        extra = f" (+{len(edge_infos) - cap} more)" if len(edge_infos) > cap else ""
        lines.append(f"{label}: {', '.join(shown)}{extra}")

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


def collect_edges_metadata(entity_id: str, entities: dict, outgoing: dict, incoming: dict, cap=METADATA_EDGE_CAP) -> list[dict]:
    """Structured (not embedded) edge list for this entity, for exact-match use
    by callers -- e.g. citing the precise line of a call/render site, or
    filtering to/from external packages -- without re-parsing graph_context text.
    """
    edges = []

    def add(edge_infos, direction, etype):
        for info in edge_infos[:cap]:
            edges.append(
                {
                    "direction": direction,  # "out" | "in"
                    "type": etype,
                    "id": info["other"],
                    "name": pretty(info["other"], entities),
                    "external": bool(info.get("external", False)),
                    "lines": info.get("lines", []),
                }
            )

    for etype, edge_infos in outgoing.get(entity_id, {}).items():
        add(edge_infos, "out", etype)
    for etype, edge_infos in incoming.get(entity_id, {}).items():
        add(edge_infos, "in", etype)

    return edges


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
        description = e.get("description") or ""

        context = describe(eid, entities, outgoing, incoming)
        edges = collect_edges_metadata(eid, entities, outgoing, incoming)
        snippet = read_snippet(raw_dir, file, start, end) if file else ""

        header = f"{etype} {name}"
        header += f" ({kind})" if kind else ""
        header += f" in {file}" if file else ""
        if description:
            header += f" -- {description}"

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
                "description": description,
                "snippet": snippet[:2000],  # keep metadata bounded
                "edges": json.dumps(edges),  # Chroma metadata is scalar-only; serialize
            }
        )

    return ids, documents, metadatas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entities", default=f"data/processed/{TAG}/entities_with_desc.jsonl")
    ap.add_argument("--edges", default=f"data/processed/{TAG}/edges.jsonl")
    ap.add_argument("--raw-dir", default=f"data/raw/{TAG}")
    ap.add_argument("--chroma-dir", default=f"data/processed/{TAG}/chroma")
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
