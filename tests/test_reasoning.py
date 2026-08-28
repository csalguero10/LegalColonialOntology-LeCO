from pathlib import Path
import pytest
from rdflib import Graph, Namespace, RDF

pytest.importorskip("owlrl")
from owlrl import DeductiveClosure, OWLRL_Semantics

ROOT = Path(__file__).resolve().parents[1]
LECO = Namespace("https://w3id.org/leco/ontology#")
EX = Namespace("https://w3id.org/leco/test/")


def test_appeal_infers_procedural_and_jurisdictional_act():
    graph = Graph().parse(ROOT / "ontology" / "LeCO.ttl", format="turtle")
    graph.add((EX.testAppeal, RDF.type, LECO.Appeal))
    DeductiveClosure(OWLRL_Semantics).expand(graph)

    assert (EX.testAppeal, RDF.type, LECO.ProceduralAct) in graph
    assert (EX.testAppeal, RDF.type, LECO.JurisdictionalAct) in graph
