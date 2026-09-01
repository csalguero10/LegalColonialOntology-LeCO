from pathlib import Path
import csv
import sys
from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Stub normalization for the self-contained package test. In the real repository
# the production leco_normalization.py is imported.
try:
    import leco_normalization  # noqa
except ImportError:
    mod = type(sys)("leco_normalization")
    mod.office_type_local_name = lambda s: "RegidorOfficeType" if "regidor" in s.lower() else None
    sys.modules["leco_normalization"] = mod

from apply_legal_relation_reviews import apply_reviews

TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI}
XML_ID = f"{{{XML}}}id"


def write_xml(path: Path, doc: str):
    if doc == "cab-001-006":
        event = 'event_cab-001-006_cab-001-006_s002_a001'; target = 'cab-001-006_cab-001-006_s002_a002'
        body = f'''<seg xml:id="cab-001-006_s002"><rs xml:id="cab-001-006_inline_appointment" type="legal_or_procedural_act">Nombrar</rs> <rs xml:id="{target}" type="role_or_office">regidores</rs></seg>'''
        stand = f'''<standOff><listEvent><event xml:id="{event}" ana="https://w3id.org/leco/ontology#Appointment" corresp="#cab-001-006_s002"><desc>Nombrar</desc></event></listEvent><listRelation/></standOff>'''
    else:
        event = 'event_cab-001-011_cab-001-011_s002_a001'; target = 'org_cab-001-011_cab-001-011_s001_a003'
        body = f'''<seg xml:id="cab-001-011_s001"><orgName xml:id="cab-001-011_inline_org">Cabildo Justicia y Regimiento</orgName></seg><seg xml:id="cab-001-011_s002">Se ordenó pregonar.</seg>'''
        stand = f'''<standOff><listOrg><org xml:id="{target}"><orgName>Cabildo Justicia y Regimiento</orgName></org></listOrg><listEvent><event xml:id="{event}" ana="https://w3id.org/leco/ontology#OrderAct" corresp="#cab-001-011_s002"><desc>ordenó</desc></event></listEvent><listRelation/></standOff>'''
    xml = f'''<?xml version="1.0" encoding="UTF-8"?><TEI xmlns="{TEI}" xml:id="{doc}"><text><body><div xml:id="{doc}_acta">{body}</div></body></text>{stand}</TEI>'''
    path.write_text(xml, encoding="utf-8")


def write_reviews(path: Path):
    fields = ["document","property","focus_xml_id","segment_id","previous_segment_id","previous_segment_entities","approved_target_xml_id","approved_basis","approved_confidence","relation_review_status","relation_reviewer_note"]
    rows = [
        ["cab-001-006","leco:appointsToOffice","event_cab-001-006_cab-001-006_s002_a001","cab-001-006_s002","","","cab-001-006_cab-001-006_s002_a002","explicit","1.00","approved","cargo explícito"],
        ["cab-001-011","leco:decidedBy","event_cab-001-011_cab-001-011_s002_a001","cab-001-011_s002","cab-001-011_s001","org:org_cab-001-011_cab-001-011_s001_a003|Cabildo Justicia y Regimiento","org_cab-001-011_cab-001-011_s001_a003","contextual","0.90","approved","autoridad contextual"],
    ]
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f); w.writerow(fields); w.writerows(rows)


def test_exact_target_and_office_materialization(tmp_path):
    inp=tmp_path/'in'; out=tmp_path/'out'; inp.mkdir()
    write_xml(inp/'cab-001-006.xml','cab-001-006'); write_xml(inp/'cab-001-011.xml','cab-001-011')
    reviews=tmp_path/'reviews.csv'; write_reviews(reviews)
    results=apply_reviews(inp,reviews,out)
    assert sum(r.status=='applied' for r in results)==2

    t6=ET.parse(str(out/'cab-001-006.xml'))
    office=t6.find(".//tei:interpGrp[@type='offices']/tei:interp",NS)
    assert office is not None
    assert office.get('ana').endswith('#RegidorOfficeType')
    rel=t6.find(".//tei:relation[@name='appointsToOffice']",NS)
    assert rel is not None and rel.get('passive') == '#'+office.get(XML_ID)
    assert rel.get('subtype')=='explicit'

    t11=ET.parse(str(out/'cab-001-011.xml'))
    rel=t11.find(".//tei:relation[@name='decidedBy']",NS)
    assert rel.get('passive')=='#org_cab-001-011_cab-001-011_s001_a003'
    assert rel.get('subtype')=='contextual'
    assert '#cab-001-011_s002' in rel.get('source') and '#cab-001-011_s001' in rel.get('source')


def test_idempotent(tmp_path):
    inp=tmp_path/'in'; mid=tmp_path/'mid'; out=tmp_path/'out'; inp.mkdir()
    write_xml(inp/'cab-001-006.xml','cab-001-006')
    reviews=tmp_path/'reviews.csv'
    fields=["document","property","focus_xml_id","segment_id","approved_target_xml_id","approved_basis","approved_confidence","relation_review_status","relation_reviewer_note"]
    with reviews.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f); w.writerow(fields); w.writerow(["cab-001-006","leco:appointsToOffice","event_cab-001-006_cab-001-006_s002_a001","cab-001-006_s002","cab-001-006_cab-001-006_s002_a002","explicit","1.00","approved",""])
    r1=apply_reviews(inp,reviews,mid); r2=apply_reviews(mid,reviews,out)
    assert r1[0].status=='applied'
    assert r2[0].status=='already_present'
