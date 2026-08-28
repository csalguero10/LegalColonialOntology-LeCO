from argparse import ArgumentParser
from pathlib import Path
from rdflib import Graph
from owlrl import DeductiveClosure, OWLRL_Semantics

ROOT = Path(__file__).resolve().parents[1]


def parse_args():
    parser = ArgumentParser(description="Run OWL-RL reasoning over LeCO ontology + data.")
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "pineda_example.ttl")
    parser.add_argument("--ontology", type=Path, default=ROOT / "ontology" / "LeCO.ttl")
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "reasoned_graph.ttl")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    graph = Graph()
    graph.parse(args.ontology, format="turtle")
    graph.parse(args.data, format="turtle")
    before = len(graph)

    DeductiveClosure(OWLRL_Semantics).expand(graph)
    after = len(graph)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(args.output, format="turtle")
    print(f"Triples antes del razonamiento:  {before:,}")
    print(f"Triples después del razonamiento: {after:,}")
    print(f"Grafo inferido: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
