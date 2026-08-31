from pathlib import Path
import importlib.util
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "enrich_tei.py"
FIXTURE = ROOT / "tests" / "fixtures" / "cab-001-002"
TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"

spec = importlib.util.spec_from_file_location("enrich_tei", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_enrichment_adds_standoff_without_changing_transcription(tmp_path):
    before = mod.source_body_text(FIXTURE / "tei.xml")
    report = mod.enrich_one(FIXTURE, tmp_path)
    assert report.status == "enriched"
    out = tmp_path / "cab-001-002.xml"
    assert out.exists()
    after = mod.source_body_text(out)
    assert before == after

    root = ET.parse(out).getroot()
    assert root.find("tei:standOff", TEI_NS) is not None
    assert root.find(".//tei:listPerson/tei:person", TEI_NS) is not None
    assert root.find(".//tei:listEvent/tei:event[@ana='https://w3id.org/leco/ontology#Appeal']", TEI_NS) is not None
    assert root.find(".//tei:listRelation/tei:relation[@type='participation']", TEI_NS) is not None
    assert root.find(".//tei:listRelation/tei:relation[@name='appealsAgainst']", TEI_NS) is not None


def test_all_local_pointers_resolve(tmp_path):
    mod.enrich_one(FIXTURE, tmp_path)
    root = ET.parse(tmp_path / "cab-001-002.xml").getroot()
    ids = {el.get(XML_ID) for el in root.iter() if el.get(XML_ID)}
    attrs = ("ref", "active", "passive", "source", "target", "corresp")
    missing = []
    for el in root.iter():
        for attr in attrs:
            for ptr in (el.get(attr) or "").split():
                if ptr.startswith("#") and ptr[1:] not in ids:
                    missing.append((el.tag, attr, ptr))
    assert not missing, missing
