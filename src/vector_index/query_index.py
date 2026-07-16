#!/usr/bin/env python3
"""
query_index.py

Search interface over the ChromaDB collection built by build_index.py.
Exposes search_code() as a plain, importable function so it can be wrapped
as a tool for an LLM agent (e.g. LangChain's @tool decorator, or any
function-calling framework) -- it takes primitive args, has no side effects
beyond reading the index, and returns JSON-serializable structured results
instead of printing.

Also runnable directly as a CLI for manual sanity checks:
  python3 query_index.py "how does session restore work"
  python3 query_index.py "authentication hook" --n 10 --type Hook
  python3 query_index.py "authentication hook" --tag v2
"""
import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.clone_raw.clone_raw import TAG  # noqa: E402

DEFAULT_CHROMA_DIR = f"data/processed/{TAG}/chroma"
DEFAULT_COLLECTION = "codeiq_entities"


@lru_cache(maxsize=None)
def _get_collection(chroma_dir: str = DEFAULT_CHROMA_DIR, collection_name: str = DEFAULT_COLLECTION):
    client = chromadb.PersistentClient(path=chroma_dir)
    return client.get_collection(collection_name)


def search_code(
    query: str,
    n_results: int = 5,
    entity_type: str | None = None,
    tag: str | None = None,
    chroma_dir: str | None = None,
    collection_name: str = DEFAULT_COLLECTION,
) -> list[dict]:
    """Semantically search the CodeIQ knowledge graph for relevant code entities.

    Use this to answer questions about the codebase's structure -- e.g. "which
    hook manages session state", "what renders the login screen", "where is
    the bookmarks feature implemented". Each result is one indexed entity
    (a File, Component, Hook, or Screen) from the parsed React/React Native
    codebase, ranked by semantic similarity to the query. Every result already
    includes the entity's source snippet and file/line location, so results
    can be cited directly as evidence in an answer -- no separate file lookup
    is needed.

    Args:
        query: Natural-language description of what you're looking for
            (e.g. "authentication session hook", "who renders the feed screen").
        n_results: Max number of matches to return (default 5).
        entity_type: Optionally restrict to one entity type -- one of
            "File", "Component", "Hook", "Screen". Omit to search all types.
        tag: Optional repo tag; selects the index at data/processed/<tag>/chroma
            without needing to know the exact path. Ignored if chroma_dir is
            given explicitly.
        chroma_dir: Optional explicit path to the Chroma persistence dir.
            Overrides `tag` if both are given. Defaults to the index for TAG.
        collection_name: Chroma collection name (default "codeiq_entities").

    Returns:
        A list of up to n_results dicts, ordered by relevance (best first),
        each with:
          - id (str): unique entity id, e.g. "src/App.tsx#InnerApp"
          - type (str): "File" | "Component" | "Hook" | "Screen"
          - name (str): entity name, e.g. "useRequireAuth"
          - file (str): repo-relative path, e.g. "src/state/session/index.tsx"
          - start_line / end_line (int): source line range of the entity
          - snippet (str): the entity's actual source code
          - description (str): one-line LLM-generated summary of the entity's
            purpose, if entities_with_desc.jsonl was used to build the index
            (empty string otherwise)
          - graph_context (str): human-readable renders/calls/depends_on/
            defines relationships (both directions) for this entity
          - edges (list[dict]): structured version of graph_context, one dict
            per relationship -- direction ("out"|"in"), type, id, name,
            external (bool, target is a third-party package), lines (call/
            render-site line numbers). Use this instead of parsing
            graph_context when you need exact line numbers or want to filter
            to/from external packages.
          - relevance (float): similarity score in [0, 1], higher is more
            relevant (converted from Chroma's raw cosine distance)
    """
    if chroma_dir is None:
        chroma_dir = f"data/processed/{tag}/chroma" if tag else DEFAULT_CHROMA_DIR

    collection = _get_collection(chroma_dir, collection_name)
    where = {"type": entity_type} if entity_type else None

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        # doc = "<header>\n<graph_context>\n\nSource:\n<snippet>"; split back apart
        header_and_context, _, snippet = doc.partition("\n\nSource:\n")
        _, _, graph_context = header_and_context.partition("\n")

        hits.append(
            {
                "id": meta["id"],
                "type": meta["type"],
                "name": meta["name"],
                "file": meta["file"],
                "start_line": meta["startLine"],
                "end_line": meta["endLine"],
                "snippet": meta["snippet"] or snippet,
                "description": meta.get("description", ""),
                "graph_context": graph_context,
                "edges": json.loads(meta["edges"]) if meta.get("edges") else [],
                "relevance": round(max(0.0, 1.0 - dist / 2), 4),
            }
        )
    return hits


def main():
    ap = argparse.ArgumentParser(description="Sanity-check queries against the CodeIQ vector index.")
    ap.add_argument("query", help="natural-language search text")
    ap.add_argument("--n", type=int, default=5, help="number of results")
    ap.add_argument("--type", dest="entity_type", help="filter: File | Component | Hook | Screen")
    ap.add_argument("--tag", default=None, help="repo tag; selects data/processed/<tag>/chroma")
    ap.add_argument("--chroma-dir", dest="chroma_dir", default=None, help="explicit chroma dir, overrides --tag")
    ap.add_argument("--collection", dest="collection_name", default=DEFAULT_COLLECTION)
    args = ap.parse_args()

    chroma_dir = args.chroma_dir or (f"data/processed/{args.tag}/chroma" if args.tag else DEFAULT_CHROMA_DIR)

    collection = _get_collection(chroma_dir, args.collection_name)
    print(f"Collection '{args.collection_name}' @ {chroma_dir}: {collection.count()} docs\n")

    hits = search_code(
        args.query,
        n_results=args.n,
        entity_type=args.entity_type,
        chroma_dir=chroma_dir,
        collection_name=args.collection_name,
    )
    for i, hit in enumerate(hits):
        print(f"--- #{i+1}  relevance={hit['relevance']} ---")
        print(f"{hit['type']} {hit['name']}  ({hit['file']}:{hit['start_line']}-{hit['end_line']})")
        if hit["description"]:
            print(hit["description"])
        if hit["graph_context"]:
            print(hit["graph_context"])
        external = [e for e in hit["edges"] if e["external"]]
        if external:
            print(f"External calls: {', '.join(e['name'] + ' L' + ','.join(map(str, e['lines'])) for e in external[:5])}")
        print("Source:")
        print(hit["snippet"][:400])
        print()


if __name__ == "__main__":
    main()