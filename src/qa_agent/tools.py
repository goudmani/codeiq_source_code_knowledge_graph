#!/usr/bin/env python3
"""
tools.py

Three retrieval tools that complement search_code() (src/vector_index/query_index.py):
  - find_entity_by_id_or_name: exact/near-exact identifier lookup, for when a
    question names a specific entity and embedding similarity risks returning
    a near-miss instead (e.g. two different `useSessionId` hooks exist, in
    session.ts and session.web.ts).
  - get_related_entities: uncapped 1-hop graph traversal for one entity, for
    when a question needs more of an entity's direct relationships than the
    capped preview (8 names per relation type) baked into search_code()'s
    graph_context.
  - get_transitive_related_entities: multi-hop BFS (renders/calls/depends_on/
    defines, one direction) for "what breaks if X changes" / "what does X
    transitively pull in" questions -- returns the whole multi-hop closure in
    one tool call instead of the LLM chaining get_related_entities calls
    hop-by-hop against its tool-call budget. Reuses build_graph.py's
    load_graph()/transitive_deps() (networkx) rather than reimplementing BFS.

The first two reuse load_entities()/load_adjacency() from
src/vector_index/build_index.py rather than reloading entities.jsonl/
edges.jsonl with new logic. All three return hits shaped like search_code()'s
so all four tools' outputs can be treated uniformly as "sources" by the agent.

Runnable directly for manual sanity checks:
  python3 tools.py find "useSessionId"
  python3 tools.py related "src/App.tsx#InnerApp" --edge-type calls --direction out
  python3 tools.py transitive "src/App.tsx#InnerApp" --edge-type depends_on --direction out
"""
import argparse
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.vector_index.build_index import load_entities, load_adjacency, pretty  # noqa: E402
from src.build_graph.build_graph import load_graph, transitive_deps  # noqa: E402

DEFAULT_ENTITIES_PATH = "data/processed/entities_with_desc.jsonl"
DEFAULT_EDGES_PATH = "data/processed/edges.jsonl"
DEFAULT_PROCESSED_DIR = "data/processed"


@lru_cache(maxsize=None)
def _get_entities(entities_path: str = DEFAULT_ENTITIES_PATH) -> dict:
    return load_entities(Path(entities_path))


@lru_cache(maxsize=None)
def _get_adjacency(edges_path: str = DEFAULT_EDGES_PATH) -> tuple:
    return load_adjacency(Path(edges_path))


@lru_cache(maxsize=None)
def _get_graph(processed_dir: str = DEFAULT_PROCESSED_DIR):
    return load_graph(Path(processed_dir))


def _to_hit(entity_id: str, entities: dict, extra: dict | None = None) -> dict:
    e = entities.get(entity_id)
    hit = {
        "id": entity_id,
        "type": e["type"] if e else ("External" if entity_id.startswith("external:") else "Unknown"),
        "name": e["name"] if e else pretty(entity_id, entities),
        "file": (e.get("file", e.get("path", "")) if e else ""),
        "start_line": (e.get("startLine", 0) if e else 0),
        "end_line": (e.get("endLine", 0) if e else 0),
        "description": (e.get("description", "") if e else ""),
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
        end_line, description (one-line LLM-generated summary, empty string
        if none). Empty list if nothing matches.
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
        start_line, end_line, description (one-line LLM-generated summary,
        empty string if none), relation (the edge type), direction ("in" or
        "out"), external (bool, target is a third-party package), lines
        (call/render-site line numbers). Empty list if the entity has no
        matching edges.
    """
    entities = _get_entities()
    outgoing, incoming = _get_adjacency()

    results = []

    def collect(adjacency: dict, rel_direction: str):
        for rel_type, edge_infos in adjacency.get(entity_id, {}).items():
            if edge_type and rel_type != edge_type:
                continue
            for info in edge_infos:
                extra = {
                    "relation": rel_type,
                    "direction": rel_direction,
                    "external": info.get("external", False),
                    "lines": info.get("lines", []),
                }
                results.append(_to_hit(info["other"], entities, extra))

    if direction in ("out", "both"):
        collect(outgoing, "out")
    if direction in ("in", "both"):
        collect(incoming, "in")

    return results[:limit]


def get_transitive_related_entities(
    entity_id: str,
    edge_type: str = "depends_on",
    direction: str = "out",
    max_depth: int = 3,
    limit: int = 30,
) -> list[dict]:
    """Multi-hop BFS from one entity, along a single relation/direction, via networkx.

    Use this for structural/impact questions that need more than one hop --
    e.g. "what breaks if useSession changes" (direction="in" over "calls"/
    "depends_on": everything that transitively uses it), or "what does
    BookmarksScreen transitively depend on" (direction="out" over
    "depends_on"). Prefer this over repeated get_related_entities calls when
    the question is explicitly about transitive/indirect impact -- one call
    here returns the whole multi-hop closure, instead of the model spending
    its tool-call budget walking hop-by-hop.

    A single relation and direction are required (unlike get_related_entities'
    "both"/"all types") because a multi-hop walk only has a coherent meaning
    along one relation at a time -- mixing renders/calls/depends_on mid-walk
    doesn't correspond to a real question.

    Args:
        entity_id: The exact entity id to expand from (e.g. "src/App.tsx#InnerApp").
        edge_type: Which relation to walk -- one of "renders", "calls",
            "depends_on", "defines" (default "depends_on").
        direction: "out" (entity_id -> ..., default) or "in" (... -> entity_id).
        max_depth: Max hops to walk (default 3, matches build_graph.py's BFS default).
        limit: Max number of related entities to return (default 30), closest
            hops first.

    Returns:
        A list of up to `limit` dicts, each with: id, type, name, file,
        start_line, end_line, description, relation (the edge type),
        direction ("in" or "out"), depth (hop count from entity_id, >= 1).
        Empty list if the entity isn't in the graph or has no matching edges.
    """
    g = _get_graph()
    if entity_id not in g:
        return []

    depths = transitive_deps(g, entity_id, edge_type=edge_type, max_depth=max_depth, direction=direction)
    entities = _get_entities()

    ranked = sorted(depths.items(), key=lambda kv: kv[1])[:limit]
    return [
        _to_hit(other_id, entities, {"relation": edge_type, "direction": direction, "depth": depth})
        for other_id, depth in ranked
    ]


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

    trans_ap = sub.add_parser("transitive", help="get_transitive_related_entities")
    trans_ap.add_argument("entity_id")
    trans_ap.add_argument("--edge-type", dest="edge_type", default="depends_on")
    trans_ap.add_argument("--direction", default="out", choices=["in", "out"])
    trans_ap.add_argument("--max-depth", dest="max_depth", type=int, default=3)
    trans_ap.add_argument("--limit", type=int, default=30)

    args = ap.parse_args()

    if args.cmd == "find":
        hits = find_entity_by_id_or_name(args.query, entity_type=args.entity_type, limit=args.limit)
    elif args.cmd == "related":
        hits = get_related_entities(args.entity_id, edge_type=args.edge_type, direction=args.direction, limit=args.limit)
    else:
        hits = get_transitive_related_entities(
            args.entity_id, edge_type=args.edge_type, direction=args.direction,
            max_depth=args.max_depth, limit=args.limit,
        )

    print(f"{len(hits)} result(s):\n")
    for h in hits:
        print(h)


if __name__ == "__main__":
    main()
