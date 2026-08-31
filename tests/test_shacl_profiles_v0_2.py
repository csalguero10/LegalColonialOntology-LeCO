from pathlib import Path
import sys
import yaml
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, OWL, SKOS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from leco_normalization import normalize_office, office_type_local_name  # noqa: E402

SH = Namespace("http://www.w3.org/ns/shacl#")
LECO = Namespace("https://w3id.org/leco/ontology#")
LECOSH = Namespace("https://w3id.org/leco/shapes#")
LECOQ = Namespace("https://w3id.org/leco/shapes/quality#")


def graph(name):
    return Graph().parse(ROOT / "shapes" / name, format="turtle")


def property_node(g, shape, path):
    for node in g.objects(shape, SH.property):
        if g.value(node, SH.path) == path:
            return node
    return None


def test_profiles_parse_and_are_shacl_sparql_wellformed():
    for name in ("LeCO_shapes.ttl", "LeCO_quality_shapes.ttl", "LeCO_shapes_strict.ttl"):
        g = graph(name)
        assert len(g) > 0
        for select in g.objects(None, SH.select):
            text = str(select).upper()
            assert "VALUES" not in text
            assert "MINUS" not in text
            assert "SERVICE" not in text


def test_core_relaxes_completeness_but_preserves_type_constraints():
    core = graph("LeCO_shapes.ttl")
    strict = graph("LeCO_shapes_strict.ttl")
    checks = [
        (LECOSH.JurisdictionalActShape, LECO.withinJurisdiction),
        (LECOSH.AppealShape, LECO.appealsAgainst),
        (LECOSH.AppealShape, LECO.beforeAuthority),
        (LECOSH.LegalDecisionShape, LECO.decidedBy),
        (LECOSH.SanctionShape, LECO.sanctions),
        (LECOSH.AppointmentShape, LECO.appointsPerson),
        (LECOSH.AppointmentShape, LECO.appointsToOffice),
        (LECOSH.HistoricalConceptUseShape, LECO.conceptUseJurisdiction),
        (LECOSH.GrantOfPowerShape, LECO.createsRepresentation),
        (LECOSH.RepartimientoActShape, LECO.resultsInLegalArrangement),
    ]
    for shape, path in checks:
        c = property_node(core, shape, path)
        s = property_node(strict, shape, path)
        assert s is not None and strict.value(s, SH.minCount) == Literal(1)
        assert c is not None
        assert core.value(c, SH.minCount) is None
    # Generic participant completeness OR is absent from CORE, present in STRICT.
    assert core.value(LECOSH.JurisdictionalActShape, SH["or"]) is None
    assert strict.value(LECOSH.JurisdictionalActShape, SH["or"]) is not None
    # investigates has no type/maxCount constraint to preserve, so CORE removes it entirely.
    assert property_node(core, LECOSH.InvestigationShape, LECO.investigates) is None


def test_quality_profile_marks_the_twelve_corpus_patterns_as_warnings():
    q = graph("LeCO_quality_shapes.ttl")
    expected_paths = {
        LECO.withinJurisdiction,
        LECO.decidedBy,
        LECO.sanctions,
        LECO.createsRepresentation,
        LECO.appointsPerson,
        LECO.appointsToOffice,
        LECO.resultsInLegalArrangement,
        LECO.appealsAgainst,
        LECO.beforeAuthority,
        LECO.conceptUseJurisdiction,
        LECO.investigates,
    }
    found = set()
    for pnode in q.objects(None, SH.property):
        if q.value(pnode, SH.minCount) == Literal(1):
            path = q.value(pnode, SH.path)
            if isinstance(path, URIRef):
                found.add(path)
                if path in expected_paths:
                    assert q.value(pnode, SH.severity) == SH.Warning
    assert expected_paths <= found
    participant_shape = LECOQ.JurisdictionalActParticipantQualityShape
    assert q.value(participant_shape, SH["or"]) is not None
    assert q.value(participant_shape, SH.severity) == SH.Warning


def test_mapping_authorizes_appointment_and_double_nature_properties():
    mapping = yaml.safe_load((ROOT / "mapping" / "tei_to_leco.yaml").read_text(encoding="utf-8"))
    direct = set(mapping["controlled_types"]["relation"]["direct_properties"])
    assert {"appointsPerson", "appointsToOffice", "createsRepresentation", "resultsInLegalArrangement"} <= direct


def test_office_normalization_decisions_from_corpus():
    expected = {
        "Alcaldes Ordinarios": "MayorOfficeType",
        "Regidores": "RegidorOfficeType",
        "diputados": "DeputyOfficeType",
        "Alquacil": "BailiffOfficeType",
        "Alquacil Mayor": "BailiffOfficeType",
        "Procuradores": "ProcuradorOfficeType",
        "Procuradores Generales": "ProcuradorOfficeType",
        "cardenal": "CardinalOfficeType",
        "Cap": "CaptainOfficeType",
        "Juez de Comisión": "JudgeOfficeType",
        "Juez": "JudgeOfficeType",
        "contador": "AccountantOfficeType",
    }
    for surface, target in expected.items():
        assert office_type_local_name(surface) == target
    assert normalize_office("Alquacil")["normalization_kind"] == "transcription_error"
    assert normalize_office("Cap")["normalization_kind"] == "abbreviation"
    assert normalize_office("Juez de Comisión")["normalization_kind"] == "broader_normalization"


def test_ontology_documents_normalization_without_erasing_source_forms():
    ont = Graph().parse(ROOT / "ontology" / "LeCO.ttl", format="turtle")
    assert (LECO.MayorOfficeType, SKOS.altLabel, Literal("Alcalde Ordinario", lang="es")) in ont
    assert (LECO.OrdinaryMayorOfficeType, OWL.deprecated, Literal(True)) in ont
    assert (LECO.BailiffOfficeType, SKOS.prefLabel, Literal("Alguacil", lang="es")) in ont
    assert (LECO.BailiffOfficeType, SKOS.hiddenLabel, Literal("Alquacil", lang="es")) in ont
    assert (LECO.ChiefBailiffOfficeType, OWL.deprecated, Literal(True)) in ont
    assert (LECO.ProcuradorGeneralOfficeType, OWL.deprecated, Literal(True)) in ont
    assert (LECO.PublicNotaryOfficeType, OWL.deprecated, Literal(True)) in ont
    assert (LECO.CaptainOfficeType, SKOS.hiddenLabel, Literal("Cap", lang="es")) in ont
    assert (LECO.CommissionJudgeOfficeType, OWL.deprecated, Literal(True)) in ont
