#!/usr/bin/env python3
"""
build_graph.py

Loads entities.jsonl / edges.jsonl (produced by extract.mjs) into a networkx
MultiDiGraph, and shows a few example queries you'll actually want:
  - what renders/calls a given entity ("who uses useSession?")
  - what a screen depends on, transitively
  - most-depended-on components (fan-in) -> candidates for "core" nodes
  - export to GraphML for Gephi, or load straight into Neo4j

Usage:
  python3 build_graph.py ./out
"""
import json
import sys
import re
from pathlib import Path
from collections import Counter

import networkx as nx


def load_graph(out_dir: Path) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()

    entities = {}
    with open(out_dir / "entities.jsonl") as f:
        for line in f:
            e = json.loads(line)
            entities[e["id"]] = e
            g.add_node(e["id"], **e)

    with open(out_dir / "edges.jsonl") as f:
        for line in f:
            e = json.loads(line)
            src, dst, etype = e["from"], e["to"], e["type"]

            # If the target wasn't a declared entity (e.g. external lib, or a
            # file-level dependency), add a lightweight stub node so the graph
            # stays connected and queryable.
            if dst not in entities:
                if dst.startswith("external:"):
                    g.add_node(dst, type="External", name=dst.split("#")[-1])
                elif "#" in dst:
                    name = dst.split("#")[-1]
                    inferred = (
                        "Hook" if re.match(r"^use[A-Z0-9]", name) else "Component"
                    )
                    g.add_node(dst, type=inferred, name=name, file=dst.split("#")[0], inferred=True)
                else:
                    g.add_node(dst, type="File", name=dst, path=dst, inferred=True)

            g.add_edge(src, dst, type=etype, **{k: v for k, v in e.items() if k not in ("from", "to", "type")})

    return g


def who_uses(g: nx.MultiDiGraph, name_substring: str, edge_type: str | None = None):
    """Find entities whose id/name matches, then list incoming edges (who renders/calls them)."""
    matches = [n for n, d in g.nodes(data=True) if name_substring.lower() in d.get("name", "").lower()]
    for m in matches:
        preds = [
            (u, data["type"])
            for u, _, data in g.in_edges(m, data=True)
            if edge_type is None or data["type"] == edge_type
        ]
        print(f"\n{m}  ({g.nodes[m].get('type')})  <- used by {len(preds)} entities")
        for u, etype in preds[:15]:
            print(f"    {etype:10s} {u}")


def transitive_deps(g: nx.MultiDiGraph, entity_id: str, edge_type="depends_on", max_depth=3):
    """BFS over depends_on edges to see what a screen/component pulls in."""
    seen = {entity_id}
    frontier = [entity_id]
    for depth in range(max_depth):
        nxt = []
        for n in frontier:
            for _, v, data in g.out_edges(n, data=True):
                if data["type"] == edge_type and v not in seen:
                    seen.add(v)
                    nxt.append(v)
        if not nxt:
            break
        print(f"depth {depth+1}: {len(nxt)} new nodes")
        frontier = nxt
    return seen


def top_fan_in(g: nx.MultiDiGraph, entity_type: str, edge_type: str, top_n=15):
    """Most-used entities of a given type by a given edge type -> likely 'core' pieces."""
    counts = Counter()
    for u, v, data in g.edges(data=True):
        if data["type"] == edge_type and g.nodes.get(v, {}).get("type") == entity_type:
            counts[v] += 1
    print(f"\nTop {top_n} most-{edge_type} {entity_type} nodes:")
    for node, c in counts.most_common(top_n):
        print(f"  {c:4d}  {node}")


def main():
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "./out")
    g = load_graph(out_dir)
    print(f"Loaded graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")

    counts = Counter(d.get("type") for _, d in g.nodes(data=True))
    print("Node types:", dict(counts))

    # --- example queries ---
    top_fan_in(g, "Hook", "calls")
    top_fan_in(g, "Component", "renders")

    who_uses(g, "useSession", edge_type="calls")

    # --- export for Gephi / other tools ---
    export_path = out_dir / "graph.graphml"
    # GraphML doesn't like None/complex attrs - stringify everything first
    g2 = nx.MultiDiGraph()
    for n, d in g.nodes(data=True):
        g2.add_node(n, **{k: str(v) for k, v in d.items()})
    for u, v, d in g.edges(data=True):
        g2.add_edge(u, v, **{k: str(v) for k, v in d.items()})
    nx.write_graphml(g2, export_path)
    print(f"\nExported to {export_path} (open in Gephi)")


if __name__ == "__main__":
    main()
