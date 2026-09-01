#!/usr/bin/env python3
"""Apply approved legal-relation reviews to TEI standOff safely.

Only rows with relation_review_status=approved are applied. Targets are resolved
exclusively from approved_target_xml_id; no name matching or fuzzy lookup is used.
The source TEI layer is never overwritten: output defaults to build/tei_legal_curated.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from lxml import etree as ET

try:
    from leco_normalization import office_type_local_name
except ImportError:
    from scripts.leco_normalization import office_type_local_name

TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI}
XML_ID = f"{{{XML}}}id"
LECO_BASE = "https://w3id.org/leco/ontology#"


def qn(local: str) -> str:
    return f"{{{TEI}}}{local}"


def norm_text(el: ET._Element) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def safe_piece(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def find_by_id(root: ET._Element, ident: str) -> Optional[ET._Element]:
    result = root.xpath("//*[@xml:id=$ident]", ident=ident, namespaces=NS)
    return result[0] if result else None


def nearest_segment_id(el: ET._Element) -> Optional[str]:
    cur = el
    while cur is not None:
        if cur.tag in {qn("seg"), qn("div")} and cur.get(XML_ID):
            return cur.get(XML_ID)
        cur = cur.getparent()
    return None


def ensure_standoff(root: ET._Element) -> ET._Element:
    so = root.find("tei:standOff", NS)
    if so is None:
        so = ET.Element(qn("standOff"))
        text = root.find("tei:text", NS)
        if text is not None:
            text.addnext(so)
        else:
            root.append(so)
    return so


def ensure_list_relation(standoff: ET._Element) -> ET._Element:
    lr = standoff.find("tei:listRelation", NS)
    if lr is None:
        lr = ET.SubElement(standoff, qn("listRelation"))
    return lr


def ensure_interp_group(standoff: ET._Element, grp_type: str) -> ET._Element:
    grp = standoff.find(f"tei:interpGrp[@type='{grp_type}']", NS)
    if grp is None:
        grp = ET.SubElement(standoff, qn("interpGrp"), type=grp_type)
    return grp


def ensure_precision(standoff: ET._Element, relation_id: str, confidence: str) -> None:
    target = f"#{relation_id}"
    for el in standoff.findall("tei:precision", NS):
        if el.get("target") == target:
            el.set("confidence", confidence)
            return
    ET.SubElement(standoff, qn("precision"), target=target, confidence=confidence)


def existing_relation(list_relation: ET._Element, active: str, name: str, passive: str) -> Optional[ET._Element]:
    for rel in list_relation.findall("tei:relation", NS):
        if (
            rel.get("type") == "objectProperty"
            and rel.get("name") == name
            and rel.get("active") == active
            and rel.get("passive") == passive
        ):
            return rel
    return None


def relation_targets(list_relation: ET._Element, active: str, name: str) -> list[str]:
    return [
        rel.get("passive")
        for rel in list_relation.findall("tei:relation", NS)
        if rel.get("type") == "objectProperty" and rel.get("name") == name and rel.get("active") == active
    ]


def make_source(row: dict[str, str], target_el: ET._Element, basis: str) -> str:
    ids: list[str] = []
    segment_id = (row.get("segment_id") or "").strip()
    if segment_id:
        ids.append(segment_id)
    if basis == "contextual":
        target_segment = nearest_segment_id(target_el)
        if target_segment and target_segment not in ids:
            ids.append(target_segment)
        # Stand-off entities do not have a textual ancestor. The audit table
        # preserves where the exact xml:id occurred in local context, so use
        # only a neighboring segment that explicitly lists that exact target.
        target_id = (row.get("approved_target_xml_id") or "").strip()
        for side in ("previous", "next", "same"):
            entities = row.get(f"{side}_segment_entities") or ""
            sid = (row.get(f"{side}_segment_id") or "").strip()
            if target_id and sid and target_id in entities and sid not in ids:
                ids.append(sid)
    return " ".join(f"#{x}" for x in ids)


def ensure_office_resource(
    root: ET._Element,
    standoff: ET._Element,
    row: dict[str, str],
    mention_el: ET._Element,
) -> tuple[str, str]:
    """Create/reuse a concrete leco:Office resource from an approved inline office mention."""
    mention_id = mention_el.get(XML_ID)
    label = norm_text(mention_el)
    office_type = office_type_local_name(label)
    if not office_type:
        # If the mention already carries a controlled ref, allow it as a fallback.
        ref = (mention_el.get("ref") or mention_el.get("ana") or "").strip()
        if ref.startswith(LECO_BASE):
            office_type = ref.rsplit("#", 1)[-1]
    if not office_type:
        raise ValueError(f"No controlled OfficeType normalization for {label!r} ({mention_id})")

    focus_id = (row.get("focus_xml_id") or "").strip()
    office_id = safe_piece(f"office_review_{focus_id}_{mention_id}")
    existing = find_by_id(root, office_id)
    if existing is None:
        grp = ensure_interp_group(standoff, "offices")
        interp = ET.SubElement(grp, qn("interp"))
        interp.set(XML_ID, office_id)
        interp.set("ana", f"{LECO_BASE}{office_type}")
        interp.set("corresp", f"#{mention_id}")
        interp.text = label
    return office_id, office_type


@dataclass
class Result:
    document: str
    property: str
    focus_xml_id: str
    approved_target_xml_id: str
    status: str
    generated_target_xml_id: str = ""
    message: str = ""


def apply_row(root: ET._Element, row: dict[str, str]) -> Result:
    doc = row["document"]
    prop = row["property"].split(":", 1)[-1]
    focus_id = row["focus_xml_id"].strip()
    approved_target_id = row["approved_target_xml_id"].strip()
    basis = row["approved_basis"].strip().lower()
    confidence = row["approved_confidence"].strip()

    if row["relation_review_status"].strip() != "approved":
        return Result(doc, prop, focus_id, approved_target_id, "not_applied_by_policy")
    if basis not in {"explicit", "contextual"}:
        return Result(doc, prop, focus_id, approved_target_id, "error", message=f"Invalid approved_basis={basis!r}")
    if not focus_id or not approved_target_id:
        return Result(doc, prop, focus_id, approved_target_id, "error", message="Approved row lacks exact focus/target xml:id")

    focus_el = find_by_id(root, focus_id)
    target_el = find_by_id(root, approved_target_id)
    if focus_el is None:
        return Result(doc, prop, focus_id, approved_target_id, "error", message="focus_xml_id not found in TEI")
    if target_el is None:
        return Result(doc, prop, focus_id, approved_target_id, "error", message="approved_target_xml_id not found in TEI")

    standoff = ensure_standoff(root)
    list_relation = ensure_list_relation(standoff)
    passive_id = approved_target_id
    generated_target_id = ""

    if prop == "appointsToOffice":
        try:
            passive_id, _ = ensure_office_resource(root, standoff, row, target_el)
            generated_target_id = passive_id
        except ValueError as exc:
            return Result(doc, prop, focus_id, approved_target_id, "error", message=str(exc))

    active = f"#{focus_id}"
    passive = f"#{passive_id}"
    if existing_relation(list_relation, active, prop, passive) is not None:
        return Result(doc, prop, focus_id, approved_target_id, "already_present", generated_target_id, "Exact relation already present")

    other_targets = relation_targets(list_relation, active, prop)
    if other_targets:
        return Result(
            doc, prop, focus_id, approved_target_id, "conflict",
            generated_target_id,
            f"Property already has target(s): {'; '.join(other_targets)}",
        )

    relation_id = safe_piece(f"review_{prop}_{focus_id}_{passive_id}")
    existing_id = find_by_id(root, relation_id)
    if existing_id is not None:
        return Result(doc, prop, focus_id, approved_target_id, "already_present", generated_target_id, "Review relation xml:id already exists")

    attrs = {
        "type": "objectProperty",
        "name": prop,
        "active": active,
        "passive": passive,
        "subtype": basis,
    }
    source = make_source(row, target_el, basis)
    if source:
        attrs["source"] = source
    rel = ET.SubElement(list_relation, qn("relation"), **attrs)
    rel.set(XML_ID, relation_id)

    if confidence:
        ensure_precision(standoff, relation_id, confidence)

    # Audit note is TEI-side documentation only; converter provenance comes from
    # subtype/source/precision and remains machine-readable.
    note_text = (row.get("relation_reviewer_note") or "").strip()
    if note_text:
        note = ET.SubElement(standoff, qn("note"), type="legal-relation-review", target=f"#{relation_id}")
        note.text = note_text

    return Result(doc, prop, focus_id, approved_target_id, "applied", generated_target_id)


def apply_reviews(input_dir: Path, review_csv: Path, output_dir: Path) -> list[Result]:
    with review_csv.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    by_doc: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_doc.setdefault(row["document"], []).append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[Result] = []

    # Preserve the complete 19-document layer, even if a document has no approved review.
    for src in sorted(input_dir.glob("*.xml")):
        doc = src.stem
        dst = output_dir / src.name
        tree = ET.parse(str(src))
        root = tree.getroot()
        for row in by_doc.get(doc, []):
            results.append(apply_row(root, row))
        tree.write(str(dst), encoding="utf-8", xml_declaration=True, pretty_print=True)

    # Report missing source documents referenced by the review file.
    available = {p.stem for p in input_dir.glob("*.xml")}
    for doc, doc_rows in by_doc.items():
        if doc not in available:
            for row in doc_rows:
                results.append(Result(doc, row["property"], row["focus_xml_id"], row["approved_target_xml_id"], "error", message="Source TEI document not found"))
    return results


def write_reports(results: list[Result], csv_path: Path, json_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(Result.__dataclass_fields__)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    json_path.write_text(json.dumps({"counts": counts, "results": [asdict(r) for r in results]}, ensure_ascii=False, indent=2), encoding="utf-8")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = repo_root()
    ap = argparse.ArgumentParser(description="Apply approved LeCO legal-relation reviews using exact xml:id targets")
    ap.add_argument("--input-dir", type=Path, default=root / "build" / "tei_participant_curated")
    ap.add_argument("--reviews", type=Path, default=root / "reviews" / "legal_relations" / "legal_relation_audit_review_queue_reviewed.csv")
    ap.add_argument("--output-dir", type=Path, default=root / "build" / "tei_legal_curated")
    ap.add_argument("--report", type=Path, default=root / "build" / "legal_relation_review_application.csv")
    ap.add_argument("--json-report", type=Path, default=root / "build" / "legal_relation_review_application.json")
    args = ap.parse_args()

    results = apply_reviews(args.input_dir, args.reviews, args.output_dir)
    write_reports(results, args.report, args.json_report)
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    print("LeCO legal-relation review application")
    print(f"Documents written: {len(list(args.output_dir.glob('*.xml')))}")
    print(f"Review rows processed: {len(results)}")
    for key in sorted(counts):
        print(f"  {key}: {counts[key]}")
    errors = counts.get("error", 0) + counts.get("conflict", 0)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
