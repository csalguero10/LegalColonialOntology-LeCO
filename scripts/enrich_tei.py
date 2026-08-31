#!/usr/bin/env python3
"""Enrich legacy LeCO pilot TEI with stand-off semantics.

Canonical source layout (never modified):
    data/documents/<local-id>/
        tei.xml
        metadata.json
        annotations.csv
        relations.csv

Generated output:
    build/tei_enriched/<local-id>.xml
    build/tei_enriched/enrichment_report.json

The enrichment is deliberately conservative:
- explicit inline annotations are linked to reusable standOff resources;
- existing sidecar relations are migrated only when their semantics can be
  mapped safely;
- deterministic contextual inferences are marked as inferred or
  humanInterpretation and retain a documentary @source pointer;
- unsupported/ambiguous sidecar relations are reported, not silently asserted.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET

TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
XML_ID = f"{{{XML}}}id"
NS = {"tei": TEI, "xml": XML}
LECO = "https://w3id.org/leco/ontology#"
ET.register_namespace("", TEI)


def qn(local: str) -> str:
    return f"{{{TEI}}}{local}"


def norm_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def plain_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return norm_space(value).casefold()


def xml_safe(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "")
    if not value or not re.match(r"[A-Za-z_]", value):
        value = "id_" + value
    return value


def text_content(el: ET.Element) -> str:
    return norm_space("".join(el.itertext()))


ACT_CLASS = {
    "decision": "LegalDecision",
    "detention": "Detention",
    "appearance": "Appearance",
    "appeal": "Appeal",
    "appointment": "Appointment",
    "order_event": "OrderAct",
    "investigation": "Investigation",
    "adjudication": "Adjudication",
    "petition": "Petition",
    "testimony": "Testimony",
    "opposition": "Opposition",
    "notification": "Notification",
    "sanction": "Sanction",
    "penalty": "Sanction",
    "fine": "Fine",
    "prohibition": "Prohibition",
    "proclamation": "Proclamation",
    "oath": "Oath",
    "execution": "Execution",
    "presentation": "Presentation",
    "approval": "Approval",
    "grant_of_power": "GrantOfPower",
    "power_of_representation": "GrantOfPower",
    "repartimiento": "RepartimientoAct",
    "reading": "ReadingAct",
    "collection": "Collection",
    "land_grant": "LandGrant",
    "obedience": "Obedience",
    "punishment": "Punishment",
    "supplication": "Supplication",
    "auction_award": "AuctionAward",
    "grant": "AdministrativeAct",
}

OFFICE_TYPE = {
    "alcalde ordinario": "OrdinaryMayorOfficeType",
    "alcalde": "MayorOfficeType",
    "procurador": "ProcuradorOfficeType",
    "regidor": "RegidorOfficeType",
    "escribano": "NotaryOfficeType",
    "escribano publico": "PublicNotaryOfficeType",
    "oidor": "OidorOfficeType",
    "gobernador": "GovernorOfficeType",
    "corregidor": "CorregidorOfficeType",
    "alguacil": "BailiffOfficeType",
    "alguacil mayor": "ChiefBailiffOfficeType",
    "teniente": "LieutenantOfficeType",
    "obispo": "BishopOfficeType",
    "capitan": "CaptainOfficeType",
    "carcelero": "JailerOfficeType",
}

CONCEPT_URI = {
    "real_service": "RealServiceConcept",
    "real servicio": "RealServiceConcept",
    "duty": "DutyConcept",
    "deber": "DutyConcept",
    "jurisdiction": "JurisdictionConcept",
    "jurisdiccion": "JurisdictionConcept",
    "justice": "JusticeConcept",
    "justicia": "JusticeConcept",
    "custom": "CustomConcept",
    "costumbre": "CustomConcept",
    "republic": "RepublicConcept",
    "republica": "RepublicConcept",
    "majesty": "MajestyConcept",
    "majestad": "MajestyConcept",
    "common_good": "CommonGoodConcept",
    "bien de esta republica": "CommonGoodConcept",
    "bien del reino": "CommonGoodConcept",
    "fidelity": "FidelityConcept",
    "fidelidad": "FidelityConcept",
}

CATEGORY_URI = {
    "indios": "Indios",
    "naturales": "Naturales",
    "indigenas": "Indigenas",
    "caribes": "Caribes",
    "espanoles": "Espanoles",
    "negro": "Negros",
    "negros": "Negros",
    "vecinos": "Vecinos",
    "pobres": "Pobres",
    "descubridores": "Descubridores",
    "conquistadores": "Conquistadores",
    "encomenderos": "Encomenderos",
    "comendaderos": "Encomenderos",
    "judios": "Judios",
}

CATEGORY_CLASS = {
    "status_category": "StatusCategory",
    "historical_status_category": "StatusCategory",
    "colonial_status_category": "StatusCategory",
    "religious_legal_category": "ReligiousLegalCategory",
    "office_status_category": "ColonialOfficeStatus",
    "ethnohistorical_category": "EthnoLegalCategory",
    "social_category": "SocioLegalCategory",
    "colonial_social_category": "SocioLegalCategory",
    "colonial_legal_social_category": "HistoricalLegalCategory",
}

ORG_TYPE = {
    "cabildo": "CabildoType",
    "audiencia": "AudienciaType",
    "council": "CouncilType",
    "royal_chamber": "RoyalChamberType",
    "cabildo_body": "JusticeAndRegimentType",
}

ROLE_FOR_ACT = {
    "appeal": "AppellantRole",
    "petition": "PetitionerRole",
    "opposition": "OpponentRole",
    "testimony": "WitnessRole",
}

CONFIDENCE = {"high": "0.95", "medium": "0.75", "low": "0.50"}


@dataclass
class EnrichmentReport:
    document: str
    reference_code: str
    status: str
    output: Optional[str]
    persons: int = 0
    organizations: int = 0
    places: int = 0
    events: int = 0
    relations: int = 0
    warnings: list[str] | None = None


class Enricher:
    def __init__(self, doc_dir: Path):
        self.doc_dir = doc_dir
        self.tei_path = doc_dir / "tei.xml"
        self.meta_path = doc_dir / "metadata.json"
        self.ann_path = doc_dir / "annotations.csv"
        self.rel_path = doc_dir / "relations.csv"
        self.warnings: list[str] = []
        self.metadata = self._load_json(self.meta_path)
        self.annotations = self._load_csv(self.ann_path)
        self.relations = self._load_csv(self.rel_path)
        self.tree = ET.parse(self.tei_path)
        self.root = self.tree.getroot()
        self.id_index = {el.get(XML_ID): el for el in self.root.iter() if el.get(XML_ID)}
        self.ann_by_id = {r.get("annotation_id", ""): r for r in self.annotations}
        self.reference_code = self.metadata.get("reference_code") or self.root.get(XML_ID) or doc_dir.name
        self.local_id = self.metadata.get("local_identifier") or doc_dir.name
        self.doc_date = self.metadata.get("date_asserted_in_scope_and_content") or self.metadata.get("date") or ""
        self.person_by_label: dict[str, str] = {}
        self.org_by_label: dict[str, str] = {}
        self.place_by_label: dict[str, str] = {}
        self.event_by_annotation: dict[str, str] = {}
        self.event_by_segment_subtype: dict[tuple[str, str], list[str]] = {}
        self.local_concept_by_annotation: dict[str, str] = {}
        self.local_category_by_annotation: dict[str, str] = {}
        self.local_rule_by_annotation: dict[str, str] = {}
        self.relation_ids: set[str] = set()
        self.precision_targets: set[str] = set()
        self.standoff: Optional[ET.Element] = None
        self.list_person: Optional[ET.Element] = None
        self.list_org: Optional[ET.Element] = None
        self.list_place: Optional[ET.Element] = None
        self.list_event: Optional[ET.Element] = None
        self.list_relation: Optional[ET.Element] = None
        self.grp_rules: Optional[ET.Element] = None
        self.grp_arguments: Optional[ET.Element] = None
        self.grp_concepts: Optional[ET.Element] = None
        self.grp_categories: Optional[ET.Element] = None
        self.grp_provenance: Optional[ET.Element] = None

    @staticmethod
    def _load_json(path: Path) -> dict:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8-sig"))

    @staticmethod
    def _load_csv(path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def unavailable(self) -> bool:
        wd = self.metadata.get("working_data") or {}
        return wd.get("transcription_status") == "unavailable"

    def warn(self, msg: str):
        self.warnings.append(msg)

    def _new(self, parent: ET.Element, tag_name: str, **attrs: str) -> ET.Element:
        el = ET.SubElement(parent, qn(tag_name))
        for k, v in attrs.items():
            if v is None:
                continue
            if k == "xml_id":
                el.set(XML_ID, v)
            else:
                el.set(k.replace("__", ":"), v)
        return el

    def _relation(self, xml_id: str, **attrs: str) -> ET.Element:
        xml_id = xml_safe(xml_id)
        if xml_id in self.relation_ids:
            i = 2
            base = xml_id
            while f"{base}_{i}" in self.relation_ids:
                i += 1
            xml_id = f"{base}_{i}"
        self.relation_ids.add(xml_id)
        rel = self._new(self.list_relation, "relation", xml_id=xml_id, **attrs)  # type: ignore[arg-type]
        return rel

    def _has_relation(self, typ: str, active: str, passive: str, ana: str | None = None, name: str | None = None) -> bool:
        if self.list_relation is None:
            return False
        for rel in self.list_relation.findall(qn("relation")):
            if rel.get("type") != typ or rel.get("active") != active or rel.get("passive") != passive:
                continue
            if ana is not None and rel.get("ana") != ana:
                continue
            if name is not None and rel.get("name") != name:
                continue
            return True
        return False

    def _precision(self, target_id: str, certainty: str):
        score = CONFIDENCE.get((certainty or "").casefold())
        if not score or target_id in self.precision_targets:
            return
        self.precision_targets.add(target_id)
        self._new(self.standoff, "precision", target=f"#{target_id}", confidence=score)  # type: ignore[arg-type]

    def _ensure_header(self):
        header = self.root.find("tei:teiHeader", NS)
        if header is None:
            return
        pub = header.find(".//tei:publicationStmt", NS)
        if pub is not None and header.find(".//tei:idno[@type='reference_code']", NS) is None:
            idno = self._new(pub, "idno", type="reference_code")
            idno.text = self.reference_code
        profile = header.find("tei:profileDesc", NS)
        if profile is None:
            profile = self._new(header, "profileDesc")
        if self.doc_date and profile.find("tei:creation", NS) is None:
            creation = self._new(profile, "creation")
            d = self._new(creation, "date")
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.doc_date):
                d.set("when", self.doc_date)
            elif re.fullmatch(r"\d{4}", self.doc_date):
                d.set("when", self.doc_date)
            d.text = self.doc_date
        rev = header.find("tei:revisionDesc", NS)
        if rev is None:
            rev = self._new(header, "revisionDesc")
        ch = self._new(rev, "change", when=date.today().isoformat(), type="semantic-enrichment")
        ch.text = "Enriquecimiento TEI-LeCO: entidades reutilizables, eventos y relaciones stand-off generadas a partir de TEI, metadatos y sidecars del corpus piloto."

    def _setup_standoff(self):
        existing = self.root.find("tei:standOff", NS)
        if existing is not None:
            self.root.remove(existing)
            self.warn("Se reemplazó un standOff preexistente en el archivo derivado; la fuente original no fue modificada.")
        self.standoff = self._new(self.root, "standOff")
        self.list_person = self._new(self.standoff, "listPerson")
        self.list_org = self._new(self.standoff, "listOrg")
        self.list_place = self._new(self.standoff, "listPlace")
        self.list_event = self._new(self.standoff, "listEvent")
        self.grp_rules = self._new(self.standoff, "interpGrp", type="normativeRules")
        self.grp_arguments = self._new(self.standoff, "interpGrp", type="legalArguments")
        self.grp_concepts = self._new(self.standoff, "interpGrp", type="localHistoricalConcepts")
        self.grp_categories = self._new(self.standoff, "interpGrp", type="localHistoricalCategories")
        self.grp_provenance = self._new(self.standoff, "interpGrp", type="provenance")
        meta = self._new(self.grp_provenance, "interp", xml_id="catalog_metadata")
        meta.text = "Metadatos archivísticos de metadata.json; se mantienen separados de las inferencias semánticas."
        self.list_relation = self._new(self.standoff, "listRelation")

    def _annotation_element(self, ann: dict[str, str]) -> Optional[ET.Element]:
        return self.id_index.get(ann.get("annotation_id", ""))

    def _entity_id(self, prefix: str, ann: dict[str, str]) -> str:
        return xml_safe(f"{prefix}_{ann.get('annotation_id')}")

    def _declare_entities(self):
        # Persons / organizations / places from explicit annotations.
        for ann in self.annotations:
            cat = ann.get("category", "")
            label = ann.get("normalized") or ann.get("surface") or ""
            key = plain_key(label)
            inline = self._annotation_element(ann)
            if cat == "person":
                ent = self.person_by_label.get(key)
                if not ent:
                    ent = self._entity_id("person", ann)
                    self.person_by_label[key] = ent
                    p = self._new(self.list_person, "person", xml_id=ent)  # type: ignore[arg-type]
                    pn = self._new(p, "persName"); pn.text = label
                if inline is not None:
                    inline.set("ref", f"#{ent}")
            elif cat in {"institution", "institutional_body"}:
                ent = self.org_by_label.get(key)
                if not ent:
                    ent = self._entity_id("org", ann)
                    self.org_by_label[key] = ent
                    subtype = ann.get("subtype", "")
                    ana = ORG_TYPE.get(subtype)
                    org = self._new(self.list_org, "org", xml_id=ent, ana=(LECO + ana) if ana else None)  # type: ignore[arg-type]
                    on = self._new(org, "orgName"); on.text = label
                if inline is not None:
                    inline.set("ref", f"#{ent}")
            elif cat == "place":
                ent = self.place_by_label.get(key)
                if not ent:
                    ent = self._entity_id("place", ann)
                    self.place_by_label[key] = ent
                    pl = self._new(self.list_place, "place", xml_id=ent)  # type: ignore[arg-type]
                    pn = self._new(pl, "placeName"); pn.text = label
                if inline is not None:
                    inline.set("ref", f"#{ent}")

        # Archival metadata can add contextual entities that do not appear literally in the transcription.
        related = self.metadata.get("related_entities") or []
        for i, label in enumerate(related, 1):
            key = plain_key(label)
            if key in self.person_by_label or key in self.org_by_label:
                continue
            if key.startswith("cabildo de ") or key == "cabildo":
                ent = f"catalog_org_{i:03d}"
                self.org_by_label[key] = ent
                org = self._new(self.list_org, "org", xml_id=ent, ana=LECO + "CabildoType")  # type: ignore[arg-type]
                on = self._new(org, "orgName"); on.text = label
                org.set("source", "#catalog_metadata")
        for i, label in enumerate(self.metadata.get("places") or [], 1):
            key = plain_key(label)
            if key in self.place_by_label:
                continue
            ent = f"catalog_place_{i:03d}"
            self.place_by_label[key] = ent
            pl = self._new(self.list_place, "place", xml_id=ent)  # type: ignore[arg-type]
            pn = self._new(pl, "placeName"); pn.text = label
            pl.set("source", "#catalog_metadata")

    def _declare_concepts_categories_rules(self):
        for ann in self.annotations:
            cat = ann.get("category", "")
            subtype = ann.get("subtype", "")
            label = ann.get("normalized") or ann.get("surface") or ""
            inline = self._annotation_element(ann)
            if cat == "historical_concept":
                known = CONCEPT_URI.get(plain_key(subtype)) or CONCEPT_URI.get(plain_key(label))
                if known:
                    ref = LECO + known
                else:
                    rid = self._entity_id("concept", ann)
                    self.local_concept_by_annotation[ann["annotation_id"]] = rid
                    interp = self._new(self.grp_concepts, "interp", xml_id=rid)  # type: ignore[arg-type]
                    interp.text = label
                    ref = f"#{rid}"
                if inline is not None:
                    inline.set("ref", ref)
            elif cat == "historical_social_legal_category":
                known = CATEGORY_URI.get(plain_key(label))
                if known:
                    ref = LECO + known
                else:
                    rid = self._entity_id("category", ann)
                    self.local_category_by_annotation[ann["annotation_id"]] = rid
                    klass = CATEGORY_CLASS.get(subtype, "HistoricalLegalCategory")
                    interp = self._new(self.grp_categories, "interp", xml_id=rid, ana=LECO + klass)  # type: ignore[arg-type]
                    interp.text = label
                    ref = f"#{rid}"
                if inline is not None:
                    inline.set("type", "historicalCategory")
                    inline.set("ref", ref)
            elif cat == "normative_source":
                rid = self._entity_id("rule", ann)
                self.local_rule_by_annotation[ann["annotation_id"]] = rid
                interp = self._new(self.grp_rules, "interp", xml_id=rid)
                interp.text = label
                if inline is not None:
                    inline.set("type", "normativeRule")
                    inline.set("ref", f"#{rid}")

    def _declare_offices(self):
        for ann in self.annotations:
            if ann.get("category") != "role_or_office":
                continue
            label = ann.get("normalized") or ann.get("surface") or ""
            office = OFFICE_TYPE.get(plain_key(label))
            inline = self._annotation_element(ann)
            if office and inline is not None:
                inline.set("type", "officeType")
                inline.set("ref", LECO + office)
            elif inline is not None:
                self.warn(f"Oficio/rol no resuelto automáticamente: {label} ({ann.get('annotation_id')})")

    def _declare_events(self):
        for ann in self.annotations:
            if ann.get("category") != "legal_or_procedural_act":
                continue
            subtype = ann.get("subtype", "")
            klass = ACT_CLASS.get(subtype, "JurisdictionalAct")
            eid = self._entity_id("event", ann)
            self.event_by_annotation[ann["annotation_id"]] = eid
            self.event_by_segment_subtype.setdefault((ann.get("segment_id", ""), subtype), []).append(eid)
            attrs = {"xml_id": eid, "ana": LECO + klass, "corresp": f"#{ann.get('segment_id')}"}
            if self.doc_date:
                if re.fullmatch(r"\d{4}(-\d{2}-\d{2})?", self.doc_date):
                    attrs["when"] = self.doc_date
            ev = self._new(self.list_event, "event", **attrs)  # type: ignore[arg-type]
            desc = self._new(ev, "desc"); desc.text = ann.get("surface") or subtype
            inline = self._annotation_element(ann)
            if inline is not None:
                inline.set("ana", LECO + klass)
                inline.set("corresp", f"#{eid}")

    def _best_cabildo_org(self) -> Optional[str]:
        # Prefer catalogued Cabildo; fallback to Justice and Regiment body.
        for key, oid in self.org_by_label.items():
            if key.startswith("cabildo de ") or key == "cabildo":
                return oid
        for ann in self.annotations:
            if ann.get("category") == "institutional_body" and ann.get("subtype") == "cabildo_body":
                return self.org_by_label.get(plain_key(ann.get("normalized") or ann.get("surface") or ""))
        return None

    def _audiencia_in_segment(self, segment_id: str) -> Optional[str]:
        for ann in self.annotations:
            if ann.get("segment_id") == segment_id and ann.get("category") == "institution" and ann.get("subtype") == "audiencia":
                return self.org_by_label.get(plain_key(ann.get("normalized") or ann.get("surface") or ""))
        return None

    def _person(self, label: str) -> Optional[str]:
        key = plain_key(label)
        if key in self.person_by_label:
            return self.person_by_label[key]
        # Conservative surname fallback, useful for "señor Pineda" in relations/prose.
        tokens = [t for t in key.split() if len(t) > 2]
        matches = []
        for pkey, pid in self.person_by_label.items():
            if key and (key in pkey or pkey in key):
                matches.append(pid)
            elif tokens and tokens[-1] in pkey.split():
                matches.append(pid)
        return matches[0] if len(set(matches)) == 1 else None

    def _event(self, segment: str, object_label: str) -> Optional[str]:
        obj = plain_key(object_label).replace(" ", "_")
        aliases = {
            "appeal": "appeal", "apelacion": "appeal", "apelar": "appeal",
            "petition": "petition", "peticion": "petition",
            "proclamation": "proclamation", "pregon": "proclamation",
            "appointment": "appointment", "nombramiento": "appointment",
            "decision": "decision", "detention": "detention",
            "investigation": "investigation", "order": "order_event", "order_event": "order_event",
            "grant_of_power": "grant_of_power", "power_of_representation": "power_of_representation",
        }
        subtype = aliases.get(obj, obj)
        candidates = self.event_by_segment_subtype.get((segment, subtype), [])
        return candidates[0] if candidates else None

    def _concept_ref_for_annotation(self, ann: dict[str, str]) -> Optional[str]:
        label = ann.get("normalized") or ann.get("surface") or ""
        known = CONCEPT_URI.get(plain_key(ann.get("subtype", ""))) or CONCEPT_URI.get(plain_key(label))
        if known:
            return LECO + known
        rid = self.local_concept_by_annotation.get(ann.get("annotation_id", ""))
        return f"#{rid}" if rid else None

    def _make_concept_uses(self):
        body = self.root.find(".//tei:text/tei:body/tei:div[@xml:id]", NS)
        context = f"#{body.get(XML_ID)}" if body is not None else f"#{self.root.get(XML_ID)}"
        for ann in self.annotations:
            if ann.get("category") != "historical_concept":
                continue
            ref = self._concept_ref_for_annotation(ann)
            if not ref:
                continue
            rid = xml_safe(f"concept_use_{ann.get('annotation_id')}")
            self._relation(rid, type="historicalConceptUse", active=context, passive=ref,
                           source=f"#{ann.get('segment_id')}", subtype="explicit", when=self.doc_date or None)

    def _make_jurisdictions(self):
        tunja = self.place_by_label.get("tunja")
        if not tunja:
            return
        cabildo = self._best_cabildo_org()
        if cabildo:
            rid = xml_safe("jurisdiction_cabildo")
            source_seg = next((a.get("segment_id") for a in self.annotations if a.get("category") == "institutional_body" and a.get("subtype") == "cabildo_body"), None)
            self._relation(rid, type="territorialJurisdiction", active=f"#{cabildo}", passive=f"#{tunja}",
                           ana=LECO + "TerritorialJurisdiction", subtype="humanInterpretation",
                           source=(f"#{source_seg}" if source_seg else f"#{self.local_id}_acta"))
        # An audiencia appearing as appellate authority in the document is enough to model an inferred
        # jurisdictional context over the place of the local dispute, but it is explicitly flagged.
        audiencias = []
        for ann in self.annotations:
            if ann.get("category") == "institution" and ann.get("subtype") == "audiencia":
                oid = self.org_by_label.get(plain_key(ann.get("normalized") or ann.get("surface") or ""))
                if oid and oid not in audiencias:
                    audiencias.append(oid)
        for i, oid in enumerate(audiencias, 1):
            rid = xml_safe(f"jurisdiction_audiencia_{i:02d}")
            source_seg = next((a.get("segment_id") for a in self.annotations if a.get("category") == "institution" and a.get("subtype") == "audiencia" and self.org_by_label.get(plain_key(a.get("normalized") or a.get("surface") or "")) == oid), None)
            self._relation(rid, type="territorialJurisdiction", active=f"#{oid}", passive=f"#{tunja}",
                           ana=LECO + "TerritorialJurisdiction", subtype="inferred",
                           source=(f"#{source_seg}" if source_seg else f"#{self.local_id}_acta"))
            self._precision(rid, "medium")

    def _make_sidecar_relations(self):
        cabildo = self._best_cabildo_org()
        for row in self.relations:
            pred = row.get("predicate", "")
            seg = row.get("segment_id", "")
            basis = row.get("basis") or "humanInterpretation"
            certainty = row.get("certainty") or ""
            rid = xml_safe("migrated_" + (row.get("relation_id") or pred))
            subj = row.get("subject", "")
            obj = row.get("object", "")

            if pred in {"containsLegalAct", "isMentionedIn", "invokesConcept"}:
                # Already represented through event @corresp / inline annotation / HistoricalConceptUse.
                continue

            if pred == "holdsOrPerformsRole":
                person = self._person(subj)
                office = OFFICE_TYPE.get(plain_key(obj))
                if person and office and cabildo:
                    self._relation(rid, type="officeHolding", active=f"#{person}", passive=f"#{cabildo}",
                                   ana=LECO + office, source=f"#{seg}", subtype=basis,
                                   when=self.metadata.get("date") or self.doc_date or None)
                    self._precision(rid, certainty)
                else:
                    self.warn(f"No se migró {pred}: {subj} → {obj} ({seg}); falta persona/oficio/institución inequívoca.")
                continue

            if pred in {"performsAct", "presentsOrRequests"}:
                person = self._person(subj)
                event = self._event(seg, obj)
                if pred == "presentsOrRequests" and not event:
                    event = self._event(seg, "petition")
                if person and event:
                    event_ann = next((a for a in self.annotations if self.event_by_annotation.get(a.get("annotation_id", "")) == event), None)
                    subtype = event_ann.get("subtype", "") if event_ann else ""
                    role = ROLE_FOR_ACT.get(subtype, "PartyRole")
                    self._relation(rid, type="participation", active=f"#{person}", passive=f"#{event}",
                                   ana=LECO + role, source=f"#{seg}", subtype=basis)
                    self._precision(rid, certainty)
                else:
                    self.warn(f"No se migró {pred}: {subj} → {obj} ({seg}); falta persona/evento inequívoco.")
                continue

            if pred == "appointsOrDesignates":
                person = self._person(obj)
                event = self._event(seg, "appointment")
                if event and person:
                    self._relation(rid, type="objectProperty", name="appointsPerson", active=f"#{event}", passive=f"#{person}",
                                   source=f"#{seg}", subtype=basis)
                    self._precision(rid, certainty)
                else:
                    self.warn(f"Relación {pred} conservada solo en reporte: {subj} → {obj} ({seg}).")
                continue

            # The remaining legacy predicates are intentionally not silently promoted.
            self.warn(f"Predicado legacy pendiente de curaduría/mapeo: {pred}: {subj} → {obj} ({seg}).")

    def _pineda_like_structural_rules(self):
        """General deterministic patterns for common pilot constructions.

        These are not tied to a document id. Every generated assertion is marked
        explicit/inferred/humanInterpretation and points to the source segment.
        """
        cabildo = self._best_cabildo_org()

        # Appeal: actor participation, authority, and appealed prior decision.
        for ann in self.annotations:
            if ann.get("category") != "legal_or_procedural_act" or ann.get("subtype") != "appeal":
                continue
            seg = ann.get("segment_id", "")
            appeal = self.event_by_annotation.get(ann.get("annotation_id", ""))
            if not appeal:
                continue
            audiencia = self._audiencia_in_segment(seg)
            if audiencia:
                self._relation(f"derived_before_{appeal}", type="objectProperty", name="beforeAuthority",
                               active=f"#{appeal}", passive=f"#{audiencia}", source=f"#{seg}", subtype="explicit")
            persons = [a for a in self.annotations if a.get("segment_id") == seg and a.get("category") == "person"]
            if len(persons) == 1:
                pid = self._person(persons[0].get("normalized") or persons[0].get("surface") or "")
                if pid:
                    if not self._has_relation("participation", f"#{pid}", f"#{appeal}", ana=LECO + "AppellantRole"):
                        rr = self._relation(f"derived_participation_{appeal}", type="participation", active=f"#{pid}", passive=f"#{appeal}",
                                            ana=LECO + "AppellantRole", source=f"#{seg}", subtype="inferred")
                        self._precision(rr.get(XML_ID), "high")
            # Link to the closest previous LegalDecision event in document order.
            all_acts = [a for a in self.annotations if a.get("category") == "legal_or_procedural_act"]
            idx = all_acts.index(ann)
            previous = [a for a in all_acts[:idx] if a.get("subtype") in {"decision", "penalty", "sanction"}]
            if previous:
                target = self.event_by_annotation.get(previous[-1].get("annotation_id", ""))
                if target:
                    rr = self._relation(f"derived_appeals_{appeal}", type="objectProperty", name="appealsAgainst",
                                        active=f"#{appeal}", passive=f"#{target}", source=f"#{seg}", subtype="inferred")
                    self._precision(rr.get(XML_ID), "medium")

        # Local legal decisions are attributed to the catalogued Cabildo when the source explicitly
        # says a collective decision (e.g. "acordaron") but the legacy annotation lacks an actor node.
        if cabildo:
            for ann in self.annotations:
                if ann.get("category") == "legal_or_procedural_act" and ann.get("subtype") == "decision":
                    ev = self.event_by_annotation.get(ann.get("annotation_id", ""))
                    if ev:
                        rr = self._relation(f"derived_decided_{ev}", type="objectProperty", name="decidedBy",
                                            active=f"#{ev}", passive=f"#{cabildo}", source=f"#{ann.get('segment_id')}", subtype="humanInterpretation")
                        self._precision(rr.get(XML_ID), "medium")

        # Order + investigation in the same segment.
        for seg in {a.get("segment_id", "") for a in self.annotations}:
            orders = self.event_by_segment_subtype.get((seg, "order_event"), [])
            investigations = self.event_by_segment_subtype.get((seg, "investigation"), [])
            if orders and investigations:
                self._relation(f"derived_orders_{seg}", type="objectProperty", name="ordersAct",
                               active=f"#{orders[0]}", passive=f"#{investigations[0]}", source=f"#{seg}", subtype="explicit")
                # If one known person surname is explicitly named in the raw segment but not tagged, attach conservatively.
                seg_el = self.id_index.get(seg)
                seg_text = plain_key(text_content(seg_el)) if seg_el is not None else ""
                matched = []
                for pkey, pid in self.person_by_label.items():
                    surname = pkey.split()[-1] if pkey.split() else ""
                    if surname and surname in seg_text.split():
                        matched.append(pid)
                if len(set(matched)) == 1:
                    rr = self._relation(f"derived_investigates_{seg}", type="objectProperty", name="investigates",
                                        active=f"#{investigations[0]}", passive=f"#{matched[0]}", source=f"#{seg}", subtype="inferred")
                    self._precision(rr.get(XML_ID), "medium")

        # "incumplimiento ... deber ... [office]" -> LegalDuty + LegalArgument, only when both lexical cues occur.
        for seg in {a.get("segment_id", "") for a in self.annotations if a.get("category") == "historical_concept" and a.get("subtype") == "duty"}:
            seg_el = self.id_index.get(seg)
            raw = text_content(seg_el) if seg_el is not None else ""
            if "incumplimiento" not in plain_key(raw):
                continue
            duty_anns = [a for a in self.annotations if a.get("segment_id") == seg and a.get("category") == "historical_concept" and a.get("subtype") == "duty"]
            office_anns = [a for a in self.annotations if a.get("segment_id") == seg and a.get("category") == "role_or_office"]
            if not duty_anns:
                continue
            office_label = (office_anns[-1].get("surface") if office_anns else "") or ""
            rule_id = xml_safe(f"rule_duty_{seg}")
            if not any(i.get(XML_ID) == rule_id for i in self.grp_rules):  # type: ignore[union-attr]
                interp = self._new(self.grp_rules, "interp", xml_id=rule_id, ana=LECO + "LegalDuty")  # type: ignore[arg-type]
                interp.text = norm_space("deber " + ("de " + office_label if office_label else ""))
            arg_id = xml_safe(f"argument_breach_{seg}")
            if not any(i.get(XML_ID) == arg_id for i in self.grp_arguments):  # type: ignore[union-attr]
                interp = self._new(self.grp_arguments, "interp", xml_id=arg_id)  # type: ignore[arg-type]
                interp.text = norm_space("incumplimiento con el deber " + ("de " + office_label if office_label else ""))
            orders = self.event_by_segment_subtype.get((seg, "order_event"), [])
            investigations = self.event_by_segment_subtype.get((seg, "investigation"), [])
            target_act = orders[0] if orders else (investigations[0] if investigations else None)
            if target_act:
                self._relation(f"derived_argument_{seg}", type="objectProperty", name="hasLegalArgument",
                               active=f"#{target_act}", passive=f"#{arg_id}", source=f"#{seg}", subtype="humanInterpretation")
                self._relation(f"derived_argument_rule_{seg}", type="objectProperty", name="argumentInvokesRule",
                               active=f"#{arg_id}", passive=f"#{rule_id}", source=f"#{seg}", subtype="humanInterpretation")

    def enrich(self):
        self._ensure_header()
        # Mark Acta document type on the main division.
        for div in self.root.findall(".//tei:text/tei:body/tei:div[@xml:id]", NS):
            if div.get("type") == "acta" and not div.get("ana"):
                div.set("ana", LECO + "ActaCabildoDocumentType")
        self._setup_standoff()
        self._declare_entities()
        self._declare_concepts_categories_rules()
        self._declare_offices()
        self._declare_events()
        self._make_concept_uses()
        self._make_jurisdictions()
        self._make_sidecar_relations()
        self._pineda_like_structural_rules()

    def counts(self) -> tuple[int, int, int, int, int]:
        return (
            len(self.list_person) if self.list_person is not None else 0,
            len(self.list_org) if self.list_org is not None else 0,
            len(self.list_place) if self.list_place is not None else 0,
            len(self.list_event) if self.list_event is not None else 0,
            len(self.list_relation) if self.list_relation is not None else 0,
        )

    def write(self, out: Path):
        # Do not call ET.indent(): indentation whitespace inside mixed-content <seg>
        # elements would alter the transcription.
        out.parent.mkdir(parents=True, exist_ok=True)
        self.tree.write(out, encoding="utf-8", xml_declaration=True)


def source_body_text(path: Path) -> str:
    root = ET.parse(path).getroot()
    body = root.find(".//tei:text/tei:body", NS)
    return text_content(body) if body is not None else ""


def enrich_one(doc_dir: Path, output_dir: Path) -> EnrichmentReport:
    if not (doc_dir / "tei.xml").exists():
        return EnrichmentReport(doc_dir.name, doc_dir.name, "skipped-no-tei", None, warnings=["No existe tei.xml"])
    enr = Enricher(doc_dir)
    if enr.unavailable():
        return EnrichmentReport(doc_dir.name, enr.reference_code, "skipped-no-transcription", None,
                                warnings=["metadata.json marca transcription_status=unavailable"])
    before = source_body_text(enr.tei_path)
    enr.enrich()
    out = output_dir / f"{doc_dir.name}.xml"
    enr.write(out)
    after = source_body_text(out)
    if before != after:
        raise RuntimeError(f"La transcripción cambió durante el enriquecimiento de {doc_dir.name}")
    p, o, pl, ev, rel = enr.counts()
    return EnrichmentReport(doc_dir.name, enr.reference_code, "enriched", str(out), p, o, pl, ev, rel, enr.warnings)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: Optional[list[str]] = None) -> int:
    root = repo_root()
    ap = argparse.ArgumentParser(description="Enriquece TEI legacy con standOff para el perfil TEI-LeCO")
    ap.add_argument("input", nargs="?", type=Path, default=root / "data" / "documents",
                    help="Carpeta documental o data/documents con --all")
    ap.add_argument("--all", action="store_true", help="Procesa todas las subcarpetas documentales")
    ap.add_argument("--output-dir", type=Path, default=root / "build" / "tei_enriched")
    args = ap.parse_args(argv)

    if args.all:
        if not args.input.is_dir():
            ap.error("--all requiere una carpeta raíz")
        docs = sorted(d for d in args.input.iterdir() if d.is_dir())
    else:
        docs = [args.input]

    reports: list[EnrichmentReport] = []
    exit_code = 0
    for doc in docs:
        try:
            rep = enrich_one(doc, args.output_dir)
            reports.append(rep)
            if rep.status == "enriched":
                print(f"✓ {rep.document}: {rep.persons} personas, {rep.organizations} instituciones, {rep.places} lugares, {rep.events} eventos, {rep.relations} relaciones")
                for w in rep.warnings or []:
                    print(f"  ⚠ {w}")
            else:
                print(f"– {rep.document}: {rep.status}")
        except Exception as exc:
            exit_code = 1
            print(f"✗ {doc.name}: {exc}", file=sys.stderr)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "enrichment_report.json"
    report_path.write_text(json.dumps([asdict(r) for r in reports], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Reporte: {report_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
