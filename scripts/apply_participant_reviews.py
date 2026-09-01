#!/usr/bin/env python3
"""Apply human-approved participant audit decisions to curated TEI.

This script is deliberately strict about identity:
- it NEVER resolves people or institutions from free-text names;
- approved targets MUST be exact xml:id values from the reviewed CSV;
- stale participant relations captured by the audit are removed before a reviewed
  decision is applied;
- keep_warning and needs_review do not create new participant assertions.

Input TEI is never edited in place. A new derived layer is written by default to
``build/tei_participant_curated``.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI, "xml": XML}
XML_ID = f"{{{XML}}}id"
ET.register_namespace("", TEI)

VALID_STATUSES = {"approved", "keep_warning", "needs_review"}
VALID_BASES = {"explicit", "contextual", "unknown"}


def qn(local: str) -> str:
    return f"{{{TEI}}}{local}"


def local_from_uri(uri: str) -> str:
    return (uri or "").rstrip("/").rsplit("/", 1)[-1]


def ptr(xid: str) -> str:
    return f"#{xid}"


def parse_current_target_ids(value: str) -> list[str]:
    """Parse audit strings like ``person:xml_id|Label; org:xml_id|Label``."""
    out: list[str] = []
    for part in (value or "").split(";"):
        part = part.strip()
        if not part:
            continue
        head = part.split("|", 1)[0].strip()
        if ":" not in head:
            continue
        _, xid = head.split(":", 1)
        xid = xid.strip()
        if xid and xid not in out:
            out.append(xid)
    return out


def parse_confidence(value: str) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        x = float(value.replace(",", "."))
    except ValueError:
        return None
    return x if 0.0 <= x <= 1.0 else None


@dataclass
class ApplicationResult:
    row: int
    document: str
    focus_id: str
    status: str
    basis: str
    approved_target_xml_id: str
    outcome: str
    removed_relation_ids: str = ""
    added_relation_id: str = ""
    reason: str = ""


class TEIParticipantCurator:
    def __init__(self, path: Path):
        self.path = path
        self.tree = ET.parse(path)
        self.root = self.tree.getroot()
        self.id_index: dict[str, ET.Element] = {
            el.get(XML_ID): el
            for el in self.root.iter()
            if el.get(XML_ID)
        }
        self.standoff = self.root.find("tei:standOff", NS)
        if self.standoff is None:
            self.standoff = ET.SubElement(self.root, qn("standOff"))
        self.list_relation = self.standoff.find("tei:listRelation", NS)
        if self.list_relation is None:
            self.list_relation = ET.SubElement(self.standoff, qn("listRelation"))

    def has_id(self, xid: str) -> bool:
        return xid in self.id_index

    def is_entity_id(self, xid: str) -> bool:
        el = self.id_index.get(xid)
        return el is not None and el.tag in {qn("person"), qn("org")}

    def is_event_id(self, xid: str) -> bool:
        el = self.id_index.get(xid)
        return el is not None and el.tag == qn("event")

    def remove_precision(self, relation_id: str) -> None:
        target = ptr(relation_id)
        for p in list(self.standoff.findall("tei:precision", NS)):
            if p.get("target") == target:
                self.standoff.remove(p)

    def participant_relations(self, focus_id: str) -> list[ET.Element]:
        active = ptr(focus_id)
        return [
            r for r in self.list_relation.findall("tei:relation", NS)
            if r.get("type") == "objectProperty"
            and r.get("name") == "hasParticipant"
            and r.get("active") == active
        ]

    def remove_snapshot_relations(self, focus_id: str, snapshot_targets: Iterable[str]) -> list[str]:
        """Remove only relations that were captured as current by the human audit.

        Participant-review relations from an earlier run for the same focus are also
        removed, making the script idempotent without deleting unrelated later work.
        """
        snapshot = {ptr(x) for x in snapshot_targets if x}
        removed: list[str] = []
        for r in list(self.participant_relations(focus_id)):
            rid = r.get(XML_ID) or ""
            should_remove = r.get("passive") in snapshot or rid.startswith("participant_review_")
            if not should_remove:
                continue
            self.list_relation.remove(r)
            if rid:
                removed.append(rid)
                self.remove_precision(rid)
                self.id_index.pop(rid, None)
        return removed

    def add_reviewed_relation(
        self,
        relation_id: str,
        focus_id: str,
        target_id: str,
        segment_id: str,
        basis: str,
        confidence: float | None,
    ) -> None:
        attrs = {
            XML_ID: relation_id,
            "type": "objectProperty",
            "name": "hasParticipant",
            "active": ptr(focus_id),
            "passive": ptr(target_id),
            "source": ptr(segment_id),
            "subtype": basis,
        }
        rel = ET.SubElement(self.list_relation, qn("relation"), attrs)
        self.id_index[relation_id] = rel
        if confidence is not None:
            ET.SubElement(
                self.standoff,
                qn("precision"),
                {"target": ptr(relation_id), "confidence": f"{confidence:.2f}"},
            )

    def write(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            ET.indent(self.tree, space="  ")
        except AttributeError:
            pass
        self.tree.write(destination, encoding="utf-8", xml_declaration=True)


def read_reviews(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def validate_review_row(row: dict[str, str]) -> str | None:
    status = (row.get("participant_review_status") or "").strip()
    basis = (row.get("approved_basis") or "").strip()
    target = (row.get("approved_target_xml_id") or "").strip()
    if status not in VALID_STATUSES:
        return f"invalid participant_review_status={status!r}"
    if basis not in VALID_BASES:
        return f"invalid approved_basis={basis!r}"
    if status == "approved":
        if not target:
            return "approved row has no approved_target_xml_id"
        if basis not in {"explicit", "contextual"}:
            return "approved row must use explicit or contextual basis"
        if parse_confidence(row.get("approved_confidence", "")) is None:
            return "approved row has invalid/missing confidence"
    else:
        if target:
            return "non-approved row must not contain approved_target_xml_id"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reviews", type=Path, default=Path("reviews/participants/participant_audit_unresolved_reviewed.csv"))
    ap.add_argument("--input-dir", type=Path, default=Path("build/tei_curated"))
    ap.add_argument("--output-dir", type=Path, default=Path("build/tei_participant_curated"))
    ap.add_argument("--report", type=Path, default=Path("build/participant_review_application.csv"))
    ap.add_argument("--json-report", type=Path, default=Path("build/participant_review_application.json"))
    args = ap.parse_args()

    reviews = read_reviews(args.reviews)
    by_doc: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for row_no, row in enumerate(reviews, start=2):  # CSV header is line 1
        by_doc[row.get("document", "")].append((row_no, row))

    if args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    results: list[ApplicationResult] = []
    source_files = sorted(args.input_dir.glob("*.xml"))
    source_docs = {p.stem for p in source_files}

    # Preserve every input document, including documents without participant-review rows.
    for source in source_files:
        doc = source.stem
        curator = TEIParticipantCurator(source)
        for row_no, row in by_doc.get(doc, []):
            focus_id = local_from_uri(row.get("focus_node", ""))
            status = (row.get("participant_review_status") or "").strip()
            basis = (row.get("approved_basis") or "").strip()
            target = (row.get("approved_target_xml_id") or "").strip()
            seg_id = (row.get("segment_id") or "").strip()

            invalid = validate_review_row(row)
            if invalid:
                results.append(ApplicationResult(row_no, doc, focus_id, status, basis, target, "invalid_review", reason=invalid))
                continue
            if not curator.is_event_id(focus_id):
                results.append(ApplicationResult(row_no, doc, focus_id, status, basis, target, "focus_not_found", reason="focus event xml:id not found in TEI"))
                continue
            if seg_id and not curator.has_id(seg_id):
                results.append(ApplicationResult(row_no, doc, focus_id, status, basis, target, "evidence_not_found", reason="segment xml:id not found in TEI"))
                continue

            snapshot_targets = parse_current_target_ids(row.get("current_hasParticipant", ""))
            removed = curator.remove_snapshot_relations(focus_id, snapshot_targets)

            if status in {"keep_warning", "needs_review"}:
                results.append(ApplicationResult(
                    row_no, doc, focus_id, status, basis, "", "left_unasserted",
                    removed_relation_ids=";".join(removed),
                    reason="review decision deliberately leaves participant unasserted",
                ))
                continue

            if not curator.is_entity_id(target):
                results.append(ApplicationResult(
                    row_no, doc, focus_id, status, basis, target, "target_not_found",
                    removed_relation_ids=";".join(removed),
                    reason="approved target xml:id is not a person/org entity in this TEI; no fallback attempted",
                ))
                continue

            relation_id = f"participant_review_{row_no:04d}_hasParticipant"
            confidence = parse_confidence(row.get("approved_confidence", ""))
            curator.add_reviewed_relation(relation_id, focus_id, target, seg_id, basis, confidence)
            results.append(ApplicationResult(
                row_no, doc, focus_id, status, basis, target, "applied",
                removed_relation_ids=";".join(removed),
                added_relation_id=relation_id,
            ))

        curator.write(args.output_dir / source.name)

    # Reviews referring to a document absent from the input layer are never silently dropped.
    for doc, doc_rows in by_doc.items():
        if doc in source_docs:
            continue
        for row_no, row in doc_rows:
            results.append(ApplicationResult(
                row_no, doc, local_from_uri(row.get("focus_node", "")),
                row.get("participant_review_status", ""), row.get("approved_basis", ""),
                row.get("approved_target_xml_id", ""), "document_not_found",
                reason=f"{doc}.xml not found under {args.input_dir}",
            ))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    fields = list(ApplicationResult.__dataclass_fields__.keys())
    with args.report.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(asdict(r) for r in results)

    counts = Counter(r.outcome for r in results)
    payload = {
        "input_documents": len(source_files),
        "review_rows": len(reviews),
        "outcomes": dict(sorted(counts.items())),
        "output_directory": str(args.output_dir),
        "principle": "Exact approved_target_xml_id only; no name-based target resolution.",
    }
    args.json_report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("LeCO participant review application")
    print(f"Documents written: {len(source_files)}")
    print(f"Review rows: {len(reviews)}")
    for key, value in sorted(counts.items()):
        print(f"  {key}: {value}")
    print(f"TEI output: {args.output_dir}")
    print(f"Report: {args.report}")
    return 0 if not any(k in counts for k in {"invalid_review", "focus_not_found", "evidence_not_found", "target_not_found", "document_not_found"}) else 2


if __name__ == "__main__":
    raise SystemExit(main())
