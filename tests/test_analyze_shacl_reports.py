from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "analyze_shacl_reports.py"
spec = importlib.util.spec_from_file_location("analyze_shacl_reports", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


NONCONFORMING = '''
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix leco: <https://w3id.org/leco/ontology#> .
@prefix ex: <https://example.org/> .

[] a sh:ValidationReport ;
   sh:conforms false ;
   sh:result [
      a sh:ValidationResult ;
      sh:resultSeverity sh:Violation ;
      sh:focusNode ex:appeal1 ;
      sh:sourceShape ex:AppealShape ;
      sh:sourceConstraintComponent sh:MinCountConstraintComponent ;
      sh:resultPath leco:beforeAuthority ;
      sh:resultMessage "Less than 1 values" ;
   ] ;
   sh:result [
      a sh:ValidationResult ;
      sh:resultSeverity sh:Warning ;
      sh:focusNode ex:act1 ;
      sh:sourceShape ex:ActQualityShape ;
      sh:sourceConstraintComponent sh:MinCountConstraintComponent ;
      sh:resultPath leco:withinJurisdiction ;
      sh:resultMessage "Missing jurisdictional context" ;
   ] .
'''

CONFORMING = '''
@prefix sh: <http://www.w3.org/ns/shacl#> .
[] a sh:ValidationReport ; sh:conforms true .
'''


def test_parse_reports_and_aggregate(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "cab-001-002.ttl").write_text(NONCONFORMING, encoding="utf-8")
    (reports / "cab-001-028.ttl").write_text(CONFORMING, encoding="utf-8")

    summary1, rows1 = mod.parse_report(reports / "cab-001-002.ttl")
    summary2, rows2 = mod.parse_report(reports / "cab-001-028.ttl")

    assert summary1.conforms is False
    assert summary1.result_count == 2
    assert summary1.violation_count == 1
    assert summary1.warning_count == 1
    assert summary2.conforms is True
    assert rows2 == []
    assert {r.result_path for r in rows1} == {
        "leco:beforeAuthority",
        "leco:withinJurisdiction",
    }

    grouped = mod.aggregate_rows(rows1 + rows2)
    assert len(grouped) == 2
    assert all(item["count"] == 1 for item in grouped)


def test_main_writes_outputs(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "cab-001-002.ttl").write_text(NONCONFORMING, encoding="utf-8")
    (reports / "cab-001-028.ttl").write_text(CONFORMING, encoding="utf-8")

    detail = tmp_path / "analysis.csv"
    summary = tmp_path / "summary.csv"
    output_json = tmp_path / "analysis.json"

    rc = mod.main([
        "--report-dir", str(reports),
        "--output", str(detail),
        "--summary-output", str(summary),
        "--json-output", str(output_json),
        "--top", "5",
    ])
    assert rc == 0
    assert detail.exists() and summary.exists() and output_json.exists()

    with detail.open(encoding="utf-8") as fh:
        detail_rows = list(csv.DictReader(fh))
    assert len(detail_rows) == 2

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["report_count"] == 2
    assert payload["conforming_documents"] == 1
    assert payload["nonconforming_documents"] == 1
    assert payload["validation_result_count"] == 2
    assert payload["severity_counts"] == {"Violation": 1, "Warning": 1}
