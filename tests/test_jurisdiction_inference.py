from pathlib import Path
import importlib.util
import sys

from rdflib import Graph, Namespace, RDF, DCTERMS

LECO = Namespace("https://w3id.org/leco/ontology#")
PROV = Namespace("http://www.w3.org/ns/prov#")


def load_converter(root: Path):
    path = root / "scripts" / "tei_to_rdf.py"
    spec = importlib.util.spec_from_file_location("tei_to_rdf_juris_tested", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(root / "scripts"))
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def write_fixture(path: Path, two_authorities: bool = False):
    second_org = """
      <org xml:id="org_audiencia" ana="https://w3id.org/leco/ontology#AudienciaType"><orgName>Real Audiencia</orgName></org>
    """ if two_authorities else ""
    second_juris = """
      <relation xml:id="jur_audiencia" type="territorialJurisdiction" active="#org_audiencia" passive="#place_tunja" source="#s1" subtype="explicit"/>
      <relation xml:id="rel_part_audiencia" type="objectProperty" name="hasParticipant" active="#event_oath" passive="#org_audiencia" source="#s1" subtype="explicit"/>
    """ if two_authorities else ""
    path.write_text(f'''<?xml version="1.0" encoding="utf-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0" xml:id="cab-test">
  <teiHeader>
    <fileDesc><titleStmt><title>Test</title></titleStmt><publicationStmt><p>x</p></publicationStmt><sourceDesc><p>x</p></sourceDesc></fileDesc>
    <profileDesc><creation><date when="1547-09-02">1547-09-02</date></creation></profileDesc>
  </teiHeader>
  <text><body><div xml:id="acta"><seg xml:id="s1">Los capitulares prestaron juramento.</seg></div></body></text>
  <standOff>
    <listOrg>
      <org xml:id="org_cabildo" ana="https://w3id.org/leco/ontology#CabildoType"><orgName>Cabildo</orgName></org>
      {second_org}
    </listOrg>
    <listPlace><place xml:id="place_tunja"><placeName>Tunja</placeName></place></listPlace>
    <listEvent><event xml:id="event_oath" ana="https://w3id.org/leco/ontology#Oath" corresp="#s1"><desc>juramento</desc></event></listEvent>
    <listRelation>
      <relation xml:id="jur_cabildo" type="territorialJurisdiction" active="#org_cabildo" passive="#place_tunja" source="#s1" subtype="explicit"/>
      <relation xml:id="rel_part_cabildo" type="objectProperty" name="hasParticipant" active="#event_oath" passive="#org_cabildo" source="#s1" subtype="explicit"/>
      {second_juris}
    </listRelation>
  </standOff>
</TEI>''', encoding="utf-8")


def convert(root: Path, tei: Path):
    mod = load_converter(root)
    conv = mod.TEILeCOConverter(root / "mapping" / "tei_to_leco.yaml")
    conv.load(tei)
    return conv.convert(), conv


def test_unique_participating_authority_derives_jurisdiction_with_provenance(tmp_path):
    root = Path(__file__).resolve().parents[1]
    tei = tmp_path / "cab-test.xml"
    write_fixture(tei)
    g, conv = convert(root, tei)

    act = conv.local_uri("event_oath")
    juris = conv.local_uri("jur_cabildo")
    assert (act, LECO.withinJurisdiction, juris) in g

    stmts = [s for s in g.subjects(RDF.subject, act)
             if (s, RDF.predicate, LECO.withinJurisdiction) in g and (s, RDF.object, juris) in g]
    assert len(stmts) == 1
    stmt = stmts[0]
    anns = list(g.subjects(LECO.annotationBody, stmt))
    assert len(anns) == 1
    ann = anns[0]
    assert (ann, LECO.annotationBasis, LECO.ContextualInferenceBasis) in g
    assert (ann, LECO.hasValidationStatus, LECO.ProposedAnnotation) in g
    assert list(g.objects(ann, LECO.attestedIn))
    score = list(g.objects(ann, LECO.confidenceScore))
    assert score and float(score[0]) <= 0.95
    activity = next(iter(g.objects(ann, PROV.wasGeneratedBy)))
    assert str(next(iter(g.objects(activity, DCTERMS.identifier)))) == "D005"


def test_ambiguous_multiple_authorities_does_not_derive(tmp_path):
    root = Path(__file__).resolve().parents[1]
    tei = tmp_path / "cab-test.xml"
    write_fixture(tei, two_authorities=True)
    g, conv = convert(root, tei)
    act = conv.local_uri("event_oath")
    assert not list(g.objects(act, LECO.withinJurisdiction))


def test_contextual_inference_basis_is_controlled_vocabulary():
    root = Path(__file__).resolve().parents[1]
    g = Graph().parse(root / "ontology" / "LeCO.ttl", format="turtle")
    assert (LECO.ContextualInferenceBasis, RDF.type, LECO.AnnotationBasis) in g
    assert (LECO.ContextualInferenceBasis, Namespace("http://www.w3.org/2004/02/skos/core#").inScheme, LECO.AnnotationBasisScheme) in g
