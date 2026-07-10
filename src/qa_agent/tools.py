#!/usr/bin/env python3
"""
tools.py

Two retrieval tools that complement search_code() (src/vector_index/query_index.py):
  - find_entity_by_id_or_name: exact/near-exact identifier lookup, for when a
    question names a specific entity and embedding similarity risks returning
    a near-miss instead (e.g. two different `useSessionId` hooks exist, in
    session.ts and session.web.ts).
  - get_related_entities: uncapped graph traversal for one entity, for when a
    question needs more of an entity's relationships than the capped preview
    (8 names per relation type) baked into search_code()'s graph_context.

Both reuse load_entities()/load_adjacency() from src/vector_index/build_index.py
rather than reloading entities.jsonl/edges.jsonl with new logic, and return
hits shaped like search_code()'s so all three tools' outputs can be treated
uniformly as "sources" by the agent.

Runnable directly for manual sanity checks:
  python3 tools.py find "useSessionId"
  python3 tools.py related "src/App.tsx#InnerApp" --edge-type calls --direction out
"""
import argparse
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.vector_index.build_index import load_entities, load_adjacency, pretty  # noqa: E402

DEFAULT_ENTITIES_PATH = "data/processed/entities.jsonl"
DEFAULT_EDGES_PATH = "data/processed/edges.jsonl"


@lru_cache(maxsize=None)
def _get_entities(entities_path: str = DEFAULT_ENTITIES_PATH) -> dict:
    return load_entities(Path(entities_path))


@lru_cache(maxsize=None)
def _get_adjacency(edges_path: str = DEFAULT_EDGES_PATH) -> tuple:
    return load_adjacency(Path(edges_path))


def _to_hit(entity_id: str, entities: dict, extra: dict | None = None) -> dict:
    e = entities.get(entity_id)
    hit = {
        "id": entity_id,
        "type": e["type"] if e else ("External" if entity_id.startswith("external:") else "Unknown"),
        "name": e["name"] if e else pretty(entity_id, entities),
        "file": (e.get("file", e.get("path", "")) if e else ""),
        "start_line": (e.get("startLine", 0) if e else 0),
        "end_line": (e.get("endLine", 0) if e else 0),
    }
    if extra:
        hit.update(extra)
    return hit


def find_entity_by_id_or_name(
    query: str,
    entity_type: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Look up a code entity by its exact id or name, without relying on semantic similarity.

    Use this when a question names a specific identifier directly (e.g. "what
    does useSessionApi do", "explain the BookmarksScreen component") -- exact
    lookup avoids search_code() returning a near-miss (embedding similarity
    can't reliably disambiguate identically-named entities in different files,
    e.g. useSessionId exists in both session.ts and session.web.ts). Tries an
    exact id match first, then an exact case-insensitive name match, then a
    substring match on name.

    Args:
        query: The entity id (e.g. "src/App.tsx#InnerApp") or name (e.g.
            "useSessionId", "BookmarksScreen") to look up.
        entity_type: Optionally restrict to one entity type -- one of
            "File", "Component", "Hook", "Screen". Omit to search all types.
        limit: Max number of matches to return (default 10).

    Returns:
        A list of up to `limit` dicts, ordered exact-name matches before
        substring matches, each with: id, type, name, file, start_line,
        end_line. Empty list if nothing matches.
    """
    entities = _get_entities()
    query_stripped = query.strip()
    query_lower = query_stripped.lower()

    if query_stripped in entities:
        e = entities[query_stripped]
        if not entity_type or e["type"] == entity_type:
            return [_to_hit(query_stripped, entities)]

    exact, partial = [], []
    for eid, e in entities.items():
        if entity_type and e["type"] != entity_type:
            continue
        name_lower = e["name"].lower()
        if name_lower == query_lower:
            exact.append(eid)
        elif query_lower in name_lower:
            partial.append(eid)

    matches = (exact + partial)[:limit]
    return [_to_hit(eid, entities) for eid in matches]


def get_related_entities(
    entity_id: str,
    edge_type: str | None = None,
    direction: str = "both",
    limit: int = 15,
) -> list[dict]:
    """Get an entity's graph relationships, uncapped, via real edges.jsonl traversal.

    Use this once you've already identified a specific entity id (e.g. from
    search_code() or find_entity_by_id_or_name()) and need more of its
    relationships than the capped preview (8 names per relation type)
    search_code() already includes -- e.g. "who else calls this hook",
    "what does this component render", or one hop beyond a single semantic
    hit for a structural/impact question.

    Args:
        entity_id: The exact entity id to expand (e.g. "src/App.tsx#InnerApp").
        edge_type: Optionally restrict to one relation -- one of "renders",
            "calls", "depends_on", "defines". Omit to include all relations.
        direction: "out" (this entity -> others), "in" (others -> this
            entity), or "both" (default).
        limit: Max number of related entities to return (default 15).

    Returns:
        A list of up to `limit` dicts, each with: id, type, name, file,
        start_line, end_line, relation (the edge type), direction ("in" or
        "out"). Empty list if the entity has no matching edges.
    """
    entities = _get_entities()
    outgoing, incoming = _get_adjacency()

    results = []

    def collect(adjacency: dict, rel_direction: str):
        for rel_type, other_ids in adjacency.get(entity_id, {}).items():
            if edge_type and rel_type != edge_type:
                continue
            for other_id in other_ids:
                results.append(_to_hit(other_id, entities, {"relation": rel_type, "direction": rel_direction}))

    if direction in ("out", "both"):
        collect(outgoing, "out")
    if direction in ("in", "both"):
        collect(incoming, "in")

    return results[:limit]


def main():
    ap = argparse.ArgumentParser(description="Sanity-check the qa_agent lookup/traversal tools.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    find_ap = sub.add_parser("find", help="find_entity_by_id_or_name")
    find_ap.add_argument("query")
    find_ap.add_argument("--type", dest="entity_type")
    find_ap.add_argument("--limit", type=int, default=10)

    rel_ap = sub.add_parser("related", help="get_related_entities")
    rel_ap.add_argument("entity_id")
    rel_ap.add_argument("--edge-type", dest="edge_type")
    rel_ap.add_argument("--direction", default="both", choices=["in", "out", "both"])
    rel_ap.add_argument("--limit", type=int, default=15)

    args = ap.parse_args()

    if args.cmd == "find":
        hits = find_entity_by_id_or_name(args.query, entity_type=args.entity_type, limit=args.limit)
    else:
        hits = get_related_entities(args.entity_id, edge_type=args.edge_type, direction=args.direction, limit=args.limit)

    print(f"{len(hits)} result(s):\n")
    for h in hits:
        print(h)


if __name__ == "__main__":
    main()
