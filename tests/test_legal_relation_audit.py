from pathlib import Path
import csv
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "legal_relation_audit.py"
spec = importlib.util.spec_from_file_location("legal_relation_audit", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_target_warning_filter():
    yes = [
        "leco:decidedBy", "leco:sanctions", "leco:appointsPerson",
        "leco:appointsToOffice", "leco:appealsAgainst", "leco:beforeAuthority",
    ]
    for path in yes:
        assert mod.is_target_warning({"result_path": path})
    assert not mod.is_target_warning({"result_path": "leco:withinJurisdiction"})
    assert not mod.is_target_warning({"result_path": ""})


def test_candidate_render_is_explicit_about_xml_id():
    c = mod.Candidate("person", "person_doc_s1_a1", "Juan", "before", "historicalPerson")
    assert c.render().startswith("person:person_doc_s1_a1|Juan|before")


def test_read_csv_utf8_bom(tmp_path):
    p = tmp_path / "x.csv"
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["document", "result_path"])
        w.writeheader(); w.writerow({"document": "cab-001-002", "result_path": "leco:decidedBy"})
    rows = mod.read_csv(p)
    assert rows[0]["document"] == "cab-001-002"
