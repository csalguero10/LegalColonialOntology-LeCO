from pathlib import Path

from rdflib import Graph, Namespace, RDF, Literal

ROOT = Path(__file__).resolve().parents[1]
SH = Namespace("http://www.w3.org/ns/shacl#")
LECO = Namespace("https://w3id.org/leco/ontology#")


def test_concept_use_time_is_not_required_by_core_profile():
    g = Graph().parse(ROOT / "shapes" / "LeCO_shapes.ttl", format="turtle")
    # No CORE property shape for conceptUseTime may have sh:minCount 1.
    for prop_shape in set(g.subjects(SH.path, LECO.conceptUseTime)):
        assert (prop_shape, SH.minCount, Literal(1)) not in g


def test_concept_use_time_is_quality_warning():
    g = Graph().parse(ROOT / "shapes" / "LeCO_quality_shapes.ttl", format="turtle")
    matches = []
    for prop_shape in set(g.subjects(SH.path, LECO.conceptUseTime)):
        if (prop_shape, SH.minCount, Literal(1)) in g:
            matches.append(prop_shape)
    assert matches, "QUALITY debe recomendar conceptUseTime"
    assert any((ps, SH.severity, SH.Warning) in g for ps in matches)


def test_strict_still_requires_concept_use_time():
    g = Graph().parse(ROOT / "shapes" / "LeCO_shapes_strict.ttl", format="turtle")
    assert any(
        (ps, SH.minCount, Literal(1)) in g
        for ps in set(g.subjects(SH.path, LECO.conceptUseTime))
    )
