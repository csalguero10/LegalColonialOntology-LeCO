#!/usr/bin/env python3
"""Build the modeling/typing review queue from legal-relation rows marked needs_review."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def classify(row: dict[str, str]) -> tuple[str, str]:
    prop = row["property"].split(":", 1)[-1]
    text = (row.get("segment_text") or "").casefold()
    note = (row.get("relation_reviewer_note") or "").casefold()
    if prop in {"appointsPerson", "appointsToOffice"}:
        if "gestion" in text or "solicita" in text or "propone" in text:
            return "appointment_status_or_request", "Revisar si el nodo es Appointment consumado, solicitud/propuesta de nombramiento o alegación sobre un nombramiento en trámite."
        return "appointment_entity_or_status", "Resolver persona/oficio faltante y comprobar si el nombramiento es un acto consumado."
    if prop in {"appealsAgainst", "beforeAuthority"}:
        if "funcion" in note or "futura" in note or "poder" in text:
            return "authorized_or_generic_appeal", "Revisar si el nodo representa una apelación concreta o una facultad/función autorizada por un poder."
        return "appeal_context", "Revisar objeto y autoridad de la apelación en el contexto procesal antes de afirmar relaciones concretas."
    if prop == "sanctions":
        return "generic_or_conditional_sanction", "Revisar si existe una sanción singular con destinatario concreto o una pena general/condicional."
    if prop == "decidedBy":
        if any(term in note for term in ("normativa", "general", "prescripción", "hipotética", "tipificación")):
            return "normative_statement_vs_decision", "Revisar si el nodo es realmente una LegalDecision singular o una prescripción/regla general."
        return "authority_context", "Revisar autoridad emisora/decisora usando contexto documental más amplio; no resolver por proximidad nominal."
    return "modeling_review", "Revisar la tipificación del evento y la relación faltante antes de modificar el grafo."


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description="Build LeCO event/modeling review queue")
    ap.add_argument("--reviews", type=Path, default=root / "reviews" / "legal_relations" / "legal_relation_audit_review_queue_reviewed.csv")
    ap.add_argument("--output", type=Path, default=root / "build" / "event_typing_review_queue.csv")
    ap.add_argument("--json-output", type=Path, default=root / "build" / "event_typing_review_queue.json")
    args = ap.parse_args()

    with args.reviews.open("r", encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("relation_review_status") == "needs_review"]

    out = []
    for r in rows:
        category, suggestion = classify(r)
        out.append({
            "document": r["document"],
            "property": r["property"],
            "focus_xml_id": r["focus_xml_id"],
            "focus_types": r["focus_types"],
            "focus_label": r["focus_label"],
            "segment_id": r["segment_id"],
            "segment_text": r["segment_text"],
            "previous_segment_text": r["previous_segment_text"],
            "next_segment_text": r["next_segment_text"],
            "review_issue_category": category,
            "suggested_modeling_action": suggestion,
            "source_review_note": r["relation_reviewer_note"],
            "proposed_event_type": "",
            "proposed_modeling_pattern": "",
            "typing_review_status": "pending",
            "typing_reviewer_note": "",
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(out[0]) if out else [
        "document","property","focus_xml_id","focus_types","focus_label","segment_id","segment_text",
        "previous_segment_text","next_segment_text","review_issue_category","suggested_modeling_action",
        "source_review_note","proposed_event_type","proposed_modeling_pattern","typing_review_status","typing_reviewer_note"
    ]
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(out)
    args.json_output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("LeCO event/modeling review queue")
    print(f"Rows: {len(out)}")
    counts = {}
    for r in out: counts[r['review_issue_category']] = counts.get(r['review_issue_category'], 0) + 1
    for k in sorted(counts): print(f"  {counts[k]} × {k}")
    print(f"CSV: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
