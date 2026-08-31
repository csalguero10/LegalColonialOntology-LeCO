#!/usr/bin/env python3
"""Convert TEI documents in the LeCO mapping profile to RDF/Turtle.

Primary input layout:
    data/documents/<local-id>/tei.xml

The converter supports two modes automatically:
- mapping-profile: TEI has standOff and follows mapping/tei_to_leco.yaml.
- legacy-inline: older pilot TEI without standOff. It converts only semantics that
  can be recovered safely from inline markup and emits warnings for missing
  relational context. No undocumented historical relation is invented.

Examples:
    python scripts/tei_to_rdf.py data/documents/cab-001-002
    python scripts/tei_to_rdf.py data/documents --all
    python scripts/tei_to_rdf.py data/documents/cab-001-002 --validate
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import quote
import xml.etree.ElementTree as ET

import yaml
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD, DCTERMS, SKOS

try:
    from leco_normalization import office_type_local_name
except ImportError:  # imported as scripts.tei_to_rdf during tests
    from scripts.leco_normalization import office_type_local_name

TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI, "xml": XML}
XML_ID = f"{{{XML}}}id"

LECO = Namespace("https://w3id.org/leco/ontology#")
RICO = Namespace("https://www.ica.org/standards/RiC/ontology#")
CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
PROV = Namespace("http://www.w3.org/ns/prov#")
TIME = Namespace("http://www.w3.org/2006/time#")

LEGACY_ACT_CLASS = {
    "decision": LECO.LegalDecision,
    "detention": LECO.Detention,
    "appearance": LECO.Appearance,
    "appeal": LECO.Appeal,
    "appointment": LECO.Appointment,
    "order_event": LECO.OrderAct,
    "investigation": LECO.Investigation,
    "adjudication": LECO.Adjudication,
    "petition": LECO.Petition,
    "testimony": LECO.Testimony,
    "opposition": LECO.Opposition,
    "notification": LECO.Notification,
    "sanction": LECO.Sanction,
    "fine": LECO.Fine,
    "prohibition": LECO.Prohibition,
    "proclamation": LECO.Proclamation,
    "oath": LECO.Oath,
    "execution": LECO.Execution,
}
LEGACY_CONCEPT = {
    "real_service": LECO.RealServiceConcept,
    "real servicio": LECO.RealServiceConcept,
    "duty": LECO.DutyConcept,
    "deber": LECO.DutyConcept,
    "jurisdiction": LECO.JurisdictionConcept,
    "jurisdiccion": LECO.JurisdictionConcept,
    "justice": LECO.JusticeConcept,
    "justicia": LECO.JusticeConcept,
    "custom": LECO.CustomConcept,
    "costumbre": LECO.CustomConcept,
    "republic": LECO.RepublicConcept,
    "república": LECO.RepublicConcept,
}
LEGACY_ORG_TYPE = {
    "audiencia": LECO.AudienciaType,
    "cabildo": LECO.CabildoType,
    "cabildo_body": LECO.JusticeAndRegimentType,
}
BASIS_MAP = {
    "explicit": LECO.ExplicitTextualEvidence,
    "inferred": LECO.InferredFromText,
    "catalog": LECO.CatalogMetadataBasis,
    "humaninterpretation": LECO.HumanInterpretationBasis,
    "human_interpretation": LECO.HumanInterpretationBasis,
}


def qn(tag: str) -> str:
    return f"{{{TEI}}}{tag}"


def norm_text(el: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def split_ptrs(value: Optional[str]) -> list[str]:
    return value.split() if value else []


def safe_piece(value: str) -> str:
    return quote(value.strip(), safe="-._~")


def first(iterable: Iterable):
    return next(iter(iterable), None)


@dataclass
class ConversionReport:
    document: str
    reference_code: str
    mode: str
    triples: int
    output: str
    warnings: list[str]
    shacl_conforms: Optional[bool] = None
    shacl_report: Optional[str] = None


class TEILeCOConverter:
    def __init__(self, mapping_path: Path, strict: bool = False):
        self.mapping_path = Path(mapping_path)
        self.mapping = yaml.safe_load(self.mapping_path.read_text(encoding="utf-8"))
        self.strict = strict
        self.warnings: list[str] = []
        self.g = Graph()
        self._bind()
        self.root: ET.Element | None = None
        self.parent_map: dict[ET.Element, ET.Element] = {}
        self.id_index: dict[str, ET.Element] = {}
        self.reference_code = ""
        self.record_uri: URIRef | None = None
        self.document_date_uri: URIRef | None = None
        self.annotation_activity_uri: URIRef | None = None
        self.mode = ""
        self.metadata: dict = {}
        self.precision_by_target: dict[str, Decimal] = {}
        self.event_uris: set[URIRef] = set()

    def _bind(self):
        for p, ns in {
            "leco": LECO, "rico": RICO, "crm": CRM, "foaf": FOAF,
            "prov": PROV, "time": TIME, "skos": SKOS,
            "dcterms": DCTERMS,
        }.items():
            self.g.bind(p, ns)

    def warn(self, msg: str):
        self.warnings.append(msg)
        if self.strict:
            raise ValueError(msg)

    def local_uri(self, xml_id: str) -> URIRef:
        return URIRef(f"https://w3id.org/leco/data/{safe_piece(self.reference_code)}/{safe_piece(xml_id)}")

    def resolve(self, pointer: Optional[str]) -> Optional[URIRef]:
        if not pointer:
            return None
        pointer = pointer.strip()
        if pointer.startswith("http://") or pointer.startswith("https://"):
            return URIRef(pointer)
        if pointer.startswith("#"):
            ident = pointer[1:]
            if ident not in self.id_index:
                self.warn(f"Puntero local sin destino: {pointer}")
            return self.local_uri(ident)
        # TEI occasionally stores a bare xml:id in relation attributes.
        if pointer in self.id_index:
            return self.local_uri(pointer)
        self.warn(f"No se pudo resolver el puntero '{pointer}'")
        return None

    def nearest_evidence(self, el: ET.Element) -> Optional[URIRef]:
        cur = el
        while cur is not None:
            if cur.tag in {qn("seg"), qn("div")} and cur.get(XML_ID):
                return self.local_uri(cur.get(XML_ID))
            cur = self.parent_map.get(cur)
        return None

    def load(self, tei_path: Path, metadata_path: Optional[Path] = None):
        tree = ET.parse(tei_path)
        self.root = tree.getroot()
        self.parent_map = {child: parent for parent in self.root.iter() for child in parent}
        self.id_index = {el.get(XML_ID): el for el in self.root.iter() if el.get(XML_ID)}
        self.mode = "mapping-profile" if self.root.find("tei:standOff", NS) is not None else "legacy-inline"

        metadata = {}
        if metadata_path and metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        self.metadata = metadata

        idno = self.root.find(".//tei:idno[@type='reference_code']", NS)
        self.reference_code = (
            (idno.text.strip() if idno is not None and idno.text else "")
            or metadata.get("reference_code")
            or self.root.get(XML_ID)
            or tei_path.parent.name
        )
        self.record_uri = URIRef(f"https://w3id.org/leco/data/{safe_piece(self.reference_code)}/record")
        self.annotation_activity_uri = self.local_uri("tei-mapping-annotation-activity")
        self.g.add((self.annotation_activity_uri, RDF.type, LECO.AnnotationActivity))
        self.g.add((self.annotation_activity_uri, RDF.type, PROV.Activity))

        # Precision is indexed before relation annotations are built.
        for prec in self.root.findall(".//tei:precision[@target][@confidence]", NS):
            for target in split_ptrs(prec.get("target")):
                key = target[1:] if target.startswith("#") else target
                try:
                    score = Decimal(prec.get("confidence"))
                except (InvalidOperation, TypeError):
                    self.warn(f"Valor confidence inválido en precision target={target}")
                    continue
                if Decimal("0") <= score <= Decimal("1"):
                    self.precision_by_target[key] = score
                else:
                    self.warn(f"confidence fuera de rango [0,1] en {target}: {score}")

        self._record(metadata)
        self._document_date()

    def _record(self, metadata: dict):
        assert self.root is not None and self.record_uri is not None
        self.g.add((self.record_uri, RDF.type, LECO.LegalDocument))
        self.g.add((self.record_uri, RDF.type, RICO.Record))
        self.g.add((self.record_uri, RDF.type, PROV.Entity))
        self.g.add((self.record_uri, DCTERMS.identifier, Literal(self.reference_code)))

        title_el = self.root.find(".//tei:fileDesc/tei:titleStmt/tei:title", NS)
        # Prefer the verified archival title from metadata.json over a generic TEI working title.
        title = metadata.get("title") or (norm_text(title_el) if title_el is not None else None)
        if title:
            self.g.add((self.record_uri, DCTERMS.title, Literal(title, lang="es")))
        source = metadata.get("record_uri")
        if source:
            self.g.add((self.record_uri, DCTERMS.source, URIRef(source)))

        # Document type belongs to the record, not to the RecordPart.
        top_div = self.root.find(".//tei:text/tei:body/tei:div", NS)
        if top_div is not None:
            ana = first(split_ptrs(top_div.get("ana")))
            if ana:
                dtype = self.resolve(ana)
            elif (top_div.get("type") or "").lower() in {"acta", "acta_cabildo"}:
                dtype = LECO.ActaCabildoDocumentType
            else:
                dtype = None
            if dtype:
                self.g.add((self.record_uri, LECO.hasDocumentType, dtype))
        if not list(self.g.objects(self.record_uri, LECO.hasDocumentType)):
            self.warn("El documento no tiene tipo documental LeCO; SHACL LegalDocumentShape puede fallar.")

    def _document_date(self):
        assert self.root is not None
        date_el = self.root.find(".//tei:profileDesc//tei:date[@when]", NS)
        if date_el is None:
            date_el = self.root.find(".//tei:creation//tei:date[@when]", NS)
        if date_el is None:
            when = self.metadata.get("date_asserted_in_scope_and_content") or self.metadata.get("date")
            label = when
        else:
            when = date_el.get("when")
            label = norm_text(date_el) or when
        if not when:
            return
        uri = self.local_uri("document-date")
        self.document_date_uri = uri
        self.g.add((uri, RDF.type, RICO.Date))
        self.g.add((uri, RDFS.label, Literal(label or when, lang="es")))
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", when):
            self.g.add((uri, TIME.inXSDDate, Literal(when, datatype=XSD.date)))
        elif re.fullmatch(r"\d{4}", when):
            self.g.add((uri, DCTERMS.date, Literal(when, datatype=XSD.gYear)))

    def convert(self):
        self._structure()
        self._stand_off_entities()
        self._inline_annotations()
        self._stand_off_interps()
        self._events()
        self._relations()
        self._legacy_sidecar_semantics()
        self._derived_rules()
        return self.g

    def _structure(self):
        assert self.root is not None and self.record_uri is not None
        structural = [el for el in self.root.iter() if el.tag in {qn("div"), qn("seg")} and el.get(XML_ID)]
        for el in structural:
            uri = self.local_uri(el.get(XML_ID))
            self.g.add((uri, RDF.type, LECO.LegalDocumentPart))
            self.g.add((uri, RDF.type, RICO.RecordPart))
            self.g.add((uri, RDF.type, PROV.Entity))
            self.g.add((uri, DCTERMS.identifier, Literal(el.get(XML_ID))))
            parent = self.parent_map.get(el)
            container = None
            while parent is not None:
                if parent.tag in {qn("div"), qn("seg")} and parent.get(XML_ID):
                    container = self.local_uri(parent.get(XML_ID))
                    break
                parent = self.parent_map.get(parent)
            if container is None:
                container = self.record_uri
            self.g.add((container, RICO.hasDirectConstituent, uri))
            self.g.add((uri, RICO.isDirectConstituentOf, container))

    def _stand_off_entities(self):
        assert self.root is not None
        for el in self.root.findall(".//tei:standOff//tei:listPerson/tei:person[@xml:id]", NS):
            uri = self.local_uri(el.get(XML_ID))
            for t in (RICO.Person, RICO.Agent, CRM.E21_Person, FOAF.Person):
                self.g.add((uri, RDF.type, t))
            label = first(el.findall("tei:persName", NS))
            if label is not None and norm_text(label):
                self.g.add((uri, RDFS.label, Literal(norm_text(label), lang="es")))
                self.g.add((uri, FOAF.name, Literal(norm_text(label))))

        for el in self.root.findall(".//tei:standOff//tei:listOrg/tei:org[@xml:id]", NS):
            uri = self.local_uri(el.get(XML_ID))
            for t in (RICO.CorporateBody, RICO.Group, RICO.Agent, CRM.E74_Group):
                self.g.add((uri, RDF.type, t))
            label = first(el.findall("tei:orgName", NS))
            if label is not None and norm_text(label):
                self.g.add((uri, RDFS.label, Literal(norm_text(label), lang="es")))
            ana = first(split_ptrs(el.get("ana")))
            if ana:
                resolved = self.resolve(ana)
                if resolved:
                    self.g.add((uri, LECO.hasInstitutionType, resolved))

        for el in self.root.findall(".//tei:standOff//tei:listPlace/tei:place[@xml:id]", NS):
            uri = self.local_uri(el.get(XML_ID))
            self.g.add((uri, RDF.type, RICO.Place))
            self.g.add((uri, RDF.type, CRM.E53_Place))
            label = first(el.findall("tei:placeName", NS))
            if label is not None and norm_text(label):
                self.g.add((uri, RDFS.label, Literal(norm_text(label), lang="es")))

    def _legacy_body_for_inline(self, el: ET.Element) -> Optional[URIRef]:
        xml_id = el.get(XML_ID)
        text = norm_text(el)
        typ = (el.get("type") or "").lower()
        subtype = (el.get("subtype") or "").lower()
        if el.tag == qn("persName"):
            uri = self.local_uri(f"{xml_id}-entity")
            for t in (RICO.Person, RICO.Agent, CRM.E21_Person, FOAF.Person):
                self.g.add((uri, RDF.type, t))
            self.g.add((uri, RDFS.label, Literal(text, lang="es")))
            return uri
        if el.tag == qn("orgName"):
            uri = self.local_uri(f"{xml_id}-entity")
            for t in (RICO.CorporateBody, RICO.Group, RICO.Agent, CRM.E74_Group):
                self.g.add((uri, RDF.type, t))
            self.g.add((uri, RDFS.label, Literal(text, lang="es")))
            inst_type = LEGACY_ORG_TYPE.get(subtype) or LEGACY_ORG_TYPE.get(typ)
            if inst_type:
                self.g.add((uri, LECO.hasInstitutionType, inst_type))
            return uri
        if el.tag == qn("placeName"):
            uri = self.local_uri(f"{xml_id}-entity")
            self.g.add((uri, RDF.type, RICO.Place)); self.g.add((uri, RDF.type, CRM.E53_Place))
            self.g.add((uri, RDFS.label, Literal(text, lang="es")))
            return uri
        if el.tag == qn("term"):
            key = subtype or text.lower()
            concept = LEGACY_CONCEPT.get(key) or LEGACY_CONCEPT.get(text.lower())
            if concept:
                return concept
            uri = self.local_uri(f"{xml_id}-concept")
            self.g.add((uri, RDF.type, LECO.HistoricalLegalConcept))
            self.g.add((uri, RDF.type, SKOS.Concept))
            self.g.add((uri, SKOS.prefLabel, Literal(text, lang="es")))
            self.g.add((uri, SKOS.inScheme, LECO.HistoricalLegalConceptScheme))
            return uri
        if el.tag == qn("rs") and typ in {"role_or_office", "officetype"}:
            office_type = office_type_local_name(text)
            if office_type:
                return LECO[office_type]
            self.warn(f"Oficio/rol legacy sin correspondencia controlada: '{text}' ({xml_id})")
            return None
        if el.tag == qn("rs") and typ == "legal_or_procedural_act":
            cls = LEGACY_ACT_CLASS.get(subtype)
            if not cls:
                self.warn(f"Acto legacy sin clase LeCO controlada: subtype='{subtype}' ({xml_id})")
                return None
            uri = self.local_uri(f"{xml_id}-event")
            self.g.add((uri, RDF.type, cls))
            self.g.add((uri, RDFS.label, Literal(text, lang="es")))
            evidence = self.nearest_evidence(el)
            if evidence:
                self.g.add((evidence, LECO.documentsAct, uri))
            self.event_uris.add(uri)
            return uri
        return None

    def _inline_annotations(self):
        assert self.root is not None
        for tag in ("persName", "orgName", "placeName", "term", "rs"):
            for el in self.root.findall(f".//tei:text//tei:{tag}[@xml:id]", NS):
                xml_id = el.get(XML_ID)
                ptr = el.get("ref") or el.get("ana")
                body = self.resolve(first(split_ptrs(ptr))) if ptr else self._legacy_body_for_inline(el)
                if body is None:
                    continue
                evidence = self.nearest_evidence(el)
                if evidence is None:
                    self.warn(f"Anotación inline sin segmento/div de evidencia: {xml_id}")
                    continue
                ann = self.local_uri(f"{xml_id}-annotation")
                self._semantic_annotation(
                    ann, evidence, body, LECO.ExplicitTextualEvidence,
                    evidence_uris=[evidence], evidence_text=norm_text(el)
                )

    def _stand_off_interps(self):
        assert self.root is not None
        for grp_type, base_type in {
            "normativeRules": LECO.NormativeRule,
            "legalArguments": LECO.LegalArgument,
            "localHistoricalConcepts": LECO.HistoricalLegalConcept,
            "localHistoricalCategories": LECO.HistoricalLegalCategory,
        }.items():
            for el in self.root.findall(f".//tei:standOff/tei:interpGrp[@type='{grp_type}']/tei:interp[@xml:id]", NS):
                uri = self.local_uri(el.get(XML_ID)); text = norm_text(el)
                self.g.add((uri, RDF.type, base_type))
                if grp_type in {"localHistoricalConcepts", "localHistoricalCategories"}:
                    self.g.add((uri, RDF.type, SKOS.Concept))
                    self.g.add((uri, SKOS.prefLabel, Literal(text, lang="es")))
                if grp_type == "localHistoricalConcepts":
                    self.g.add((uri, SKOS.inScheme, LECO.HistoricalLegalConceptScheme))
                elif grp_type == "localHistoricalCategories":
                    self.g.add((uri, SKOS.inScheme, LECO.HistoricalLegalCategoryScheme))
                else:
                    self.g.add((uri, RDFS.label, Literal(text, lang="es")))
                    self.g.add((uri, LECO.lexicalForm, Literal(text)))
                for ana in split_ptrs(el.get("ana")):
                    resolved = self.resolve(ana)
                    if resolved:
                        self.g.add((uri, RDF.type, resolved))
                        if grp_type == "localHistoricalCategories":
                            scheme_map = {
                                LECO.EthnoLegalCategory: LECO.EthnoLegalCategoryScheme,
                                LECO.StatusCategory: LECO.StatusCategoryScheme,
                                LECO.ReligiousLegalCategory: LECO.ReligiousLegalCategoryScheme,
                                LECO.SocioLegalCategory: LECO.SocioLegalCategoryScheme,
                                LECO.ColonialOfficeStatus: LECO.ColonialOfficeStatusScheme,
                            }
                            if resolved in scheme_map:
                                self.g.add((uri, SKOS.inScheme, scheme_map[resolved]))

    def _events(self):
        assert self.root is not None
        for el in self.root.findall(".//tei:standOff//tei:listEvent/tei:event[@xml:id]", NS):
            uri = self.local_uri(el.get(XML_ID)); self.event_uris.add(uri)
            ana = first(split_ptrs(el.get("ana")))
            cls = self.resolve(ana) if ana else LECO.JurisdictionalAct
            if cls:
                self.g.add((uri, RDF.type, cls))
            desc = el.find("tei:desc", NS)
            if desc is not None and norm_text(desc):
                self.g.add((uri, RDFS.label, Literal(norm_text(desc), lang="es")))
            for corresp in split_ptrs(el.get("corresp")):
                evidence = self.resolve(corresp)
                if evidence:
                    self.g.add((evidence, LECO.documentsAct, uri))

    def _basis(self, subtype: Optional[str]) -> URIRef:
        return BASIS_MAP.get((subtype or "").lower(), LECO.HumanInterpretationBasis)

    def _semantic_annotation(
        self,
        ann_uri: URIRef,
        target: URIRef,
        body: URIRef,
        basis: URIRef,
        evidence_uris: list[URIRef],
        evidence_text: Optional[str] = None,
        relation_xml_id: Optional[str] = None,
    ):
        assert self.annotation_activity_uri is not None
        self.g.add((ann_uri, RDF.type, LECO.SemanticAnnotation))
        self.g.add((ann_uri, LECO.annotationTarget, target))
        self.g.add((ann_uri, LECO.annotationBody, body))
        self.g.add((ann_uri, LECO.annotationBasis, basis))
        self.g.add((ann_uri, LECO.hasValidationStatus, LECO.HumanValidatedAnnotation))
        self.g.add((ann_uri, PROV.wasGeneratedBy, self.annotation_activity_uri))
        for ev in evidence_uris:
            self.g.add((ann_uri, LECO.attestedIn, ev))
        if evidence_text:
            self.g.add((ann_uri, LECO.evidenceText, Literal(evidence_text)))
        if relation_xml_id and relation_xml_id in self.precision_by_target:
            self.g.add((ann_uri, LECO.confidenceScore, Literal(self.precision_by_target[relation_xml_id], datatype=XSD.decimal)))
        if basis == LECO.InferredFromText and relation_xml_id not in self.precision_by_target:
            self.warn(f"Relación inferida sin <precision>: {relation_xml_id}")

    def _relation_annotation(self, el: ET.Element, body: URIRef):
        xml_id = el.get(XML_ID)
        evidences = [self.resolve(p) for p in split_ptrs(el.get("source"))]
        evidences = [e for e in evidences if e is not None]
        if not evidences:
            # Provenance cannot satisfy SemanticAnnotationShape without a target.
            self.warn(f"Relación {xml_id} sin @source: se genera la relación RDF pero no SemanticAnnotation.")
            return
        ann = self.local_uri(f"{xml_id}-annotation")
        self._semantic_annotation(
            ann, evidences[0], body, self._basis(el.get("subtype")), evidences,
            relation_xml_id=xml_id,
        )

    def _date_resource(self, rel: ET.Element) -> Optional[URIRef]:
        when, start, end = rel.get("when"), rel.get("from"), rel.get("to")
        if not (when or start or end):
            return self.document_date_uri
        uri = self.local_uri(f"{rel.get(XML_ID)}-date")
        self.g.add((uri, RDF.type, RICO.Date))
        if when:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", when):
                self.g.add((uri, TIME.inXSDDate, Literal(when, datatype=XSD.date)))
            elif re.fullmatch(r"\d{4}", when):
                self.g.add((uri, DCTERMS.date, Literal(when, datatype=XSD.gYear)))
            else:
                self.g.add((uri, DCTERMS.date, Literal(when)))
        if start:
            self.g.add((uri, LECO.normalizedForm, Literal(f"from:{start}")))
        if end:
            self.g.add((uri, LECO.normalizedForm, Literal(f"to:{end}")))
        return uri

    def _relations(self):
        assert self.root is not None
        direct_allowed = set(self.mapping.get("controlled_types", {}).get("relation", {}).get("direct_properties", []))
        for el in self.root.findall(".//tei:standOff//tei:relation[@xml:id]", NS):
            typ = el.get("type")
            xml_id = el.get(XML_ID)
            active = self.resolve(first(split_ptrs(el.get("active"))))
            passive = self.resolve(first(split_ptrs(el.get("passive"))))

            if typ == "participation" and active and passive:
                role = self.resolve(first(split_ptrs(el.get("ana"))))
                if not role:
                    self.warn(f"Participation sin rol: {xml_id}"); continue
                uri = self.local_uri(xml_id)
                self.g.add((uri, RDF.type, LECO.Participation))
                self.g.add((uri, LECO.participationActor, active))
                self.g.add((uri, LECO.participationInAct, passive))
                self.g.add((uri, LECO.participationRole, role))
                self.g.add((passive, LECO.hasParticipation, uri))
                self._relation_annotation(el, uri)
                continue

            if typ == "officeHolding" and active and passive:
                office = self.local_uri(f"{xml_id}-office")
                office_type = self.resolve(first(split_ptrs(el.get("ana"))))
                self.g.add((office, RDF.type, LECO.Office)); self.g.add((office, RDF.type, RICO.Position))
                if office_type: self.g.add((office, LECO.hasOfficeType, office_type))
                self.g.add((office, LECO.officeExistsIn, passive))
                uri = self.local_uri(xml_id)
                self.g.add((uri, RDF.type, RICO.PositionHoldingRelation))
                self.g.add((uri, RICO.relationHasSource, active)); self.g.add((uri, RICO.relationHasTarget, office))
                date = self._date_resource(el)
                if date: self.g.add((uri, RICO.relationHasDate, date))
                self.g.add((active, LECO.holdsOffice, office))
                self._relation_annotation(el, uri)
                continue

            if typ == "territorialJurisdiction" and active and passive:
                uri = self.local_uri(xml_id)
                juris_type = self.resolve(first(split_ptrs(el.get("ana")))) or LECO.TerritorialJurisdiction
                self.g.add((uri, RDF.type, juris_type))
                self.g.add((uri, LECO.territorialScope, passive))
                self.g.add((active, LECO.exercisesJurisdiction, uri))
                self.g.add((uri, LECO.jurisdictionExercisedBy, active))
                self._relation_annotation(el, uri)
                continue

            if typ == "historicalCategoryAssignment" and active and passive:
                uri = self.local_uri(xml_id)
                self.g.add((uri, RDF.type, LECO.HistoricalCategoryAssignment))
                self.g.add((uri, LECO.categoryAssignedTo, active))
                self.g.add((uri, LECO.assignsHistoricalCategory, passive))
                evidences = [self.resolve(p) for p in split_ptrs(el.get("source"))]
                for ev in [e for e in evidences if e]: self.g.add((uri, LECO.attestedIn, ev))
                date = self._date_resource(el)
                if date: self.g.add((uri, LECO.categoryAssignmentTime, date))
                corresp = self.resolve(first(split_ptrs(el.get("corresp"))))
                if corresp: self.g.add((uri, LECO.categoryAssignmentJurisdiction, corresp))
                self._relation_annotation(el, uri)
                continue

            if typ == "historicalConceptUse" and passive:
                uri = self.local_uri(xml_id)
                self.g.add((uri, RDF.type, LECO.HistoricalConceptUse))
                self.g.add((uri, LECO.conceptUsed, passive))
                evidences = [self.resolve(p) for p in split_ptrs(el.get("source"))]
                evidences = [e for e in evidences if e]
                for ev in evidences: self.g.add((uri, LECO.attestedIn, ev))
                if evidences:
                    source_id = split_ptrs(el.get("source"))[0].lstrip("#")
                    source_el = self.id_index.get(source_id)
                    lexical = None
                    if source_el is not None:
                        # Prefer the exact inline term that points to the same concept.
                        for term in source_el.iter(qn("term")):
                            ref = first(split_ptrs(term.get("ref") or term.get("ana")))
                            if ref and self.resolve(ref) == passive:
                                lexical = norm_text(term)
                                break
                        lexical = lexical or norm_text(source_el)
                    if lexical:
                        self.g.add((uri, LECO.lexicalForm, Literal(lexical)))
                date = self._date_resource(el)
                if date: self.g.add((uri, LECO.conceptUseTime, date))
                # Explicit context can be supplied in @corresp as a jurisdiction.
                corresp = self.resolve(first(split_ptrs(el.get("corresp"))))
                if corresp: self.g.add((uri, LECO.conceptUseJurisdiction, corresp))
                self._relation_annotation(el, uri)
                continue

            if typ == "objectProperty":
                name = el.get("name")
                if not (name and active and passive):
                    self.warn(f"objectProperty incompleta: {xml_id}"); continue
                if name not in direct_allowed:
                    self.warn(f"Propiedad no autorizada por mapping YAML: {name} ({xml_id})"); continue
                pred = RICO.directlyPrecedesInSequence if name == "directlyPrecedesInSequence" else LECO[name]
                self.g.add((active, pred, passive))
                statement = self.local_uri(f"{xml_id}-statement")
                self.g.add((statement, RDF.type, RDF.Statement))
                self.g.add((statement, RDF.subject, active)); self.g.add((statement, RDF.predicate, pred)); self.g.add((statement, RDF.object, passive))
                self._relation_annotation(el, statement)
                continue

    def _legacy_sidecar_semantics(self):
        # The converter deliberately does not invent complex relations from prose.
        # Legacy TEI will therefore often be incomplete under SHACL until migrated
        # to the mapping profile (standOff + relation structures).
        if self.mode == "legacy-inline":
            self.warn(
                "TEI legacy sin standOff: se convirtió estructura, entidades y actos inline, "
                "pero las relaciones jurisdiccionales/procesales complejas deben migrarse al perfil TEI-LeCO."
            )

    def _derived_rules(self):
        # Authority → jurisdiction lookup.
        authority_juris: dict[URIRef, list[URIRef]] = {}
        for authority, _, juris in self.g.triples((None, LECO.exercisesJurisdiction, None)):
            authority_juris.setdefault(authority, []).append(juris)

        # Decisions/appeals inherit jurisdiction from the authority encoded by the source.
        for predicate in (LECO.decidedBy, LECO.beforeAuthority):
            for act, _, authority in list(self.g.triples((None, predicate, None))):
                for juris in authority_juris.get(authority, []):
                    self.g.add((act, LECO.withinJurisdiction, juris))
                self.g.add((act, LECO.hasParticipant, authority))

        # Persons who are targets of coercive/investigative acts are participants in the broad event sense.
        for predicate in (LECO.sanctions, LECO.investigates, LECO.appointsPerson):
            for act, _, actor in list(self.g.triples((None, predicate, None))):
                self.g.add((act, LECO.hasParticipant, actor))

        # Ordered acts inherit the jurisdiction of the order when no jurisdiction is explicitly present.
        for order, _, ordered in list(self.g.triples((None, LECO.ordersAct, None))):
            if not list(self.g.objects(ordered, LECO.withinJurisdiction)):
                for juris in self.g.objects(order, LECO.withinJurisdiction):
                    self.g.add((ordered, LECO.withinJurisdiction, juris))

        # Historical concept uses: if context is a Cabildo acta and there is exactly one Cabildo jurisdiction,
        # use it as document-level jurisdictional context. This is a structural derivation, not NLP inference.
        cabildo_authorities = [
            s for s in self.g.subjects(LECO.hasInstitutionType, LECO.CabildoType)
            if list(self.g.objects(s, LECO.exercisesJurisdiction))
        ]
        cabildo_juris = {j for a in cabildo_authorities for j in self.g.objects(a, LECO.exercisesJurisdiction)}
        if len(cabildo_juris) == 1:
            cabildo_j = next(iter(cabildo_juris))
            for use in self.g.subjects(RDF.type, LECO.HistoricalConceptUse):
                if not list(self.g.objects(use, LECO.conceptUseJurisdiction)):
                    self.g.add((use, LECO.conceptUseJurisdiction, cabildo_j))
        for use in self.g.subjects(RDF.type, LECO.HistoricalConceptUse):
            if not list(self.g.objects(use, LECO.conceptUseTime)) and self.document_date_uri:
                self.g.add((use, LECO.conceptUseTime, self.document_date_uri))

    def validate_shacl(self, ontology_path: Path, shapes_path: Path, report_path: Path) -> tuple[bool, str]:
        try:
            from pyshacl import validate
        except ImportError as exc:
            raise RuntimeError("pyshacl no está instalado. Ejecuta: pip install -r requirements.txt") from exc
        ontology = Graph().parse(ontology_path, format="turtle")
        shapes = Graph().parse(shapes_path, format="turtle")
        integrated = Graph()
        for prefix, ns in self.g.namespaces(): integrated.bind(prefix, ns)
        for triple in ontology: integrated.add(triple)
        for triple in self.g: integrated.add(triple)
        conforms, report_graph, report_text = validate(
            data_graph=integrated,
            shacl_graph=shapes,
            inference="rdfs",
            advanced=True,
            meta_shacl=True,
            abort_on_first=False,
            allow_infos=True,
            allow_warnings=True,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(report_graph, Graph):
            report_graph.serialize(report_path, format="turtle")
        return bool(conforms), str(report_text)


def resolve_input(input_path: Path, root: Path) -> tuple[str, Path, Optional[Path]]:
    """Resolve document id, TEI path and archival metadata.

    Supports both canonical source folders::

        data/documents/cab-001-002/tei.xml

    and generated enriched TEI files::

        build/tei_enriched/cab-001-002.xml

    Enriched TEI remains a derived artifact, while metadata is recovered from
    data/documents/<document-id>/metadata.json whenever it is not adjacent to
    the XML file.
    """
    if input_path.is_dir():
        doc_name = input_path.name
        tei_path = input_path / "tei.xml"
        metadata_candidates = [input_path / "metadata.json"]
    else:
        tei_path = input_path
        doc_name = input_path.parent.name if input_path.name == "tei.xml" else input_path.stem
        metadata_candidates = [
            input_path.parent / "metadata.json",
            root / "data" / "documents" / doc_name / "metadata.json",
        ]

    metadata_path = next((m for m in metadata_candidates if m.exists()), None)
    return doc_name, tei_path, metadata_path


def convert_one(
    converter: TEILeCOConverter,
    input_path: Path,
    output_path: Path,
    validate: bool,
    ontology_path: Path,
    shapes_path: Path,
    shacl_report_path: Path,
    root: Path,
) -> ConversionReport:
    doc_name, tei_path, metadata_path = resolve_input(input_path, root)
    if not tei_path.exists():
        raise FileNotFoundError(f"No existe TEI: {tei_path}")
    converter.load(tei_path, metadata_path)
    converter.convert()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    converter.g.serialize(output_path, format="turtle")
    conforms = None; shacl_text = None
    if validate:
        conforms, shacl_text = converter.validate_shacl(ontology_path, shapes_path, shacl_report_path)
    return ConversionReport(
        document=doc_name,
        reference_code=converter.reference_code,
        mode=converter.mode,
        triples=len(converter.g),
        output=str(output_path),
        warnings=converter.warnings,
        shacl_conforms=conforms,
        shacl_report=str(shacl_report_path) if validate else None,
    )


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: Optional[list[str]] = None) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description="TEI → LeCO/RDF converter")
    parser.add_argument("input", nargs="?", type=Path, default=root / "data" / "documents",
                        help="Carpeta documental, archivo TEI XML o directorio con --all")
    parser.add_argument("--all", action="store_true",
                        help="Convierte subcarpetas con tei.xml y/o archivos *.xml del directorio indicado")
    parser.add_argument("--output-dir", type=Path, default=root / "build" / "rdf")
    parser.add_argument("--mapping", type=Path, default=root / "mapping" / "tei_to_leco.yaml")
    parser.add_argument("--strict", action="store_true", help="Convierte warnings de mapeo en errores")
    parser.add_argument("--validate", action="store_true", help="Ejecuta SHACL tras convertir")
    parser.add_argument("--ontology", type=Path, default=root / "ontology" / "LeCO.ttl")
    parser.add_argument(
        "--shacl-profile", choices=("core", "quality", "strict"), default="core",
        help="Perfil SHACL: core=integridad (default), quality=advertencias de completitud, strict=gold standard",
    )
    parser.add_argument(
        "--shapes", type=Path, default=None,
        help="Shapes explícitas; si se indica, reemplaza --shacl-profile",
    )
    parser.add_argument(
        "--report-dir", type=Path, default=None,
        help="Directorio de reportes. Por defecto se separa por perfil para evitar sobrescrituras.",
    )
    args = parser.parse_args(argv)

    profile_shapes = {
        "core": root / "shapes" / "LeCO_shapes.ttl",
        "quality": root / "shapes" / "LeCO_quality_shapes.ttl",
        "strict": root / "shapes" / "LeCO_shapes_strict.ttl",
    }
    shapes_path = args.shapes or profile_shapes[args.shacl_profile]
    if args.report_dir is not None:
        report_dir = args.report_dir
    elif args.shapes is not None:
        report_dir = root / "build" / "shacl_reports_custom"
    elif args.shacl_profile == "core":
        report_dir = root / "build" / "shacl_reports"
    else:
        report_dir = root / "build" / f"shacl_reports_{args.shacl_profile}"

    if args.all:
        if not args.input.is_dir():
            parser.error("--all requiere una carpeta raíz")
        source_dirs = sorted(d for d in args.input.iterdir() if d.is_dir() and (d / "tei.xml").exists())
        enriched_files = sorted(p for p in args.input.iterdir() if p.is_file() and p.suffix.lower() == ".xml")
        inputs = source_dirs + enriched_files
    else:
        inputs = [args.input]

    if not inputs:
        print("No se encontraron documentos TEI.", file=sys.stderr)
        return 2

    reports = []
    exit_code = 0
    for input_path in inputs:
        doc_name, _, _ = resolve_input(input_path, root)
        converter = TEILeCOConverter(args.mapping, strict=args.strict)
        out = args.output_dir / f"{doc_name}.ttl"
        shacl_out = report_dir / f"{doc_name}.ttl"
        try:
            report = convert_one(converter, input_path, out, args.validate, args.ontology, shapes_path, shacl_out, root)
            reports.append(report)
            state = ""
            if args.validate:
                state = f" | SHACL[{args.shacl_profile}]: " + ("✓" if report.shacl_conforms else "✗")
                if not report.shacl_conforms: exit_code = 1
            print(f"✓ {report.document}: {report.triples} triples | {report.mode}{state}")
            for warning in report.warnings:
                print(f"  ⚠ {warning}")
        except Exception as exc:
            exit_code = 1
            print(f"✗ {doc_name}: {exc}", file=sys.stderr)

    report_file = args.output_dir / "conversion_report.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps([asdict(r) for r in reports], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Reporte: {report_file}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
