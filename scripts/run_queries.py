from argparse import ArgumentParser
from pathlib import Path
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
QUERY_DIR = ROOT / "queries" / "core"


def parse_args():
    parser = ArgumentParser(description="Run LeCO core competency questions as SPARQL queries.")
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "pineda_example.ttl")
    parser.add_argument("--ontology", type=Path, default=ROOT / "ontology" / "LeCO.ttl")
    parser.add_argument("--query", help="Run only one query by prefix, e.g. C06")
    return parser.parse_args()


def load_graph(ontology: Path, data: Path) -> Graph:
    graph = Graph()
    graph.parse(ontology, format="turtle")
    graph.parse(data, format="turtle")
    return graph


def render_result(path: Path, result) -> None:
    print(f"\n=== {path.stem} ===")
    rows = list(result)
    if not rows:
        print("(sin resultados en el dataset de ejemplo)")
        return
    for row in rows:
        print(" | ".join(str(value) for value in row))


def main() -> int:
    args = parse_args()
    graph = load_graph(args.ontology, args.data)
    paths = sorted(QUERY_DIR.glob("*.rq"))
    if args.query:
        prefix = args.query.upper()
        paths = [p for p in paths if p.name.upper().startswith(prefix)]
        if not paths:
            raise SystemExit(f"No se encontró una consulta con prefijo {prefix}")

    for path in paths:
        query = path.read_text(encoding="utf-8")
        render_result(path, graph.query(query))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
