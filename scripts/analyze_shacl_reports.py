#!/usr/bin/env python3
"""Analyze a directory of RDF SHACL validation reports for the LeCO corpus.

The script is intentionally read-only with respect to source/enriched TEI and RDF.
It parses pySHACL Turtle reports from ``build/shacl_reports`` and produces:

* ``build/shacl_analysis.csv``: one row per ``sh:ValidationResult``;
* ``build/shacl_analysis_summary.csv``: grouped counts for repeated problems;
* ``build/shacl_analysis.json``: corpus/document summary plus result details.

Typical use from the repository root::

    python scripts/analyze_shacl_reports.py

Custom paths are also supported::

    python scripts/analyze_shacl_reports.py \
        --report-dir build/shacl_reports \
        --output build/shacl_analysis.csv \
        --summary-output build/shacl_analysis_summary.csv \
        --json-output build/shacl_analysis.json

The analyzer does not decide whether a constraint should be a Violation or a
Warning. That is a methodological decision to make after inspecting corpus-wide
patterns.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF, SH

KNOWN_PREFIXES = {
    "https://w3id.org/leco/ontology#": "leco:",
    "http://www.w3.org/ns/shacl#": "sh:",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://www.w3.org/2004/02/skos/core#": "skos:",
    "https://www.ica.org/standards/RiC/ontology#": "rico:",
    "http://www.cidoc-crm.org/cidoc-crm/": "crm:",
    "http://purl.org/dc/terms/": "dcterms:",
    "http://www.w3.org/ns/prov#": "prov:",
}


@dataclass(frozen=True)
class ResultRow:
    document: str
    report_file: str
    conforms: bool
    severity: str
    focus_node: str
    source_shape: str
    constraint: str
    result_path: str
    value: str
    message: str


@dataclass(frozen=True)
class ReportSummary:
    document: str
    report_file: str
    conforms: bool
    result_count: int
    violation_count: int
    warning_count: int
    info_count: int


def compact_term(term) -> str:
    """Return a stable, readable representation of an RDF term."""
    if term is None:
        return ""
    if isinstance(term, URIRef):
        text = str(term)
        for ns, prefix in KNOWN_PREFIXES.items():
            if text.startswith(ns):
                return prefix + text[len(ns):]
        return text
    if isinstance(term, BNode):
        return f"_:{term}"
    if isinstance(term, Literal):
        return str(term)
    return str(term)


def local_name(value: str) -> str:
    """Human-friendly local name for severity/constraint URI strings."""
    if not value:
        return ""
    if value.startswith("sh:"):
        return value[3:]
    for sep in ("#", "/"):
        if sep in value:
            value = value.rsplit(sep, 1)[-1]
    return value


def severity_name(term) -> str:
    compact = compact_term(term)
    return local_name(compact) or "Unknown"


def first_object(graph: Graph, subject, predicate):
    return next(graph.objects(subject, predicate), None)


def joined_objects(graph: Graph, subject, predicate, separator: str = " | ") -> str:
    vals = [compact_term(v) for v in graph.objects(subject, predicate)]
    return separator.join(dict.fromkeys(vals))


def report_conforms(graph: Graph) -> bool:
    for report in graph.subjects(RDF.type, SH.ValidationReport):
        value = first_object(graph, report, SH.conforms)
        if isinstance(value, Literal):
            try:
                return bool(value.toPython())
            except Exception:
                return str(value).strip().lower() == "true"
    # A malformed/partial report should not be silently treated as conforming.
    return False


def parse_report(path: Path) -> tuple[ReportSummary, list[ResultRow]]:
    graph = Graph().parse(path, format="turtle")
    conforms = report_conforms(graph)
    document = path.stem
    rows: list[ResultRow] = []

    result_nodes = sorted(
        set(graph.subjects(RDF.type, SH.ValidationResult)),
        key=lambda n: str(n),
    )
    for result in result_nodes:
        severity_term = first_object(graph, result, SH.resultSeverity)
        constraint_term = first_object(graph, result, SH.sourceConstraintComponent)
        row = ResultRow(
            document=document,
            report_file=str(path),
            conforms=conforms,
            severity=severity_name(severity_term),
            focus_node=compact_term(first_object(graph, result, SH.focusNode)),
            source_shape=compact_term(first_object(graph, result, SH.sourceShape)),
            constraint=compact_term(constraint_term),
            result_path=compact_term(first_object(graph, result, SH.resultPath)),
            value=joined_objects(graph, result, SH.value),
            message=joined_objects(graph, result, SH.resultMessage),
        )
        rows.append(row)

    counts = Counter(r.severity for r in rows)
    summary = ReportSummary(
        document=document,
        report_file=str(path),
        conforms=conforms,
        result_count=len(rows),
        violation_count=counts.get("Violation", 0),
        warning_count=counts.get("Warning", 0),
        info_count=counts.get("Info", 0),
    )
    return summary, rows


def discover_reports(report_dir: Path) -> list[Path]:
    return sorted(
        p for p in report_dir.glob("*.ttl")
        if p.is_file() and not p.name.startswith(".")
    )


def write_detail_csv(path: Path, rows: Iterable[ResultRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "document", "report_file", "conforms", "severity", "focus_node",
        "source_shape", "constraint", "result_path", "value", "message",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def aggregate_rows(rows: Iterable[ResultRow]) -> list[dict]:
    counter: Counter[tuple] = Counter()
    for r in rows:
        # Do not group by focus node/value: the purpose is to discover repeated
        # corpus-level constraint patterns.
        key = (
            r.document,
            r.severity,
            r.source_shape,
            r.constraint,
            r.result_path,
            r.message,
        )
        counter[key] += 1

    grouped = []
    for key, count in sorted(
        counter.items(),
        key=lambda item: (item[0][0], item[0][1], item[0][4], item[0][3], item[0][5]),
    ):
        document, severity, source_shape, constraint, result_path, message = key
        grouped.append({
            "document": document,
            "severity": severity,
            "source_shape": source_shape,
            "constraint": constraint,
            "result_path": result_path,
            "message": message,
            "count": count,
        })
    return grouped


def write_summary_csv(path: Path, grouped: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "document", "severity", "source_shape", "constraint",
        "result_path", "message", "count",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(grouped)


def corpus_aggregates(rows: list[ResultRow]) -> list[dict]:
    documents_by_key: defaultdict[tuple, set[str]] = defaultdict(set)
    counts: Counter[tuple] = Counter()
    for r in rows:
        key = (r.severity, r.constraint, r.result_path, r.message)
        counts[key] += 1
        documents_by_key[key].add(r.document)

    items = []
    for key, count in counts.items():
        severity, constraint, result_path, message = key
        items.append({
            "severity": severity,
            "constraint": constraint,
            "result_path": result_path,
            "message": message,
            "count": count,
            "document_count": len(documents_by_key[key]),
            "documents": sorted(documents_by_key[key]),
        })
    items.sort(key=lambda x: (-x["count"], -x["document_count"], x["result_path"], x["constraint"]))
    return items


def write_json(
    path: Path,
    report_dir: Path,
    summaries: list[ReportSummary],
    rows: list[ResultRow],
    grouped: list[dict],
) -> dict:
    severity_counts = Counter(r.severity for r in rows)
    global_patterns = corpus_aggregates(rows)
    payload = {
        "report_directory": str(report_dir),
        "report_count": len(summaries),
        "conforming_documents": sum(1 for s in summaries if s.conforms),
        "nonconforming_documents": sum(1 for s in summaries if not s.conforms),
        "validation_result_count": len(rows),
        "severity_counts": dict(sorted(severity_counts.items())),
        "documents": [asdict(s) for s in summaries],
        "corpus_patterns": global_patterns,
        "document_patterns": grouped,
        "results": [asdict(r) for r in rows],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def print_console_summary(payload: dict, top: int = 12) -> None:
    print("SHACL corpus diagnostics")
    print(f"Reports: {payload['report_count']}")
    print(
        f"Conforms: {payload['conforming_documents']} | "
        f"Non-conforms: {payload['nonconforming_documents']}"
    )
    print(f"Validation results: {payload['validation_result_count']}")
    if payload["severity_counts"]:
        sev = " | ".join(f"{k}: {v}" for k, v in payload["severity_counts"].items())
        print(f"Severity: {sev}")

    patterns = payload["corpus_patterns"][:top]
    if patterns:
        print("\nMost frequent corpus patterns:")
        for item in patterns:
            path = item["result_path"] or "(no resultPath)"
            constraint = local_name(item["constraint"]) or "(no constraint)"
            print(
                f"  {item['count']:>4} × {item['severity']:<9} | "
                f"{path} | {constraint} | {item['document_count']} doc(s)"
            )

    nonconforming = [d["document"] for d in payload["documents"] if not d["conforms"]]
    if nonconforming:
        print("\nNon-conforming documents:")
        print("  " + ", ".join(nonconforming))


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Analyze LeCO SHACL Turtle reports corpus-wide.")
    parser.add_argument("--report-dir", type=Path, default=root / "build" / "shacl_reports")
    parser.add_argument("--output", type=Path, default=root / "build" / "shacl_analysis.csv")
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=root / "build" / "shacl_analysis_summary.csv",
    )
    parser.add_argument("--json-output", type=Path, default=root / "build" / "shacl_analysis.json")
    parser.add_argument("--top", type=int, default=12, help="Number of frequent patterns to print.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.report_dir.exists():
        print(f"Report directory does not exist: {args.report_dir}", file=sys.stderr)
        return 2

    report_files = discover_reports(args.report_dir)
    if not report_files:
        print(f"No Turtle SHACL reports found in: {args.report_dir}", file=sys.stderr)
        return 2

    summaries: list[ReportSummary] = []
    rows: list[ResultRow] = []
    parse_errors: list[str] = []

    for report_file in report_files:
        try:
            summary, report_rows = parse_report(report_file)
        except Exception as exc:
            parse_errors.append(f"{report_file.name}: {exc}")
            continue
        summaries.append(summary)
        rows.extend(report_rows)

    if not summaries:
        print("No SHACL report could be parsed.", file=sys.stderr)
        for err in parse_errors:
            print(f"  {err}", file=sys.stderr)
        return 2

    grouped = aggregate_rows(rows)
    write_detail_csv(args.output, rows)
    write_summary_csv(args.summary_output, grouped)
    payload = write_json(args.json_output, args.report_dir, summaries, rows, grouped)
    print_console_summary(payload, top=max(args.top, 0))

    print("\nOutputs:")
    print(f"  Detail:  {args.output}")
    print(f"  Summary: {args.summary_output}")
    print(f"  JSON:    {args.json_output}")

    if parse_errors:
        print("\nWarnings: some reports could not be parsed:", file=sys.stderr)
        for err in parse_errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
