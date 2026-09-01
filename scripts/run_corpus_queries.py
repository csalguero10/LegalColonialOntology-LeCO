#!/usr/bin/env python3
"""Run SPARQL queries against a LeCO corpus Turtle graph."""
from __future__ import annotations

import argparse
from pathlib import Path

from rdflib import Graph


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--graph",
        type=Path,
        default=root / "build" / "corpus" / "corpus_graph.ttl",
    )
    parser.add_argument(
        "--query-dir",
        type=Path,
        default=root / "queries" / "corpus",
    )
    parser.add_argument("--limit-print", type=int, default=50)
    args = parser.parse_args()

    graph = Graph().parse(args.graph, format="turtle")
    queries = sorted(args.query_dir.glob("*.rq"))
    if not queries:
        raise SystemExit(f"No hay consultas .rq en {args.query_dir}")

    print(f"Corpus graph: {len(graph):,} triples")
    for path in queries:
        print(f"\n=== {path.stem} ===")
        result = graph.query(path.read_text(encoding="utf-8"))
        rows = list(result)
        print(f"Rows: {len(rows)}")
        for row in rows[: args.limit_print]:
            print(" | ".join("" if v is None else str(v) for v in row))
        if len(rows) > args.limit_print:
            print(f"... {len(rows) - args.limit_print} row(s) more")


if __name__ == "__main__":
    main()
