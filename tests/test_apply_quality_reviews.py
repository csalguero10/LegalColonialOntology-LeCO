from pathlib import Path
import csv
import importlib.util
import sys
import xml.etree.ElementTree as ET

TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI, "xml": XML}
XML_ID = f"{{{XML}}}id"


def load_module(root: Path):
    path = root / "scripts" / "apply_quality_reviews.py"
    spec = importlib.util.spec_from_file_location("apply_quality_reviews_tested", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def minimal_tei(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("""<?xml version="1.0" encoding="utf-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0" xml:id="cab-001-002">
  <teiHeader>
    <fileDesc><titleStmt><title>x</title></titleStmt><publicationStmt><p>x</p></publicationStmt><sourceDesc><p>x</p></sourceDesc></fileDesc>
    <profileDesc><creation><date when="1547-09-02">1547-09-02</date></creation></profileDesc>
    <revisionDesc/>
  </teiHeader>
  <text><body><div xml:id="cab-001-002_acta">
    <seg xml:id="cab-001-002_s004">Juan de Pineda <persName xml:id="m1" ref="#person_pineda">Juan de Pineda</persName>
      <rs xml:id="a1" type="legal_or_procedural_act" corresp="#event_appearance">compareció</rs>
      ante <orgName xml:id="o1" ref="#org_audiencia">Real Audiencia</orgName>.
    </seg>
    <seg xml:id="cab-001-002_s005">Se <rs xml:id="a2" type="legal_or_procedural_act" corresp="#event_order">ordenó</rs> investigar.</seg>
  </div></body></text>
  <standOff>
    <listPerson><person xml:id="person_pineda"><persName>Juan de Pineda</persName></person></listPerson>
    <listOrg><org xml:id="org_audiencia"><orgName>Real Audiencia</orgName></org></listOrg>
    <listEvent>
      <event xml:id="event_appearance" corresp="#cab-001-002_s004"><desc>compareció</desc></event>
      <event xml:id="event_order" corresp="#cab-001-002_s005"><desc>ordenó</desc></event>
    </listEvent>
    <listRelation/>
  </standOff>
</TEI>""", encoding="utf-8")


def row(**kw):
    base = {
        "document": "cab-001-002",
        "severity": "Warning",
        "constraint": "sh:MinCountConstraintComponent",
        "result_path": "",
        "message": "",
        "focus_node": "",
        "focus_types": "",
        "focus_label": "",
        "evidence_uris": "",
        "evidence_xml_ids": "",
        "evidence_text": "",
        "evidence_file": "source-tei",
        "evidence_method": "",
        "suggested_action": "",
        "suggested_action_note": "",
        "review_status": "",
        "reviewer_note": "",
    }
    base.update(kw)
    return base


def test_explicit_participant_and_contextual_authority(tmp_path):
    root = Path(__file__).resolve().parents[1]
    mod = load_module(root)
    tei = tmp_path / "cab-001-002.xml"
    minimal_tei(tei)
    cur = mod.TEICurator(tei)

    r1 = row(
        focus_node="https://w3id.org/leco/data/x/event_appearance",
        evidence_xml_ids="cab-001-002_s004",
        review_status="explicit_recoverable",
        reviewer_note="Juan de Pineda está explícitamente vinculado al acto.",
    )
    out1 = mod.apply_row(cur, r1, 2)
    assert out1.outcome == "applied"
    assert out1.target == "person_pineda"

    r2 = row(
        result_path="leco:decidedBy",
        focus_node="https://w3id.org/leco/data/x/event_order",
        evidence_xml_ids="cab-001-002_s005",
        review_status="contextual_inference",
        reviewer_note="inferir leco:decidedBy = RealAudiencia; confidence aproximada 0.80",
    )
    out2 = mod.apply_row(cur, r2, 3)
    assert out2.outcome == "applied"
    assert out2.target == "org_audiencia"

    rels = cur.relations.findall("tei:relation", NS)
    names = {(r.get("name"), r.get("active"), r.get("passive"), r.get("subtype")) for r in rels}
    assert ("hasParticipant", "#event_appearance", "#person_pineda", "explicit") in names
    assert ("decidedBy", "#event_order", "#org_audiencia", "inferred") in names


def test_keep_warning_and_jurisdiction_are_not_forced(tmp_path):
    root = Path(__file__).resolve().parents[1]
    mod = load_module(root)
    tei = tmp_path / "cab-001-002.xml"
    minimal_tei(tei)
    cur = mod.TEICurator(tei)

    keep = row(
        result_path="leco:appealsAgainst",
        focus_node="https://w3id.org/leco/data/x/event_appearance",
        evidence_xml_ids="cab-001-002_s004",
        review_status="keep_warning",
    )
    assert mod.apply_row(cur, keep, 2).outcome == "not_applied_by_policy"

    juris = row(
        result_path="leco:withinJurisdiction",
        focus_node="https://w3id.org/leco/data/x/event_order",
        evidence_xml_ids="cab-001-002_s005",
        review_status="contextual_inference",
    )
    assert mod.apply_row(cur, juris, 3).outcome == "deferred"
    assert not any(r.get("name") == "withinJurisdiction" for r in cur.relations.findall("tei:relation", NS))


def test_mapping_supports_curated_helper_nodes():
    root = Path(__file__).resolve().parents[1]
    mapping = (root / "mapping" / "tei_to_leco.yaml").read_text(encoding="utf-8")
    assert "- offices" in mapping
    assert "- legalArrangements" in mapping
    assert "- hasParticipant" in mapping
    assert "- principal" in mapping
    assert "- representative" in mapping
