#!/usr/bin/env python3
"""Apply approved LeCO QUALITY review decisions to enriched TEI.

The reviewed CSV is a human-curated decision ledger. This script never edits
build/tei_enriched in place. It writes curated TEI to build/tei_curated and an
application audit trail.

Only decisions whose target can be resolved deterministically are asserted.
Accepted decisions that still need target resolution remain in the pending
report instead of being guessed.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI, "xml": XML}
XML_ID = f"{{{XML}}}id"
ET.register_namespace("", TEI)

LECO = "https://w3id.org/leco/ontology#"
APPLY_STATUSES = {"explicit_recoverable", "contextual_inference"}


def qn(local: str) -> str:
    return f"{{{TEI}}}{local}"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def text(el: Optional[ET.Element]) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def local_from_uri(uri: str) -> str:
    return (uri or "").rstrip("/").rsplit("/", 1)[-1]


def ptr(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    return v if v.startswith("#") or "://" in v else f"#{v}"


def parse_confidence(note: str, default: float) -> float:
    m = re.search(r"confidence(?: aproximada)?\s*([0-9]+(?:[\.,][0-9]+)?)", note or "", re.I)
    if m:
        try:
            return max(0.0, min(1.0, float(m.group(1).replace(",", "."))))
        except ValueError:
            pass
    return default


@dataclass
class Result:
    row: int
    document: str
    status: str
    result_path: str
    focus_node: str
    evidence_xml_id: str
    outcome: str
    relation_xml_id: str = ""
    target: str = ""
    reason: str = ""


class TEICurator:
    def __init__(self, path: Path, metadata_date: Optional[str] = None):
        self.path = path
        self.metadata_date = metadata_date
        self.tree = ET.parse(path)
        self.root = self.tree.getroot()
        self.id_index: dict[str, ET.Element] = {}
        for el in self.root.iter():
            xid = el.get(XML_ID)
            if xid:
                self.id_index[xid] = el
        self.standoff = self.root.find("tei:standOff", NS)
        if self.standoff is None:
            self.standoff = ET.SubElement(self.root, qn("standOff"))
        self.relations = self.standoff.find("tei:listRelation", NS)
        if self.relations is None:
            self.relations = ET.SubElement(self.standoff, qn("listRelation"))
        self.precisions = {
            p.get("target"): p for p in self.standoff.findall("tei:precision", NS) if p.get("target")
        }
        self.existing_rel_keys = set()
        for r in self.relations.findall("tei:relation", NS):
            self.existing_rel_keys.add((r.get("type"), r.get("name"), r.get("active"), r.get("passive")))

    def segment(self, xid: str) -> Optional[ET.Element]:
        el = self.id_index.get(xid)
        if el is not None and el.tag == qn("seg"):
            return el
        return self.root.find(f".//tei:seg[@xml:id='{xid}']", NS)

    def document_date(self) -> Optional[str]:
        d = self.root.find(".//tei:profileDesc/tei:creation/tei:date", NS)
        if d is not None:
            candidate = d.get("when") or text(d)
            if candidate and re.match(r"^\d{4}(-\d{2}(-\d{2})?)?$", candidate):
                return candidate
        if self.metadata_date and re.match(r"^\d{4}(-\d{2}(-\d{2})?)?$", self.metadata_date):
            return self.metadata_date
        return None

    def ensure_interpgrp(self, typ: str) -> ET.Element:
        grp = self.standoff.find(f"tei:interpGrp[@type='{typ}']", NS)
        if grp is None:
            grp = ET.SubElement(self.standoff, qn("interpGrp"), {"type": typ})
        return grp

    def ensure_precision(self, target_id: str, confidence: float):
        target = f"#{target_id}"
        if target in self.precisions:
            return
        p = ET.SubElement(self.standoff, qn("precision"), {"target": target, "confidence": f"{confidence:.2f}"})
        self.precisions[target] = p

    def add_object_relation(self, xid: str, name: str, active: str, passive: str, source: str, subtype: str, confidence: Optional[float] = None) -> tuple[bool, str]:
        key = ("objectProperty", name, ptr(active), ptr(passive))
        if key in self.existing_rel_keys:
            return False, "duplicate"
        attrs = {
            XML_ID: xid,
            "type": "objectProperty",
            "name": name,
            "active": ptr(active) or active,
            "passive": ptr(passive) or passive,
            "source": ptr(source) or source,
            "subtype": subtype,
        }
        ET.SubElement(self.relations, qn("relation"), attrs)
        self.existing_rel_keys.add(key)
        self.id_index[xid] = self.relations[-1]
        if confidence is not None:
            self.ensure_precision(xid, confidence)
        return True, xid

    def add_helper(self, grp_type: str, xid: str, label: str, ana: Optional[str] = None) -> str:
        if xid in self.id_index:
            return xid
        grp = self.ensure_interpgrp(grp_type)
        attrs = {XML_ID: xid}
        if ana:
            attrs["ana"] = ana
        el = ET.SubElement(grp, qn("interp"), attrs)
        el.text = label
        self.id_index[xid] = el
        return xid

    def event_inline(self, focus_id: str, seg: ET.Element) -> Optional[ET.Element]:
        for el in seg.iter(qn("rs")):
            if el.get("corresp") == f"#{focus_id}":
                return el
        return None

    def ordered_semantic_elements(self, seg: ET.Element) -> list[ET.Element]:
        tags = {qn("persName"), qn("orgName"), qn("rs"), qn("term")}
        return [el for el in seg.iter() if el.tag in tags]

    def entity_pointer(self, el: ET.Element) -> Optional[str]:
        if el.tag in {qn("persName"), qn("orgName")}:
            return el.get("ref")
        return None

    def entity_candidates(self, seg: ET.Element) -> list[tuple[int, ET.Element, str]]:
        out = []
        for i, el in enumerate(self.ordered_semantic_elements(seg)):
            p = self.entity_pointer(el)
            if p:
                out.append((i, el, p))
        return out

    def unique_entity(self, seg: ET.Element, tag_preference: Optional[str] = None) -> Optional[str]:
        candidates = []
        for _, el, p in self.entity_candidates(seg):
            if tag_preference == "person" and el.tag != qn("persName"):
                continue
            if tag_preference == "org" and el.tag != qn("orgName"):
                continue
            candidates.append(p.lstrip("#"))
        # de-duplicate repeated mentions of the same entity
        candidates = list(dict.fromkeys(candidates))
        return candidates[0] if len(candidates) == 1 else None

    def find_entity_by_name(self, phrase: str, tags=("person", "org")) -> Optional[str]:
        wanted = norm(phrase)
        candidates = []
        if "person" in tags:
            for el in self.standoff.findall(".//tei:listPerson/tei:person[@xml:id]", NS):
                label = text(el.find("tei:persName", NS))
                if wanted in norm(label) or norm(label) in wanted:
                    candidates.append((el.get(XML_ID), label))
        if "org" in tags:
            for el in self.standoff.findall(".//tei:listOrg/tei:org[@xml:id]", NS):
                label = text(el.find("tei:orgName", NS))
                if wanted in norm(label) or norm(label) in wanted:
                    candidates.append((el.get(XML_ID), label))
        if len(candidates) == 1:
            return candidates[0][0]
        return None

    def named_target_from_note(self, note: str, tags=("person", "org")) -> Optional[str]:
        n = norm(note)
        aliases = [
            ("real audiencia", "Real Audiencia"),
            ("audiencia", "Audiencia"),
            ("cabildo", "Cabildo"),
            ("justicia y regimiento", "Justicia y Regimiento"),
            ("juan de pineda", "Juan de Pineda"),
            ("hernan suarez de villalobos", "Hernan Suárez de Villalobos"),
            ("juan de orozco", "Juan de Orozco"),
            ("gonzalo suarez", "Gonzalo Suárez"),
            ("miguel de trujillo", "Miguel de Trujillo"),
        ]
        for needle, label in aliases:
            if needle in n:
                found = self.find_entity_by_name(label, tags)
                if found:
                    return found
        return None

    def nearest_entity(self, seg: ET.Element, focus_id: str, prefer: str = "before", tag_preference: Optional[str] = None) -> Optional[str]:
        ordered = self.ordered_semantic_elements(seg)
        focus_el = self.event_inline(focus_id, seg)
        if focus_el is None or focus_el not in ordered:
            candidates = self.entity_candidates(seg)
            return candidates[0][2].lstrip("#") if len(candidates) == 1 else None
        fi = ordered.index(focus_el)
        candidates = []
        for i, el in enumerate(ordered):
            p = self.entity_pointer(el)
            if not p:
                continue
            if tag_preference == "person" and el.tag != qn("persName"):
                continue
            if tag_preference == "org" and el.tag != qn("orgName"):
                continue
            candidates.append((i, el, p))
        if not candidates:
            return None
        if prefer == "before":
            prior = [c for c in candidates if c[0] < fi]
            if prior:
                return max(prior, key=lambda c: c[0])[2].lstrip("#")
        if prefer == "after":
            after = [c for c in candidates if c[0] > fi]
            if after:
                return min(after, key=lambda c: c[0])[2].lstrip("#")
        if len(candidates) == 1:
            return candidates[0][2].lstrip("#")
        return None

    def nearest_office(self, seg: ET.Element, focus_id: str) -> Optional[tuple[str, str]]:
        ordered = self.ordered_semantic_elements(seg)
        focus_el = self.event_inline(focus_id, seg)
        fi = ordered.index(focus_el) if focus_el in ordered else -1
        offices = []
        for i, el in enumerate(ordered):
            if el.tag == qn("rs") and (el.get("type") or "").lower() == "officetype" and el.get("ref"):
                offices.append((i, el))
        if not offices:
            return None
        after = [x for x in offices if x[0] > fi]
        chosen = min(after, key=lambda x: x[0]) if after else (offices[0] if len(offices) == 1 else None)
        if not chosen:
            return None
        el = chosen[1]
        return el.get("ref"), text(el)

    def org_principal_and_person_representative(self, seg: ET.Element, focus_id: str) -> tuple[Optional[str], Optional[str]]:
        ordered = self.ordered_semantic_elements(seg)
        focus_el = self.event_inline(focus_id, seg)
        fi = ordered.index(focus_el) if focus_el in ordered else -1
        orgs=[]; persons=[]
        for i, el in enumerate(ordered):
            if el.tag == qn("orgName") and el.get("ref"):
                orgs.append((i,el.get("ref").lstrip("#")))
            if el.tag == qn("persName") and el.get("ref"):
                persons.append((i,el.get("ref").lstrip("#")))
        principals=[x for x in orgs if x[0] < fi]
        reps=[x for x in persons if x[0] > fi]
        principal=max(principals,key=lambda x:x[0])[1] if principals else None
        # RepresentationRelation currently expects one representative in the profile.
        representative=reps[0][1] if len(reps)==1 else None
        return principal, representative

    def write(self, out: Path):
        out.parent.mkdir(parents=True, exist_ok=True)
        rev = self.root.find(".//tei:revisionDesc", NS)
        if rev is not None:
            ET.SubElement(rev, qn("change"), {
                "when": "2026-08-31",
                "type": "quality-review-application"
            }).text = "Aplicación reproducible de decisiones humanas aprobadas del triage QUALITY de LeCO."
        try:
            ET.indent(self.tree, space="  ")
        except AttributeError:
            pass
        self.tree.write(out, encoding="utf-8", xml_declaration=True)


def load_reviews(path: Path) -> list[dict[str,str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def apply_row(cur: TEICurator, row: dict[str,str], rownum: int) -> Result:
    doc = row["document"]
    status = row["review_status"]
    path = row.get("result_path", "") or ""
    focus_uri = row.get("focus_node", "") or ""
    focus_id = local_from_uri(focus_uri)
    evidence = row.get("evidence_xml_ids", "") or ""
    note = row.get("reviewer_note", "") or ""
    subtype = "explicit" if status == "explicit_recoverable" else "inferred"
    conf = None if subtype == "explicit" else parse_confidence(note, 0.80)
    base = Result(rownum, doc, status, path or "(participant)", focus_uri, evidence, "pending")
    seg = cur.segment(evidence)
    if status not in APPLY_STATUSES:
        base.outcome = "not_applied_by_policy"
        base.reason = f"review_status={status}"
        return base
    if not focus_id or focus_id not in cur.id_index:
        base.reason = "focus_node no resuelve a xml:id en TEI enriquecido"
        return base
    if seg is None:
        base.reason = "segmento de evidencia no encontrado"
        return base

    prop = path.replace("leco:", "") if path else "hasParticipant"
    rid = f"review_{rownum:04d}_{prop}"

    # 1) Participants. Apply only when a subject-like entity is resolvable.
    if not path:
        target = cur.named_target_from_note(note, tags=("person","org"))
        if not target:
            target = cur.unique_entity(seg, tag_preference="person")
        if not target:
            target = cur.unique_entity(seg, tag_preference="org")
        if not target:
            base.reason = "no se pudo resolver un participante único/nombrado sin análisis gramatical adicional"
            return base
        ok, relid = cur.add_object_relation(rid, "hasParticipant", focus_id, target, evidence, subtype, conf)
        base.outcome = "applied" if ok else "already_present"
        base.relation_xml_id = relid
        base.target = target
        return base

    # 2) Authority that decided the act.
    if prop == "decidedBy":
        target = cur.named_target_from_note(note, tags=("org","person"))
        if not target:
            target = cur.unique_entity(seg, tag_preference="org")
        if not target:
            target = cur.unique_entity(seg, tag_preference="person")
        if not target:
            base.reason = "autoridad decisora no resoluble a una entidad única/nombrada sin conjetura adicional"
            return base
        ok, relid = cur.add_object_relation(rid, "decidedBy", focus_id, target, evidence, subtype, conf)
        base.outcome = "applied" if ok else "already_present"; base.relation_xml_id=relid; base.target=target
        return base

    # 3) Investigated/sanctioned/appointed person.
    if prop in {"investigates", "sanctions", "appointsPerson"}:
        target = cur.named_target_from_note(note, tags=("person","org"))
        if not target:
            target = cur.unique_entity(seg, tag_preference="person")
        if not target and prop != "appointsPerson":
            target = cur.unique_entity(seg, tag_preference="org")
        if not target:
            base.reason = f"objeto de {prop} no resoluble a una entidad única/nombrada"
            return base
        ok, relid = cur.add_object_relation(rid, prop, focus_id, target, evidence, subtype, conf)
        base.outcome = "applied" if ok else "already_present"; base.relation_xml_id=relid; base.target=target
        return base

    # 4) Appointment office: mint an Office individual preserving historical label.
    if prop == "appointsToOffice":
        office = cur.nearest_office(seg, focus_id)
        if not office:
            base.reason = "mención de oficio no resoluble en el segmento"
            return base
        office_type, label = office
        office_id = f"review_office_{rownum:04d}"
        cur.add_helper("offices", office_id, label, office_type)
        ok, relid = cur.add_object_relation(rid, prop, focus_id, office_id, evidence, subtype, conf)
        base.outcome = "applied" if ok else "already_present"; base.relation_xml_id=relid; base.target=office_id
        return base

    # 5) Historical concept time inherited from document date.
    if prop == "conceptUseTime":
        relation = cur.id_index.get(focus_id)
        date = cur.document_date()
        if relation is None or relation.tag != qn("relation") or not date:
            base.reason = "no se pudo heredar una fecha documental fiable"
            return base
        if relation.get("when"):
            base.outcome = "already_present"; base.target=relation.get("when") or ""
            return base
        relation.set("when", date)
        cur.ensure_precision(focus_id, conf or 0.90)
        base.outcome = "applied"; base.relation_xml_id=focus_id; base.target=date
        return base

    # 6) Repartimiento: mint a generic legal arrangement, without adding parties/scopes.
    if prop == "resultsInLegalArrangement":
        arr_id = f"review_arrangement_{rownum:04d}"
        cur.add_helper("legalArrangements", arr_id, f"Arreglo jurídico asociado a {text(cur.id_index.get(focus_id)) or row.get('focus_label','acto')}", LECO + "LegalArrangement")
        ok, relid = cur.add_object_relation(rid, prop, focus_id, arr_id, evidence, subtype, conf)
        base.outcome = "applied" if ok else "already_present"; base.relation_xml_id=relid; base.target=arr_id
        return base

    # 7) Grant of power is kept for a dedicated representation review pass.
    # The current STRICT/Core model expects a single principal and a single
    # representative. Some colonial powers in the corpus appoint several
    # procuradores, so silently choosing one would distort the source.
    if prop == "createsRepresentation":
        base.outcome = "deferred"
        base.reason = "requiere resolver principal(es)/representante(s) y revisar multiplicidad antes de crear RepresentationRelation"
        return base

    # 8) Jurisdiction is deliberately deferred. Many cases disappear once authority
    # relations are recovered and tei_to_rdf derived rules run.
    if prop in {"withinJurisdiction", "conceptUseJurisdiction"}:
        base.outcome = "deferred"
        base.reason = "recalcular tras recuperar autoridades; no crear jurisdicción redundante desde el CSV"
        return base

    # Appeals/beforeAuthority in this reviewed ledger are normally keep_warning and
    # should not reach this branch; unknown properties remain pending.
    base.reason = f"sin regla automática segura para {prop}"
    return base


def metadata_date_for(documents_dir: Path, doc: str) -> Optional[str]:
    p = documents_dir / doc / "metadata.json"
    if not p.exists():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    for key in ("date_asserted_in_scope_and_content", "date", "normalized_date", "document_date"):
        value = obj.get(key)
        if isinstance(value, str) and re.match(r"^\d{4}(-\d{2}(-\d{2})?)?$", value.strip()):
            return value.strip()
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviews", type=Path, default=Path("reviews/quality/quality_triage_reviewed.csv"))
    ap.add_argument("--input-dir", type=Path, default=Path("build/tei_enriched"))
    ap.add_argument("--output-dir", type=Path, default=Path("build/tei_curated"))
    ap.add_argument("--documents-dir", type=Path, default=Path("data/documents"), help="Fuente de metadata.json para contexto temporal cuando el TEI no contiene fecha normalizada")
    ap.add_argument("--report", type=Path, default=Path("build/quality_review_application.csv"))
    ap.add_argument("--pending", type=Path, default=Path("build/quality_review_application_pending.csv"))
    ap.add_argument("--json", type=Path, default=Path("build/quality_review_application.json"))
    args = ap.parse_args()

    reviews = load_reviews(args.reviews)
    by_doc: dict[str, list[tuple[int,dict[str,str]]]] = {}
    for i, row in enumerate(reviews, start=2):
        by_doc.setdefault(row["document"], []).append((i,row))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results: list[Result] = []
    docs_written = 0
    input_docs = {p.stem: p for p in args.input_dir.glob("*.xml") if p.is_file()}
    all_docs = sorted(set(input_docs) | set(by_doc))
    for doc in all_docs:
        doc_rows = by_doc.get(doc, [])
        src = input_docs.get(doc)
        if src is None:
            for rownum,row in doc_rows:
                results.append(Result(rownum, doc, row.get("review_status",""), row.get("result_path","") or "(participant)", row.get("focus_node",""), row.get("evidence_xml_ids",""), "pending", reason="TEI enriquecido no encontrado"))
            continue
        cur = TEICurator(src, metadata_date=metadata_date_for(args.documents_dir, doc))
        for rownum,row in doc_rows:
            results.append(apply_row(cur,row,rownum))
        cur.write(args.output_dir / f"{doc}.xml")
        docs_written += 1

    fields = list(Result.__dataclass_fields__.keys())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(asdict(r) for r in results)
    pending=[r for r in results if r.outcome in {"pending","deferred"}]
    with args.pending.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(asdict(r) for r in pending)

    counts={}
    for r in results: counts[r.outcome]=counts.get(r.outcome,0)+1
    payload={"documents_written":docs_written,"review_rows":len(results),"outcomes":counts,"pending_or_deferred":len(pending)}
    args.json.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print("LeCO QUALITY review application")
    print(f"Documents written: {docs_written}")
    print(f"Review rows: {len(results)}")
    for k,v in sorted(counts.items()): print(f"  {k}: {v}")
    print(f"Curated TEI: {args.output_dir}")
    print(f"Audit report: {args.report}")
    print(f"Pending/deferred: {args.pending}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
