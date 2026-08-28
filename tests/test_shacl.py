from pathlib import Path
import pytest
from rdflib import Graph

pyshacl = pytest.importorskip("pyshacl")
from pyshacl import validate

ROOT = Path(__file__).resolve().parents[1]


def test_pineda_example_conforms_to_leco_shapes():
    data = Graph().parse(ROOT / "data" / "pineda_example.ttl", format="turtle")
    ontology = Graph().parse(ROOT / "ontology" / "LeCO.ttl", format="turtle")
    shapes = Graph().parse(ROOT / "shapes" / "LeCO_shapes.ttl", format="turtle")

    conforms, _, report_text = validate(
        data_graph=data,
        shacl_graph=shapes,
        ont_graph=ontology,
        inference="rdfs",
        advanced=True,
        meta_shacl=True,
        abort_on_first=False,
    )
    assert conforms, report_text
