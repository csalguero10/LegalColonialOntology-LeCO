from pathlib import Path
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "ontology": ROOT / "ontology" / "LeCO.ttl",
    "shapes": ROOT / "shapes" / "LeCO_shapes.ttl",
    "data": ROOT / "data" / "pineda_example.ttl",
}


def main() -> int:
    failed = False
    for label, path in FILES.items():
        graph = Graph()
        try:
            graph.parse(path, format="turtle")
            print(f"✓ {label:8} {path.relative_to(ROOT)}: {len(graph):,} triples")
        except Exception as exc:
            failed = True
            print(f"✗ {label:8} {path.relative_to(ROOT)}")
            print(f"  {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
