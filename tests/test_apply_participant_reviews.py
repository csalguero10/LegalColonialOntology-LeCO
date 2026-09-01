from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI, "xml": XML}
XML_ID = f"{{{XML}}}id"

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply_participant_reviews.py"


def write_tei(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="{TEI}">
 <text><body><seg xml:id="s1">Juan compareció.</seg></body></text>
 <standOff>
  <listPerson><person xml:id="p1"><persName>Juan</persName></person><person xml:id="p2"><persName>Pedro</persName></person></listPerson>
  <listEvent><event xml:id="ev1" ana="https://w3id.org/leco/ontology#Appearance" corresp="#s1"/></listEvent>
  <listRelation><relation xml:id="old_wrong" type="objectProperty" name="hasParticipant" active="#ev1" passive="#p2" source="#s1" subtype="inferred"/></listRelation>
  <precision target="#old_wrong" confidence="0.80"/>
 </standOff>
</TEI>''', encoding="utf-8")


def write_csv(path: Path, status="approved", target="p1", basis="explicit", confidence="1.00"):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["document","focus_node","segment_id","current_hasParticipant","approved_target_xml_id","approved_basis","approved_confidence","participant_review_status"]
    row = {
        "document":"doc1", "focus_node":"https://example.org/ev1", "segment_id":"s1",
        "current_hasParticipant":"person:p2|Pedro", "approved_target_xml_id":target,
        "approved_basis":basis, "approved_confidence":confidence,
        "participant_review_status":status,
    }
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerow(row)


def run(tmp_path: Path, status="approved", target="p1", basis="explicit", confidence="1.00"):
    inp=tmp_path/"in"; out=tmp_path/"out"; reviews=tmp_path/"reviews.csv"
    write_tei(inp/"doc1.xml"); write_csv(reviews,status,target,basis,confidence)
    p=subprocess.run([sys.executable,str(SCRIPT),"--reviews",str(reviews),"--input-dir",str(inp),"--output-dir",str(out),"--report",str(tmp_path/"report.csv"),"--json-report",str(tmp_path/"report.json")], capture_output=True, text=True)
    return p,out


def participant_targets(xml_path: Path):
    root=ET.parse(xml_path).getroot()
    return [(r.get(XML_ID),r.get("passive"),r.get("subtype")) for r in root.findall(".//tei:listRelation/tei:relation[@name='hasParticipant']",NS)]


def test_approved_replaces_snapshot_with_exact_xml_id(tmp_path):
    p,out=run(tmp_path)
    assert p.returncode == 0, p.stdout+p.stderr
    assert participant_targets(out/"doc1.xml") == [("participant_review_0002_hasParticipant", "#p1", "explicit")]
    root=ET.parse(out/"doc1.xml").getroot()
    assert root.find(".//tei:precision[@target='#participant_review_0002_hasParticipant']",NS) is not None
    assert root.find(".//tei:precision[@target='#old_wrong']",NS) is None


def test_keep_warning_removes_suspect_relation_and_adds_none(tmp_path):
    p,out=run(tmp_path,status="keep_warning",target="",basis="unknown",confidence="")
    assert p.returncode == 0, p.stdout+p.stderr
    assert participant_targets(out/"doc1.xml") == []


def test_missing_approved_target_is_not_guessed(tmp_path):
    p,out=run(tmp_path,target="does_not_exist")
    assert p.returncode == 2
    assert participant_targets(out/"doc1.xml") == []
    report=(tmp_path/"report.csv").read_text(encoding="utf-8-sig")
    assert "target_not_found" in report
