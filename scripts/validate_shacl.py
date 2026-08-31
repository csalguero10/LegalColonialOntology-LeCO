#!/usr/bin/env python3
"""Validate a LeCO RDF data graph with CORE, QUALITY or STRICT SHACL profiles."""
from __future__ import annotations

import argparse
from pathlib import Path
from rdflib import Graph


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = repo_root()
    ap = argparse.ArgumentParser(description="Validate LeCO RDF with a selected SHACL profile")
    ap.add_argument("--data", type=Path, default=root / "data" / "pineda_example.ttl")
    ap.add_argument("--ontology", type=Path, default=root / "ontology" / "LeCO.ttl")
    ap.add_argument("--profile", choices=("core", "quality", "strict"), default="core")
    ap.add_argument("--shapes", type=Path, default=None, help="Override the selected profile shapes")
    ap.add_argument("--report", type=Path, default=None)
    args = ap.parse_args()

    try:
        from pyshacl import validate
        from pyshacl.errors import ValidationFailure
    except ImportError as exc:
        raise SystemExit("pyshacl no está instalado. Ejecuta: pip install -r requirements.txt") from exc

    profile_paths = {
        "core": root / "shapes" / "LeCO_shapes.ttl",
        "quality": root / "shapes" / "LeCO_quality_shapes.ttl",
        "strict": root / "shapes" / "LeCO_shapes_strict.ttl",
    }
    shapes_path = args.shapes or profile_paths[args.profile]
    report_path = args.report or root / "build" / f"shacl_report_{args.profile}.ttl"

    data = Graph().parse(args.data, format="turtle")
    ontology = Graph().parse(args.ontology, format="turtle")
    shapes = Graph().parse(shapes_path, format="turtle")

    integrated = Graph()
    for prefix, ns in data.namespaces():
        integrated.bind(prefix, ns)
    for triple in ontology:
        integrated.add(triple)
    for triple in data:
        integrated.add(triple)

    conforms, report_graph, report_text = validate(
        data_graph=integrated,
        shacl_graph=shapes,
        inference="rdfs",
        advanced=True,
        meta_shacl=True,
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
    )

    print(f"SHACL profile: {args.profile}")
    print(report_text)

    if isinstance(report_graph, ValidationFailure):
        print("SHACL validation could not be executed because the shapes graph is invalid.")
        print(f"Reason: {report_graph.message}")
        return 2

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_graph.serialize(destination=report_path, format="turtle")
    print(f"Reporte RDF: {report_path}")
    return 0 if conforms else 1


if __name__ == "__main__":
    raise SystemExit(main())
