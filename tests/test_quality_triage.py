import csv
import subprocess
import sys
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

LECO = Namespace("https://w3id.org/leco/ontology#")


def write_analysis(path: Path, rows):
    fields = [
        "document", "report_file", "conforms", "severity", "focus_node",
        "source_shape", "constraint", "result_path", "value", "message",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader(); w.writerows(rows)


def test_links_event_warning_to_original_tei_segment(tmp_path):
    root = tmp_path
    (root / "build/rdf").mkdir(parents=True)
    (root / "build/tei_enriched").mkdir(parents=True)
    (root / "data/documents/cab-001-002").mkdir(parents=True)

    base = "https://w3id.org/leco/data/co-ahrb-cab-001-d002/"
    event = URIRef(base + "event_cab-001-002_s004_a001")
    seg = URIRef(base + "cab-001-002_s004")
    g = Graph()
    g.add((event, RDF.type, LECO.Appeal))
    g.add((event, RDFS.label, Literal("apelar", lang="es")))
    g.add((seg, LECO.documentsAct, event))
    g.serialize(root / "build/rdf/cab-001-002.ttl", format="turtle")

    source_xml = '''<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div xml:id="cab-001-002_acta"><seg xml:id="cab-001-002_s004">Juan de Pineda compareció ante la Real Audiencia para apelar la sanción.</seg></div></body></text></TEI>'''
    (root / "data/documents/cab-001-002/tei.xml").write_text(source_xml, encoding="utf-8")
    (root / "build/tei_enriched/cab-001-002.xml").write_text(source_xml, encoding="utf-8")

    analysis = root / "build/shacl_quality_analysis.csv"
    write_analysis(analysis, [{
        "document": "cab-001-002", "report_file": "x", "conforms": "True",
        "severity": "Warning", "focus_node": str(event), "source_shape": "_:s",
        "constraint": "sh:MinCountConstraintComponent", "result_path": "leco:withinJurisdiction",
        "value": "", "message": "warning",
    }])

    script = Path(__file__).resolve().parents[1] / "scripts" / "quality_triage.py"
    out = root / "build/quality_triage.csv"
    subprocess.run([
        sys.executable, str(script), "--analysis", str(analysis),
        "--rdf-dir", str(root / "build/rdf"),
        "--enriched-dir", str(root / "build/tei_enriched"),
        "--source-documents-dir", str(root / "data/documents"),
        "--output", str(out),
        "--json-output", str(root / "build/out.json"),
        "--unresolved-output", str(root / "build/unresolved.csv"),
    ], check=True)

    row = next(csv.DictReader(out.open(encoding="utf-8")))
    assert row["evidence_xml_ids"] == "cab-001-002_s004"
    assert "Juan de Pineda" in row["evidence_text"]
    assert row["evidence_file"] == "source-tei"
    assert row["suggested_action"] == "review_jurisdiction_context"


def test_links_concept_use_via_attested_in_and_or_warning_action(tmp_path):
    root = tmp_path
    (root / "build/rdf").mkdir(parents=True)
    (root / "build/tei_enriched").mkdir(parents=True)
    (root / "data/documents/cab-001-006").mkdir(parents=True)

    base = "https://w3id.org/leco/data/co-ahrb-cab-001-d006/"
    use = URIRef(base + "concept_use_cab-001-006_s003_a001")
    seg = URIRef(base + "cab-001-006_s003")
    g = Graph()
    g.add((use, RDF.type, LECO.HistoricalConceptUse))
    g.add((use, LECO.attestedIn, seg))
    g.add((use, LECO.lexicalForm, Literal("Majestad")))
    g.serialize(root / "build/rdf/cab-001-006.ttl", format="turtle")

    xml = '''<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div xml:id="cab-001-006_acta"><seg xml:id="cab-001-006_s003">Se hizo referencia a la Majestad en el acuerdo.</seg></div></body></text></TEI>'''
    (root / "data/documents/cab-001-006/tei.xml").write_text(xml, encoding="utf-8")
    (root / "build/tei_enriched/cab-001-006.xml").write_text(xml, encoding="utf-8")

    analysis = root / "build/shacl_quality_analysis.csv"
    write_analysis(analysis, [{
        "document": "cab-001-006", "report_file": "x", "conforms": "True",
        "severity": "Warning", "focus_node": str(use), "source_shape": "_:s",
        "constraint": "sh:MinCountConstraintComponent", "result_path": "leco:conceptUseTime",
        "value": "", "message": "warning",
    }])

    script = Path(__file__).resolve().parents[1] / "scripts" / "quality_triage.py"
    out = root / "build/quality_triage.csv"
    subprocess.run([
        sys.executable, str(script), "--analysis", str(analysis),
        "--rdf-dir", str(root / "build/rdf"),
        "--enriched-dir", str(root / "build/tei_enriched"),
        "--source-documents-dir", str(root / "data/documents"),
        "--output", str(out),
        "--json-output", str(root / "build/out.json"),
        "--unresolved-output", str(root / "build/unresolved.csv"),
    ], check=True)

    row = next(csv.DictReader(out.open(encoding="utf-8")))
    assert row["evidence_xml_ids"] == "cab-001-006_s003"
    assert "Majestad" in row["evidence_text"]
    assert row["focus_label"] == "Majestad"
    assert row["suggested_action"] == "review_concept_time"
