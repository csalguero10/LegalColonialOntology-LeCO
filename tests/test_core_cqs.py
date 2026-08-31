from pathlib import Path
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
QUERY_DIR = ROOT / "queries" / "core"

# El fixture de Pineda contiene evidencia suficiente para estas CQ.
EXPECTED_NONEMPTY = {
    "C01", "C02", "C03", "C04", "C05", "C06",
    "C07", "C08", "C09", "C10", "C11", "C12"
}


def graph():
    g = Graph()
    g.parse(ROOT / "ontology" / "LeCO.ttl", format="turtle")
    g.parse(ROOT / "data" / "pineda_example.ttl", format="turtle")
    return g


def test_all_12_core_queries_execute():
    g = graph()
    queries = sorted(QUERY_DIR.glob("C*.rq"))
    assert len(queries) == 12
    for path in queries:
        rows = list(g.query(path.read_text(encoding="utf-8")))
        cq = path.name[:3]
        if cq in EXPECTED_NONEMPTY:
            assert rows, f"{cq} debería devolver resultados para pineda_example.ttl"
