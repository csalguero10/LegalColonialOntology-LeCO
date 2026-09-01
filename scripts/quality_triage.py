#!/usr/bin/env python3
"""Connect LeCO SHACL QUALITY warnings to their textual evidence.

The script reads the detailed CSV produced by ``analyze_shacl_reports.py`` for
QUALITY, then resolves each warning against the generated RDF and the TEI.
It is deliberately read-only with respect to source/enriched TEI and RDF.

Default inputs (from repository root)::

    build/shacl_quality_analysis.csv
    build/rdf/<document>.ttl
    build/tei_enriched/<document>.xml
    data/documents/<document>/tei.xml

Default outputs::

    build/quality_triage.csv
    build/quality_triage.json
    build/quality_triage_unresolved.csv

The original TEI under data/documents is preferred for evidence text. The
stand-off enriched TEI is used for structural pointers and as a fallback.
No missing legal relation is asserted or repaired by this script.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import unquote
import xml.etree.ElementTree as ET

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
XML_ID = f"{{{XML_NS}}}id"
NS = {"tei": TEI_NS}

LECO = Namespace("https://w3id.org/leco/ontology#")

DATA_URI_SEGMENT_RE = re.compile(r"(cab-\d{3}-\d{3}_s\d+)", re.IGNORECASE)

ACTION_MAP = {
    "withinJurisdiction": (
        "review_jurisdiction_context",
        "Revisar autoridad/institución y contexto documental. Solo añadir jurisdicción si está explícita o si se registra como inferencia contextual con procedencia.",
    ),
    "decidedBy": (
        "review_deciding_authority",
        "Comprobar quién adopta la decisión en el segmento y su contexto inmediato; no asumir Cabildo automáticamente si el texto no lo permite.",
    ),
    "sanctions": (
        "review_sanction_target",
        "Identificar el destinatario de la sanción si está textual o inequívocamente contextualizado; conservar el warning si no puede determinarse.",
    ),
    "createsRepresentation": (
        "review_representation_relation",
        "Revisar el poder: principal, representante y relación creada. No convertir la mera palabra 'poder' en representación completa sin evidencia.",
    ),
    "appointsPerson": (
        "review_appointment_person",
        "Comprobar la persona nombrada en el segmento y si el mapping/enriquecimiento omitió una relación explícita.",
    ),
    "appointsToOffice": (
        "review_appointment_office",
        "Comprobar el oficio al que se nombra. Normalizar el tipo de oficio sin borrar la forma histórica del texto.",
    ),
    "resultsInLegalArrangement": (
        "review_legal_arrangement",
        "Revisar si el acto produce realmente un régimen/arreglo jurídico (p. ej. repartimiento/merced) o si la fuente solo menciona el término.",
    ),
    "appealsAgainst": (
        "review_appealed_decision",
        "Identificar la decisión/acto contra el cual se apela, solo si el texto o el contexto documental lo sustentan.",
    ),
    "beforeAuthority": (
        "review_appeal_authority",
        "Identificar la autoridad ante la que se interpone la apelación y registrar inferencia/procedencia si no es textual directa.",
    ),
    "conceptUseJurisdiction": (
        "review_concept_jurisdiction",
        "Revisar si el uso conceptual puede contextualizarse jurisdiccionalmente; mantener warning cuando el alcance no sea seguro.",
    ),
    "conceptUseTime": (
        "review_concept_time",
        "Revisar fecha del segmento/documento. Si se hereda la fecha documental, registrarla como contexto derivado y no como fecha textual del término.",
    ),
    "investigates": (
        "review_investigation_target",
        "Identificar qué persona, conducta o asunto se investiga si la fuente lo expresa; de lo contrario conservar el warning.",
    ),
}


@dataclass
class TriageRow:
    document: str
    severity: str
    constraint: str
    result_path: str
    message: str
    focus_node: str
    focus_types: str
    focus_label: str
    evidence_uris: str
    evidence_xml_ids: str
    evidence_text: str
    evidence_file: str
    evidence_method: str
    suggested_action: str
    suggested_action_note: str
    review_status: str
    reviewer_note: str


def norm_text(el: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def uri_local(uri: str) -> str:
    if not uri:
        return ""
    return unquote(uri.rstrip("/").rsplit("/", 1)[-1])


def local_name(value: str) -> str:
    if not value:
        return ""
    if value.startswith("leco:"):
        return value[5:]
    if "#" in value:
        return value.rsplit("#", 1)[-1]
    if "/" in value:
        return value.rsplit("/", 1)[-1]
    return value


def load_tei_index(path: Optional[Path]) -> dict[str, str]:
    if not path or not path.exists():
        return {}
    root = ET.parse(path).getroot()
    return {
        el.get(XML_ID): norm_text(el)
        for el in root.iter()
        if el.get(XML_ID)
    }


def load_enriched_root(path: Optional[Path]) -> tuple[Optional[ET.Element], dict[str, ET.Element]]:
    if not path or not path.exists():
        return None, {}
    root = ET.parse(path).getroot()
    return root, {el.get(XML_ID): el for el in root.iter() if el.get(XML_ID)}


def compact_uri(term) -> str:
    if term is None:
        return ""
    text = str(term)
    if text.startswith(str(LECO)):
        return "leco:" + text[len(str(LECO)):]
    return text


def graph_label(g: Graph, focus: URIRef) -> str:
    labels = [str(x) for x in g.objects(focus, RDFS.label)]
    if not labels:
        labels = [str(x) for x in g.objects(focus, LECO.lexicalForm)]
    return " | ".join(dict.fromkeys(labels))


def graph_types(g: Graph, focus: URIRef) -> str:
    vals = [compact_uri(x) for x in g.objects(focus, RDF.type)]
    return " | ".join(dict.fromkeys(vals))


def evidence_candidates(g: Graph, focus: URIRef) -> list[tuple[URIRef, str]]:
    """Return evidence URIs with the route used to obtain them."""
    out: list[tuple[URIRef, str]] = []

    # 1) Nodes such as HistoricalConceptUse / assignments may carry evidence directly.
    for ev in g.objects(focus, LECO.attestedIn):
        if isinstance(ev, URIRef):
            out.append((ev, "focus leco:attestedIn"))

    # 2) Acts/events are normally linked from the segment via leco:documentsAct.
    for ev in g.subjects(LECO.documentsAct, focus):
        if isinstance(ev, URIRef):
            out.append((ev, "segment leco:documentsAct focus"))

    # 3) Relation/statement nodes are bodies of semantic annotations with provenance.
    for ann in g.subjects(LECO.annotationBody, focus):
        for ev in g.objects(ann, LECO.attestedIn):
            if isinstance(ev, URIRef):
                out.append((ev, "SemanticAnnotation leco:attestedIn"))

    # 4) Less common: an annotation may directly target the focus node.
    for ann in g.subjects(LECO.annotationTarget, focus):
        for ev in g.objects(ann, LECO.attestedIn):
            if isinstance(ev, URIRef):
                out.append((ev, "annotationTarget provenance"))

    # Stable de-duplication preserving the strongest/first route.
    seen: set[str] = set()
    unique: list[tuple[URIRef, str]] = []
    for uri, method in out:
        if str(uri) not in seen:
            seen.add(str(uri))
            unique.append((uri, method))
    return unique


def tei_pointer_evidence(
    focus_uri: str,
    enriched_index: dict[str, ET.Element],
) -> list[tuple[str, str]]:
    """Fallback to explicit TEI standOff @corresp/@source pointers."""
    local = uri_local(focus_uri)
    el = enriched_index.get(local)
    out: list[tuple[str, str]] = []
    if el is not None:
        for attr in ("corresp", "source"):
            for ptr in (el.get(attr) or "").split():
                if ptr.startswith("#"):
                    out.append((ptr[1:], f"TEI @{attr}"))
    return out


def heuristic_segment_id(focus_uri: str) -> Optional[str]:
    match = DATA_URI_SEGMENT_RE.search(unquote(focus_uri))
    return match.group(1) if match else None


def action_for(result_path: str, constraint: str) -> tuple[str, str]:
    prop = local_name(result_path)
    if prop in ACTION_MAP:
        return ACTION_MAP[prop]
    if not result_path and local_name(constraint) == "OrConstraintComponent":
        return (
            "review_participant",
            "Revisar si el segmento identifica actor/participante del acto. Si solo se deduce del contexto, modelar la inferencia con evidencia y confianza; si no, conservar el warning.",
        )
    return (
        "human_review",
        "Revisar el warning junto con su evidencia antes de modificar TEI, mapping u ontología.",
    )


def choose_evidence_text(
    evidence_ids: list[str],
    source_index: dict[str, str],
    enriched_index_text: dict[str, str],
) -> tuple[list[str], str]:
    texts: list[str] = []
    files: list[str] = []
    for xml_id in evidence_ids:
        text = source_index.get(xml_id)
        if text:
            texts.append(text)
            files.append("source-tei")
            continue
        text = enriched_index_text.get(xml_id)
        if text:
            texts.append(text)
            files.append("enriched-tei")
    # de-duplicate exact repeated segments
    texts = list(dict.fromkeys(texts))
    files = list(dict.fromkeys(files))
    return texts, " | ".join(files)


def process_warning(
    row: dict[str, str],
    rdf_dir: Path,
    enriched_dir: Path,
    source_documents_dir: Path,
    graph_cache: dict[str, Graph],
    tei_cache: dict[str, tuple[dict[str, str], dict[str, str], dict[str, ET.Element]]],
) -> TriageRow:
    document = row["document"]
    rdf_path = rdf_dir / f"{document}.ttl"
    if document not in graph_cache:
        g = Graph()
        if rdf_path.exists():
            g.parse(rdf_path, format="turtle")
        graph_cache[document] = g
    g = graph_cache[document]

    if document not in tei_cache:
        source_path = source_documents_dir / document / "tei.xml"
        enriched_path = enriched_dir / f"{document}.xml"
        source_index = load_tei_index(source_path)
        enriched_root, enriched_elements = load_enriched_root(enriched_path)
        enriched_text = {
            xml_id: norm_text(el) for xml_id, el in enriched_elements.items()
        }
        tei_cache[document] = (source_index, enriched_text, enriched_elements)
    source_index, enriched_text, enriched_elements = tei_cache[document]

    focus_text = row.get("focus_node", "")
    focus = URIRef(focus_text) if focus_text.startswith(("http://", "https://")) else None

    candidates: list[tuple[str, str]] = []
    if focus is not None:
        candidates.extend((str(uri), method) for uri, method in evidence_candidates(g, focus))

    # Fallback to the enriched TEI pointers if RDF provenance is absent.
    if not candidates:
        for xml_id, method in tei_pointer_evidence(focus_text, enriched_elements):
            candidates.append((xml_id, method))

    # Last-resort structural heuristic: focus IDs generated from inline/event IDs
    # retain the segment identifier. This does not assert semantics; it only finds
    # the segment from which the generated node originated.
    if not candidates:
        seg_id = heuristic_segment_id(focus_text)
        if seg_id:
            candidates.append((seg_id, "focus URI contains TEI segment xml:id"))

    evidence_uris: list[str] = []
    evidence_ids: list[str] = []
    methods: list[str] = []
    for raw, method in candidates:
        if raw.startswith(("http://", "https://")):
            evidence_uris.append(raw)
            evidence_ids.append(uri_local(raw))
        else:
            evidence_ids.append(raw)
        methods.append(method)
    evidence_uris = list(dict.fromkeys(evidence_uris))
    evidence_ids = list(dict.fromkeys(evidence_ids))
    methods = list(dict.fromkeys(methods))

    texts, evidence_file_kind = choose_evidence_text(evidence_ids, source_index, enriched_text)
    action, action_note = action_for(row.get("result_path", ""), row.get("constraint", ""))

    return TriageRow(
        document=document,
        severity=row.get("severity", ""),
        constraint=row.get("constraint", ""),
        result_path=row.get("result_path", ""),
        message=row.get("message", ""),
        focus_node=focus_text,
        focus_types=graph_types(g, focus) if focus is not None else "",
        focus_label=graph_label(g, focus) if focus is not None else "",
        evidence_uris=" || ".join(evidence_uris),
        evidence_xml_ids=" || ".join(evidence_ids),
        evidence_text=" || ".join(texts),
        evidence_file=evidence_file_kind,
        evidence_method=" || ".join(methods),
        suggested_action=action,
        suggested_action_note=action_note,
        review_status="pending",
        reviewer_note="",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: Iterable[TriageRow]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(TriageRow.__dataclass_fields__)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_json(path: Path, rows: list[TriageRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "warning_count": len(rows),
        "warnings_with_textual_evidence": sum(bool(r.evidence_text) for r in rows),
        "warnings_without_textual_evidence": sum(not bool(r.evidence_text) for r in rows),
        "review_status_counts": {
            "pending": sum(r.review_status == "pending" for r in rows),
        },
        "rows": [asdict(r) for r in rows],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description="Connect LeCO QUALITY warnings with TEI evidence.")
    p.add_argument("--analysis", type=Path, default=root / "build" / "shacl_quality_analysis.csv")
    p.add_argument("--rdf-dir", type=Path, default=root / "build" / "rdf")
    p.add_argument("--enriched-dir", type=Path, default=root / "build" / "tei_enriched")
    p.add_argument("--source-documents-dir", type=Path, default=root / "data" / "documents")
    p.add_argument("--output", type=Path, default=root / "build" / "quality_triage.csv")
    p.add_argument("--json-output", type=Path, default=root / "build" / "quality_triage.json")
    p.add_argument("--unresolved-output", type=Path, default=root / "build" / "quality_triage_unresolved.csv")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.analysis.exists():
        raise SystemExit(
            f"No existe {args.analysis}. Ejecuta primero analyze_shacl_reports.py sobre build/shacl_reports_quality."
        )

    source_rows = read_csv(args.analysis)
    graph_cache: dict[str, Graph] = {}
    tei_cache: dict[str, tuple[dict[str, str], dict[str, str], dict[str, ET.Element]]] = {}
    triage = [
        process_warning(
            row,
            args.rdf_dir,
            args.enriched_dir,
            args.source_documents_dir,
            graph_cache,
            tei_cache,
        )
        for row in source_rows
    ]

    write_csv(args.output, triage)
    write_json(args.json_output, triage)
    unresolved = [r for r in triage if not r.evidence_text]
    write_csv(args.unresolved_output, unresolved)

    print("LeCO QUALITY evidence triage")
    print(f"Warnings: {len(triage)}")
    print(f"With textual evidence: {len(triage) - len(unresolved)}")
    print(f"Without textual evidence: {len(unresolved)}")
    print("\nOutputs:")
    print(f"  Review table: {args.output}")
    print(f"  JSON:        {args.json_output}")
    print(f"  Unresolved:  {args.unresolved_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
