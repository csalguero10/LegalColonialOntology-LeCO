#!/usr/bin/env python3
"""Audit high-value LeCO QUALITY relationship warnings against TEI evidence.

Read-only diagnostic stage. It targets exactly these QUALITY properties:

  leco:decidedBy
  leco:sanctions
  leco:appointsPerson
  leco:appointsToOffice
  leco:appealsAgainst
  leco:beforeAuthority

For every warning it links the RDF focus node to its TEI segment, neighboring
segments, and exact candidate xml:ids. It never modifies TEI or RDF and never
selects a target automatically.

Defaults are for the participant-curated stage of the repository:
  build/shacl_quality_participant_analysis.csv
  build/tei_participant_curated/*.xml
  build/rdf_participant_curated/*.ttl

Outputs:
  build/legal_relation_audit.csv
  build/legal_relation_audit_review_queue.csv
  build/legal_relation_audit.json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI, "xml": XML}
XML_ID = f"{{{XML}}}id"
LECO = Namespace("https://w3id.org/leco/ontology#")

TARGET_PATHS = {
    "leco:decidedBy": "authority",
    "leco:sanctions": "person_or_collective",
    "leco:appointsPerson": "person",
    "leco:appointsToOffice": "office",
    "leco:appealsAgainst": "legal_decision",
    "leco:beforeAuthority": "authority",
}

SUGGESTIONS = {
    "leco:decidedBy": "Identificar la autoridad que adopta la decisión. Distinguir autoridad decisora de beneficiario, destinatario o persona mencionada.",
    "leco:sanctions": "Identificar a quién recae la sanción. No usar automáticamente al Cabildo ni a la autoridad que impone la pena.",
    "leco:appointsPerson": "Identificar la persona nombrada. Si el texto solo habla de personas genéricas, conservar el warning.",
    "leco:appointsToOffice": "Identificar el cargo concreto del nombramiento. Aprobar el xml:id de la mención de oficio solo después de confirmar que corresponde a ese nombramiento.",
    "leco:appealsAgainst": "Identificar la decisión/sanción concreta contra la que se apela. No asumir la decisión anterior solo por proximidad si hay más de una candidata.",
    "leco:beforeAuthority": "Identificar la autoridad ante la cual se presenta la apelación o actuación. Preferir mención explícita; si es contextual, registrar confidence.",
}


def qn(local: str) -> str:
    return f"{{{TEI}}}{local}"


def norm_text(el: Optional[ET.Element]) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def local_name(uri: str) -> str:
    return (uri or "").rstrip("/").rsplit("/", 1)[-1]


def compact(term) -> str:
    if term is None:
        return ""
    s = str(term)
    if s.startswith(str(LECO)):
        return "leco:" + s[len(str(LECO)):]
    return s


def split_ptrs(value: Optional[str]) -> list[str]:
    return [x for x in (value or "").split() if x]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def is_target_warning(row: dict[str, str]) -> bool:
    return (row.get("result_path") or "").strip() in TARGET_PATHS


@dataclass
class Candidate:
    kind: str
    xml_id: str
    label: str
    position: str
    semantic_hint: str = ""

    def render(self) -> str:
        parts = [self.kind + ":" + self.xml_id, self.label, self.position]
        if self.semantic_hint:
            parts.append(self.semantic_hint)
        return "|".join(parts)


@dataclass
class AuditRow:
    document: str
    property: str
    target_requirement: str
    focus_node: str
    focus_xml_id: str
    focus_types: str
    focus_label: str
    segment_id: str
    segment_text: str
    previous_segment_id: str
    previous_segment_text: str
    next_segment_id: str
    next_segment_text: str
    same_segment_entities: str
    previous_segment_entities: str
    next_segment_entities: str
    same_segment_events: str
    previous_segment_events: str
    next_segment_events: str
    same_segment_office_mentions: str
    previous_segment_office_mentions: str
    next_segment_office_mentions: str
    current_property_targets: str
    suggested_review_action: str
    approved_target_xml_id: str
    approved_basis: str
    approved_confidence: str
    relation_review_status: str
    relation_reviewer_note: str


class TEIContext:
    def __init__(self, path: Path):
        self.path = path
        self.tree = ET.parse(path)
        self.root = self.tree.getroot()
        self.index = {el.get(XML_ID): el for el in self.root.iter() if el.get(XML_ID)}
        self.segments = [el for el in self.root.findall(".//tei:body//tei:seg", NS) if el.get(XML_ID)]
        self.segment_pos = {el.get(XML_ID): i for i, el in enumerate(self.segments)}

        self.entity_labels: dict[str, tuple[str, str]] = {}
        for p in self.root.findall(".//tei:standOff//tei:listPerson/tei:person[@xml:id]", NS):
            self.entity_labels[p.get(XML_ID)] = ("person", norm_text(p.find("tei:persName", NS)))
        for o in self.root.findall(".//tei:standOff//tei:listOrg/tei:org[@xml:id]", NS):
            self.entity_labels[o.get(XML_ID)] = ("org", norm_text(o.find("tei:orgName", NS)))

        self.events: dict[str, ET.Element] = {
            e.get(XML_ID): e for e in self.root.findall(".//tei:standOff//tei:listEvent/tei:event[@xml:id]", NS)
        }

    def segment_for_focus(self, focus_id: str) -> Optional[ET.Element]:
        event = self.events.get(focus_id) or self.index.get(focus_id)
        if event is not None and event.tag == qn("event"):
            corresp = (event.get("corresp") or "").strip()
            if corresp.startswith("#"):
                seg = self.index.get(corresp[1:])
                if seg is not None and seg.tag == qn("seg"):
                    return seg
        m = re.search(r"(cab-\d{3}-\d{3}_s\d+)", focus_id)
        if m:
            seg = self.index.get(m.group(1))
            if seg is not None and seg.tag == qn("seg"):
                return seg
        return None

    def neighbors(self, seg: ET.Element) -> tuple[Optional[ET.Element], Optional[ET.Element]]:
        i = self.segment_pos.get(seg.get(XML_ID), -1)
        prev = self.segments[i - 1] if i > 0 else None
        nxt = self.segments[i + 1] if 0 <= i < len(self.segments) - 1 else None
        return prev, nxt

    def _semantic_elements(self, seg: ET.Element) -> list[ET.Element]:
        return [
            el for el in seg.iter()
            if el.tag in {qn("persName"), qn("orgName"), qn("rs"), qn("term")}
        ]

    def _focus_inline_index(self, seg: ET.Element, focus_id: str) -> Optional[int]:
        sem = self._semantic_elements(seg)
        for i, el in enumerate(sem):
            if el.tag == qn("rs") and (el.get("corresp") or "") == f"#{focus_id}":
                return i
        return None

    def entities(self, seg: Optional[ET.Element], focus_id: str = "") -> list[Candidate]:
        if seg is None:
            return []
        sem = self._semantic_elements(seg)
        fi = self._focus_inline_index(seg, focus_id) if focus_id else None
        out: list[Candidate] = []
        for i, el in enumerate(sem):
            if el.tag not in {qn("persName"), qn("orgName")}:
                continue
            ref = (el.get("ref") or "").strip()
            if not ref.startswith("#"):
                continue
            target = ref[1:]
            pos = "same"
            if fi is not None:
                pos = "before" if i < fi else "after" if i > fi else "same"
            out.append(Candidate(
                "person" if el.tag == qn("persName") else "org",
                target,
                norm_text(el),
                pos,
                el.get("type") or "",
            ))
        return out

    def office_mentions(self, seg: Optional[ET.Element], focus_id: str = "") -> list[Candidate]:
        if seg is None:
            return []
        sem = self._semantic_elements(seg)
        fi = self._focus_inline_index(seg, focus_id) if focus_id else None
        out: list[Candidate] = []
        for i, el in enumerate(sem):
            if el.tag != qn("rs") or not el.get(XML_ID):
                continue
            typ = (el.get("type") or "").lower()
            subtype = (el.get("subtype") or "").lower()
            if typ not in {"officetype", "role_or_office"} and "office" not in subtype:
                continue
            pos = "same"
            if fi is not None:
                pos = "before" if i < fi else "after" if i > fi else "same"
            hint = el.get("ref") or el.get("ana") or subtype
            out.append(Candidate("officeMention", el.get(XML_ID), norm_text(el), pos, hint))
        return out

    def events_in_segment(self, seg: Optional[ET.Element], focus_id: str = "") -> list[Candidate]:
        if seg is None:
            return []
        sid = seg.get(XML_ID)
        out: list[Candidate] = []
        for eid, event in self.events.items():
            if eid == focus_id:
                continue
            if (event.get("corresp") or "") != f"#{sid}":
                continue
            ana = event.get("ana") or ""
            out.append(Candidate("event", eid, norm_text(event.find("tei:desc", NS)), "same", ana))
        return out

    def events_for_neighbor(self, seg: Optional[ET.Element]) -> list[Candidate]:
        return self.events_in_segment(seg, "")


def graph_types(g: Graph, node: URIRef) -> str:
    vals = [compact(x) for x in g.objects(node, RDF.type)]
    return " | ".join(dict.fromkeys(vals))


def graph_label(g: Graph, node: URIRef) -> str:
    vals = [str(x) for x in g.objects(node, RDFS.label)]
    if not vals:
        vals = [str(x) for x in g.objects(node, LECO.lexicalForm)]
    return " | ".join(dict.fromkeys(vals))


def rdf_predicate(path: str) -> URIRef:
    if not path.startswith("leco:"):
        raise ValueError(path)
    return LECO[path.split(":", 1)[1]]


def current_targets(g: Graph, node: URIRef, path: str) -> list[str]:
    vals = []
    for obj in g.objects(node, rdf_predicate(path)):
        if isinstance(obj, URIRef):
            vals.append(local_name(str(obj)))
        else:
            vals.append(str(obj))
    return list(dict.fromkeys(vals))


def render(items: list[Candidate]) -> str:
    return "; ".join(x.render() for x in items)


def review_queue_reason(row: AuditRow) -> str:
    # All rows are reviewable; this helper is kept to make future filtering easy.
    return "pending"


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", type=Path, default=Path("build/shacl_quality_participant_analysis.csv"))
    ap.add_argument("--tei-dir", type=Path, default=Path("build/tei_participant_curated"))
    ap.add_argument("--rdf-dir", type=Path, default=Path("build/rdf_participant_curated"))
    ap.add_argument("--output", type=Path, default=Path("build/legal_relation_audit.csv"))
    ap.add_argument("--queue-output", type=Path, default=Path("build/legal_relation_audit_review_queue.csv"))
    ap.add_argument("--json-output", type=Path, default=Path("build/legal_relation_audit.json"))
    args = ap.parse_args(argv)

    rows = [r for r in read_csv(args.analysis) if is_target_warning(r)]
    tei_cache: dict[str, TEIContext] = {}
    rdf_cache: dict[str, Graph] = {}
    output: list[AuditRow] = []

    for src in rows:
        doc = src["document"]
        tei_path = args.tei_dir / f"{doc}.xml"
        rdf_path = args.rdf_dir / f"{doc}.ttl"
        if not tei_path.exists():
            raise FileNotFoundError(f"No existe TEI curado: {tei_path}")
        if not rdf_path.exists():
            raise FileNotFoundError(f"No existe RDF curado: {rdf_path}")
        ctx = tei_cache.setdefault(doc, TEIContext(tei_path))
        if doc not in rdf_cache:
            rdf_cache[doc] = Graph().parse(rdf_path, format="turtle")
        g = rdf_cache[doc]

        focus_uri = URIRef(src["focus_node"])
        focus_id = local_name(src["focus_node"])
        seg = ctx.segment_for_focus(focus_id)
        prev, nxt = ctx.neighbors(seg) if seg is not None else (None, None)
        path = (src.get("result_path") or "").strip()

        same_entities = ctx.entities(seg, focus_id)
        prev_entities = ctx.entities(prev)
        next_entities = ctx.entities(nxt)
        same_events = ctx.events_in_segment(seg, focus_id)
        prev_events = ctx.events_for_neighbor(prev)
        next_events = ctx.events_for_neighbor(nxt)
        same_offices = ctx.office_mentions(seg, focus_id)
        prev_offices = ctx.office_mentions(prev)
        next_offices = ctx.office_mentions(nxt)

        output.append(AuditRow(
            document=doc,
            property=path,
            target_requirement=TARGET_PATHS[path],
            focus_node=src["focus_node"],
            focus_xml_id=focus_id,
            focus_types=graph_types(g, focus_uri),
            focus_label=graph_label(g, focus_uri),
            segment_id=seg.get(XML_ID) if seg is not None else "",
            segment_text=norm_text(seg),
            previous_segment_id=prev.get(XML_ID) if prev is not None else "",
            previous_segment_text=norm_text(prev),
            next_segment_id=nxt.get(XML_ID) if nxt is not None else "",
            next_segment_text=norm_text(nxt),
            same_segment_entities=render(same_entities),
            previous_segment_entities=render(prev_entities),
            next_segment_entities=render(next_entities),
            same_segment_events=render(same_events),
            previous_segment_events=render(prev_events),
            next_segment_events=render(next_events),
            same_segment_office_mentions=render(same_offices),
            previous_segment_office_mentions=render(prev_offices),
            next_segment_office_mentions=render(next_offices),
            current_property_targets="; ".join(current_targets(g, focus_uri, path)),
            suggested_review_action=SUGGESTIONS[path],
            approved_target_xml_id="",
            approved_basis="",
            approved_confidence="",
            relation_review_status="pending",
            relation_reviewer_note="",
        ))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(AuditRow.__dataclass_fields__.keys())
    for path in (args.output, args.queue_output):
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(asdict(r) for r in output)

    by_property = Counter(r.property for r in output)
    payload = {
        "warnings": len(output),
        "by_property": dict(sorted(by_property.items())),
        "inputs": {
            "analysis": str(args.analysis),
            "tei_dir": str(args.tei_dir),
            "rdf_dir": str(args.rdf_dir),
        },
        "outputs": {
            "detail": str(args.output),
            "review_queue": str(args.queue_output),
        },
    }
    args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("LeCO legal-relation evidence audit")
    print(f"Warnings selected: {len(output)}")
    for prop, n in by_property.most_common():
        print(f"  {n:>3} × {prop}")
    print("\nNo TEI/RDF was modified.")
    print(f"Detail: {args.output}")
    print(f"Review queue: {args.queue_output}")
    print(f"JSON: {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
