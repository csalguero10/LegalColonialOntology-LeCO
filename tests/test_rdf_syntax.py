from pathlib import Path
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]


def test_turtle_files_parse():
    paths = [
        ROOT / "ontology" / "LeCO.ttl",
        ROOT / "shapes" / "LeCO_shapes.ttl",
        ROOT / "data" / "pineda_example.ttl",
    ]
    for path in paths:
        graph = Graph()
        graph.parse(path, format="turtle")
        assert len(graph) > 0, path
