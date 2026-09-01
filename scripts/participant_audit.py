#!/usr/bin/env python3
"""Audit participant resolutions for LeCO QUALITY warnings.

This is a read-only diagnostic pass. It deliberately audits *all* original
participant warnings, including those that appear resolved in the current RDF,
because previous heuristic target resolution may have selected the wrong entity.

Default inputs, from repository root:
  reviews/quality/quality_triage_reviewed.csv
  build/tei_curated/*.xml
  build/rdf_curated_inferred/*.ttl

Default outputs:
  build/participant_audit.csv
  build/participant_audit_unresolved.csv
  build/participant_audit.json

No TEI or RDF is modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI, "xml": XML}
XML_ID = f"{{{XML}}}id"
LECO = Namespace("https://w3id.org/leco/ontology#")


def qn(local: str) -> str:
    return f"{{{TEI}}}{local}"


def text(el: Optional[ET.Element]) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def local(uri: str) -> str:
    return (uri or "").rstrip("/").rsplit("/", 1)[-1]


def compact(term) -> str:
    if term is None:
        return ""
    s = str(term)
    base = str(LECO)
    return "leco:" + s[len(base):] if s.startswith(base) else s


def is_participant_warning(row: dict[str, str]) -> bool:
    constraint = row.get("constraint", "") or ""
    path = (row.get("result_path", "") or "").strip()
    msg = (row.get("message", "") or "").lower()
    return (not path and constraint.endswith("OrConstraintComponent")) or (
        not path and "participante" in msg
    )


@dataclass
class EntityMention:
    xml_id: str
    target_id: str
    kind: str
    label: str
    position: str

    def render(self) -> str:
        return f"{self.kind}:{self.target_id}|{self.label}|{self.position}"


@dataclass
class AuditRow:
    document: str
    focus_node: str
    focus_type: str
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
    current_hasParticipant: str
    current_participationActors: str
    current_resolution_status: str
    audit_flag: str
    original_review_status: str
    original_reviewer_note: str
    suggested_review_action: str
    approved_target_xml_id: str
    approved_basis: str
    approved_confidence: str
    participant_review_status: str
    participant_reviewer_note: str


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
            self.entity_labels[p.get(XML_ID)] = ("person", text(p.find("tei:persName", NS)))
        for o in self.root.findall(".//tei:standOff//tei:listOrg/tei:org[@xml:id]", NS):
            self.entity_labels[o.get(XML_ID)] = ("org", text(o.find("tei:orgName", NS)))

    def event_inline(self, focus_id: str, seg: ET.Element) -> Optional[ET.Element]:
        for rs in seg.iter(qn("rs")):
            if rs.get("corresp") == f"#{focus_id}":
                return rs
        return None

    def segment_for_focus(self, focus_id: str) -> Optional[ET.Element]:
        event = self.index.get(focus_id)
        if event is not None and event.tag == qn("event"):
            corresp = event.get("corresp", "")
            if corresp.startswith("#"):
                seg = self.index.get(corresp[1:])
                if seg is not None and seg.tag == qn("seg"):
                    return seg
        # fallback from generated event id containing source segment id
        m = re.search(r"(cab-\d{3}-\d{3}_s\d+)", focus_id)
        if m:
            seg = self.index.get(m.group(1))
            if seg is not None and seg.tag == qn("seg"):
                return seg
        return None

    def neighbors(self, seg: ET.Element) -> tuple[Optional[ET.Element], Optional[ET.Element]]:
        sid = seg.get(XML_ID)
        i = self.segment_pos.get(sid, -1)
        prev = self.segments[i - 1] if i > 0 else None
        nxt = self.segments[i + 1] if 0 <= i < len(self.segments) - 1 else None
        return prev, nxt

    def mentions(self, seg: Optional[ET.Element], focus_id: Optional[str] = None) -> list[EntityMention]:
        if seg is None:
            return []
        focus_el = self.event_inline(focus_id, seg) if focus_id else None
        semantic = [el for el in seg.iter() if el.tag in {qn("persName"), qn("orgName"), qn("rs"), qn("term")}]
        fi = semantic.index(focus_el) if focus_el is not None and focus_el in semantic else None
        out: list[EntityMention] = []
        for i, el in enumerate(semantic):
            if el.tag not in {qn("persName"), qn("orgName")}:
                continue
            ref = (el.get("ref") or "").strip()
            if not ref.startswith("#"):
                continue
            target = ref[1:]
            kind = "person" if el.tag == qn("persName") else "org"
            pos = "same"
            if fi is not None:
                pos = "before" if i < fi else "after" if i > fi else "same"
            out.append(EntityMention(el.get(XML_ID) or "", target, kind, text(el), pos))
        return out

    def label_for(self, target_id: str) -> str:
        kind, label = self.entity_labels.get(target_id, ("entity", target_id))
        return f"{kind}:{target_id}|{label}"


def graph_types(g: Graph, node: URIRef) -> str:
    vals = [compact(t) for t in g.objects(node, RDF.type)]
    return " | ".join(dict.fromkeys(vals))


def graph_label(g: Graph, node: URIRef) -> str:
    vals = [str(v) for v in g.objects(node, RDFS.label)]
    if not vals:
        vals = [str(v) for v in g.objects(node, LECO.lexicalForm)]
    return " | ".join(dict.fromkeys(vals))


def current_participants(g: Graph, focus: URIRef) -> tuple[list[str], list[str]]:
    direct = [local(str(x)) for x in g.objects(focus, LECO.hasParticipant) if isinstance(x, URIRef)]
    actors: list[str] = []
    for participation in g.objects(focus, LECO.hasParticipation):
        for actor in g.objects(participation, LECO.participationActor):
            if isinstance(actor, URIRef):
                actors.append(local(str(actor)))
    # Some datasets only contain participationInAct in the reverse direction.
    for participation in g.subjects(LECO.participationInAct, focus):
        for actor in g.objects(participation, LECO.participationActor):
            if isinstance(actor, URIRef):
                actors.append(local(str(actor)))
    return list(dict.fromkeys(direct)), list(dict.fromkeys(actors))


def flag_resolution(current: list[str], same: list[EntityMention], prev: list[EntityMention], nxt: list[EntityMention]) -> tuple[str, str]:
    current = list(dict.fromkeys(current))
    if not current:
        return "unresolved", "Revisar candidatos del mismo segmento y, si no bastan, el contexto anterior/posterior."
    if len(current) > 1:
        return "multiple_current_targets", "Verificar si la pluralidad está justificada o si alguna relación fue añadida heurísticamente."
    target = current[0]
    same_hits = [m for m in same if m.target_id == target]
    if same_hits:
        positions = {m.position for m in same_hits}
        if positions == {"before"}:
            return "resolved_same_segment_before", "Comprobar que la mención anterior al acto funciona realmente como actor/participante y no como autoridad/destinatario."
        if positions == {"after"}:
            return "resolved_same_segment_after_REVIEW", "Target situado después del acto: revisar especialmente; puede ser objeto/destinatario y no participante actoral."
        return "resolved_same_segment", "Verificar la función semántica de la entidad en el acto."
    if any(m.target_id == target for m in prev):
        return "resolved_previous_context", "Relación contextual: confirmar continuidad discursiva y conservar provenance/confidence."
    if any(m.target_id == target for m in nxt):
        return "resolved_next_context_REVIEW", "Target solo aparece en el segmento siguiente; requiere revisión humana cuidadosa."
    return "resolved_target_not_in_local_context_REVIEW", "El target actual no aparece en el segmento ni en sus vecinos: posible resolución heurística incorrecta."


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviews", type=Path, default=Path("reviews/quality/quality_triage_reviewed.csv"))
    ap.add_argument("--tei-dir", type=Path, default=Path("build/tei_curated"))
    ap.add_argument("--rdf-dir", type=Path, default=Path("build/rdf_curated_inferred"))
    ap.add_argument("--output", type=Path, default=Path("build/participant_audit.csv"))
    ap.add_argument("--unresolved-output", type=Path, default=Path("build/participant_audit_unresolved.csv"))
    ap.add_argument("--json-output", type=Path, default=Path("build/participant_audit.json"))
    args = ap.parse_args()

    source = [r for r in read_rows(args.reviews) if is_participant_warning(r)]
    out: list[AuditRow] = []
    graph_cache: dict[str, Graph] = {}
    tei_cache: dict[str, TEIContext] = {}

    for r in source:
        doc = r["document"]
        tei_path = args.tei_dir / f"{doc}.xml"
        rdf_path = args.rdf_dir / f"{doc}.ttl"
        if doc not in tei_cache:
            tei_cache[doc] = TEIContext(tei_path)
        if doc not in graph_cache:
            graph_cache[doc] = Graph().parse(rdf_path, format="turtle")
        ctx = tei_cache[doc]
        g = graph_cache[doc]
        focus_uri = r.get("focus_node", "")
        focus = URIRef(focus_uri)
        fid = local(focus_uri)
        seg = ctx.segment_for_focus(fid)
        prev, nxt = ctx.neighbors(seg) if seg is not None else (None, None)
        same_mentions = ctx.mentions(seg, fid)
        prev_mentions = ctx.mentions(prev)
        next_mentions = ctx.mentions(nxt)
        direct, actors = current_participants(g, focus)
        all_current = list(dict.fromkeys(direct + actors))
        flag, action = flag_resolution(all_current, same_mentions, prev_mentions, next_mentions)

        def rendered(ids: list[str]) -> str:
            return "; ".join(ctx.label_for(x) for x in ids)

        out.append(AuditRow(
            document=doc,
            focus_node=focus_uri,
            focus_type=graph_types(g, focus),
            focus_label=graph_label(g, focus) or r.get("focus_label", ""),
            segment_id=seg.get(XML_ID) if seg is not None else "",
            segment_text=text(seg),
            previous_segment_id=prev.get(XML_ID) if prev is not None else "",
            previous_segment_text=text(prev),
            next_segment_id=nxt.get(XML_ID) if nxt is not None else "",
            next_segment_text=text(nxt),
            same_segment_entities="; ".join(m.render() for m in same_mentions),
            previous_segment_entities="; ".join(m.render() for m in prev_mentions),
            next_segment_entities="; ".join(m.render() for m in next_mentions),
            current_hasParticipant=rendered(direct),
            current_participationActors=rendered(actors),
            current_resolution_status="resolved" if all_current else "unresolved",
            audit_flag=flag,
            original_review_status=r.get("review_status", ""),
            original_reviewer_note=r.get("reviewer_note", ""),
            suggested_review_action=action,
            approved_target_xml_id="",
            approved_basis="",
            approved_confidence="",
            participant_review_status="pending",
            participant_reviewer_note="",
        ))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(AuditRow.__dataclass_fields__.keys())
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(asdict(x) for x in out)
    unresolved = [x for x in out if x.current_resolution_status == "unresolved" or "REVIEW" in x.audit_flag or x.audit_flag == "multiple_current_targets"]
    with args.unresolved_output.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(asdict(x) for x in unresolved)

    from collections import Counter
    flags = Counter(x.audit_flag for x in out)
    payload = {
        "participant_warnings_original": len(out),
        "currently_resolved": sum(x.current_resolution_status == "resolved" for x in out),
        "currently_unresolved": sum(x.current_resolution_status == "unresolved" for x in out),
        "review_queue": len(unresolved),
        "audit_flags": dict(sorted(flags.items())),
    }
    args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("LeCO participant audit")
    print(f"Original participant warnings: {payload['participant_warnings_original']}")
    print(f"Currently resolved: {payload['currently_resolved']}")
    print(f"Currently unresolved: {payload['currently_unresolved']}")
    print(f"Review queue (unresolved or suspicious): {payload['review_queue']}")
    for k, v in flags.most_common():
        print(f"  {v:3d} × {k}")
    print(f"Audit CSV: {args.output}")
    print(f"Review queue: {args.unresolved_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
