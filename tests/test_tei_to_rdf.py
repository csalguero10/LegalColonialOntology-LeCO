from pathlib import Path
import shutil

import pytest
from rdflib import Graph
from rdflib.namespace import RDF

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pineda_mapping_profile.xml"
MAPPING = ROOT / "mapping" / "tei_to_leco.yaml"

# Import the converter exactly as it is used from scripts/.
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from tei_to_rdf import (  # noqa: E402
    TEILeCOConverter, convert_one, LECO, RICO, CRM, FOAF
)


def _make_document(tmp_path: Path) -> Path:
    doc = tmp_path / "data" / "documents" / "cab-001-002"
    doc.mkdir(parents=True)
    shutil.copy(FIXTURE, doc / "tei.xml")
    return doc


def test_mapping_profile_generates_core_leco_graph(tmp_path):
    doc = _make_document(tmp_path)
    out = tmp_path / "build" / "rdf" / "cab-001-002.ttl"
    converter = TEILeCOConverter(MAPPING)
    report = convert_one(
        converter, doc, out, False,
        ROOT / "ontology" / "LeCO.ttl",
        ROOT / "shapes" / "LeCO_shapes.ttl",
        tmp_path / "build" / "shacl_reports" / "cab-001-002.ttl",
    )
    assert report.mode == "mapping-profile"
    assert out.exists()
    g = Graph().parse(out, format="turtle")

    base = "https://w3id.org/leco/data/co-ahrb-cab-001-d002/"
    from rdflib import URIRef
    record = URIRef(base + "record")
    pineda = URIRef(base + "p_pineda")
    appeal = URIRef(base + "ev_appeal")
    sanction = URIRef(base + "ev_sanction")
    audiencia = URIRef(base + "org_audiencia")
    part = URIRef(base + "rel_part_appeal")
    concept_use = URIRef(base + "rel_concept_real_service")
    argument = URIRef(base + "arg_breach")
    rule = URIRef(base + "rule_duty")

    assert (record, RDF.type, LECO.LegalDocument) in g
    assert (record, LECO.hasDocumentType, LECO.ActaCabildoDocumentType) in g
    assert (pineda, RDF.type, RICO.Person) in g
    assert (pineda, RDF.type, CRM.E21_Person) in g
    assert (pineda, RDF.type, FOAF.Person) in g
    assert (appeal, RDF.type, LECO.Appeal) in g
    assert (appeal, LECO.appealsAgainst, sanction) in g
    assert (appeal, LECO.beforeAuthority, audiencia) in g
    assert (appeal, LECO.hasParticipation, part) in g
    assert (part, LECO.participationActor, pineda) in g
    assert (part, LECO.participationRole, LECO.AppellantRole) in g
    assert (concept_use, LECO.conceptUsed, LECO.RealServiceConcept) in g
    assert list(g.objects(concept_use, LECO.conceptUseJurisdiction))
    assert list(g.objects(concept_use, LECO.conceptUseTime))
    assert (argument, LECO.argumentInvokesRule, rule) in g


def test_generated_graph_conforms_when_pyshacl_available(tmp_path):
    pytest.importorskip("pyshacl")
    if not (ROOT / "ontology" / "LeCO.ttl").exists() or not (ROOT / "shapes" / "LeCO_shapes.ttl").exists():
        pytest.skip("Ontology/shapes are not present in this update-only package")
    doc = _make_document(tmp_path)
    converter = TEILeCOConverter(MAPPING)
    report = convert_one(
        converter,
        doc,
        tmp_path / "build" / "rdf" / "cab-001-002.ttl",
        True,
        ROOT / "ontology" / "LeCO.ttl",
        ROOT / "shapes" / "LeCO_shapes.ttl",
        tmp_path / "build" / "shacl_reports" / "cab-001-002.ttl",
    )
    assert report.shacl_conforms is True


def test_real_corpus_path_if_present_is_accepted(tmp_path):
    real_doc = ROOT / "data" / "documents" / "cab-001-002"
    if not (real_doc / "tei.xml").exists():
        pytest.skip("Local corpus is not bundled with this update package")
    converter = TEILeCOConverter(MAPPING)
    report = convert_one(
        converter, real_doc,
        tmp_path / "cab-001-002.ttl", False,
        ROOT / "ontology" / "LeCO.ttl",
        ROOT / "shapes" / "LeCO_shapes.ttl",
        tmp_path / "report.ttl",
    )
    assert report.triples > 0
    assert report.mode in {"mapping-profile", "legacy-inline"}
