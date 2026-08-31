from argparse import ArgumentParser
from pathlib import Path

from rdflib import Graph
from pyshacl import validate
from pyshacl.errors import ValidationFailure

ROOT = Path(__file__).resolve().parents[1]


def parse_args():
    parser = ArgumentParser(description="Validate LeCO RDF data against SHACL shapes.")
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "pineda_example.ttl")
    parser.add_argument("--ontology", type=Path, default=ROOT / "ontology" / "LeCO.ttl")
    parser.add_argument("--shapes", type=Path, default=ROOT / "shapes" / "LeCO_shapes.ttl")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "shacl_report.ttl")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = Graph().parse(args.ontology, format="turtle")
    data.parse(args.data, format="turtle")
    shapes = Graph().parse(args.shapes, format="turtle")

    conforms, report_graph, report_text = validate(
        data_graph=data,
        shacl_graph=shapes,
        inference="rdfs",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
        advanced=True,
        meta_shacl=True,
    )

    # A ValidationFailure means the SHACL shapes graph itself is ill-formed.
    # In that case pySHACL returns a ValidationFailure object instead of an
    # rdflib.Graph, so attempting .serialize() would raise AttributeError.
    if isinstance(report_graph, ValidationFailure):
        print("SHACL validation could not be executed because the shapes graph is invalid.")
        print(f"Reason: {report_graph.message}")
        print(report_text)
        return 2

    args.report.parent.mkdir(parents=True, exist_ok=True)
    report_graph.serialize(destination=args.report, format="turtle")

    print(report_text)
    print(f"Reporte RDF: {args.report}")
    return 0 if conforms else 1


if __name__ == "__main__":
    raise SystemExit(main())
