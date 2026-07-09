#!/usr/bin/env python3
"""
query_index.py

Quick sanity-check CLI for the ChromaDB collection built by build_index.py.

Usage:
  python3 query_index.py "how does session restore work"
  python3 query_index.py "authentication hook" --n 10
  python3 query_index.py "session" --where type=Hook
"""
import argparse

import chromadb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="natural-language search text")
    ap.add_argument("--chroma-dir", default="data/processed/chroma")
    ap.add_argument("--collection", default="codeiq_entities")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--where", help="metadata filter, e.g. type=Hook")
    args = ap.parse_args()

    client = chromadb.PersistentClient(path=args.chroma_dir)
    collection = client.get_collection(args.collection)
    print(f"Collection '{args.collection}': {collection.count()} docs\n")

    where = None
    if args.where:
        key, val = args.where.split("=", 1)
        where = {key: val}

    results = collection.query(
        query_texts=[args.query],
        n_results=args.n,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    for i, (doc, meta, dist) in enumerate(
        zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
    ):
        print(f"--- #{i+1}  distance={dist:.4f} ---")
        print(f"{meta['type']} {meta['name']}  ({meta['file']}:{meta['startLine']}-{meta['endLine']})")
        print(doc[:400])
        print()


if __name__ == "__main__":
    main()
