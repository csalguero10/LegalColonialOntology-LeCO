#!/usr/bin/env python3
"""
Build the LeCO corpus knowledge graph from per-document RDF files.

Outputs:
- corpus_graph.ttl: union of instance graphs only
- corpus_dataset.trig: one named graph per document
- corpus_manifest.json: provenance/reproducibility manifest
- corpus_core_report.ttl: optional global CORE SHACL report
- corpus_reasoned.ttl: optional ontology + corpus + OWL-RL closure

The source RDF files are never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import RDF

LECO_DATA = "https://w3id.org/leco/data/"
LECO_GRAPH = "https://w3id.org/leco/graph/"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def discover_rdf_files(input_dir: Path) -> list[Path]:
    files = sorted(
        p for p in input_dir.glob("*.ttl")
        if p.is_file()
        and not p.name.endswith("_report.ttl")
        and p.name not in {
            "corpus_graph.ttl",
            "corpus_reasoned.ttl",
            "corpus_core_report.ttl",
        }
    )
    return files


def document_id_from_path(path: Path) -> str:
    return path.stem


def named_graph_uri(document_id: str) -> URIRef:
    return URIRef(f"{LECO_GRAPH}{document_id}")


def parse_turtle(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path, format="turtle")
    return graph


def build_union_and_dataset(files: Iterable[Path]):
    union = Graph()
    dataset = Dataset()
    manifest_docs = []
    resource_sources: dict[str, set[str]] = defaultdict(set)
    input_triple_sum = 0

    for path in files:
        doc_id = document_id_from_path(path)
        source = parse_turtle(path)
        input_triple_sum += len(source)

        graph_uri = named_graph_uri(doc_id)
        named = dataset.graph(graph_uri)

        for triple in source:
            union.add(triple)
            named.add(triple)
            s = triple[0]
            if isinstance(s, URIRef) and str(s).startswith(LECO_DATA):
                resource_sources[str(s)].add(doc_id)

        manifest_docs.append({
            "document_id": doc_id,
            "named_graph": str(graph_uri),
            "source_file": str(path),
            "source_sha256": sha256_file(path),
            "source_triples": len(source),
        })

    cross_document_subjects = {
        uri: sorted(doc_ids)
        for uri, doc_ids in resource_sources.items()
        if len(doc_ids) > 1
    }

    return union, dataset, manifest_docs, input_triple_sum, cross_document_subjects


def class_counts(graph: Graph, limit: int = 30):
    counts = Counter(str(o) for _, _, o in graph.triples((None, RDF.type, None)))
    return [
        {"class": cls, "count": count}
        for cls, count in counts.most_common(limit)
    ]


def validate_core(corpus: Graph, ontology_path: Path, shapes_path: Path, report_path: Path):
    try:
        from pyshacl import validate
        from pyshacl.errors import ValidationFailure
    except ImportError as exc:
        raise RuntimeError(
            "pyshacl no está instalado. Ejecuta: pip install -r requirements.txt"
        ) from exc

    ontology = parse_turtle(ontology_path)
    shapes = parse_turtle(shapes_path)

    validation_graph = Graph()
    for triple in corpus:
        validation_graph.add(triple)
    for triple in ontology:
        validation_graph.add(triple)

    conforms, report_graph, report_text = validate(
        data_graph=validation_graph,
        shacl_graph=shapes,
        inference="rdfs",
        advanced=True,
        meta_shacl=True,
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
    )

    if isinstance(report_graph, ValidationFailure):
        raise RuntimeError(
            "La validación SHACL no pudo ejecutarse: "
            + str(getattr(report_graph, "message", report_text))
        )

    report_graph.serialize(destination=report_path, format="turtle")
    return bool(conforms), report_text


def reason_corpus(corpus: Graph, ontology_path: Path, output_path: Path):
    try:
        from owlrl import DeductiveClosure, OWLRL_Semantics
    except ImportError as exc:
        raise RuntimeError(
            "owlrl no está instalado. Ejecuta: pip install -r requirements.txt"
        ) from exc

    reasoned = Graph()
    ontology = parse_turtle(ontology_path)

    for triple in ontology:
        reasoned.add(triple)
    for triple in corpus:
        reasoned.add(triple)

    before = len(reasoned)
    DeductiveClosure(OWLRL_Semantics).expand(reasoned)
    after = len(reasoned)
    reasoned.serialize(destination=output_path, format="turtle")
    return before, after


def write_manifest(
    output_path: Path,
    input_dir: Path,
    documents,
    input_triple_sum: int,
    union: Graph,
    cross_document_subjects,
    core_conforms=None,
    reasoning_stats=None,
):
    payload = {
        "artifact": "LeCO corpus graph manifest",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_directory": str(input_dir),
        "document_count": len(documents),
        "input_triple_sum": input_triple_sum,
        "union_triples": len(union),
        "deduplicated_triples": input_triple_sum - len(union),
        "distinct_subjects": len(set(union.subjects())),
        "distinct_predicates": len(set(union.predicates())),
        "top_rdf_types": class_counts(union),
        "named_graph_policy": f"{LECO_GRAPH}{{document_id}}",
        "cross_document_local_subject_count": len(cross_document_subjects),
        "cross_document_local_subjects": cross_document_subjects,
        "core_global_conforms": core_conforms,
        "reasoning": reasoning_stats,
        "documents": documents,
        "methodological_note": (
            "corpus_graph.ttl contiene únicamente la unión de los RDF de instancia. "
            "corpus_dataset.trig conserva la procedencia documental mediante un named graph "
            "por documento. corpus_reasoned.ttl, cuando se genera, es un artefacto derivado "
            "que combina corpus + ontología + cierre OWL-RL y no sustituye la evidencia fuente."
        ),
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    root = Path(__file__).resolve().parents[1]

    parser = argparse.ArgumentParser(description="Construir el knowledge graph conjunto de LeCO.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=root / "build" / "rdf_legal_curated",
        help="Directorio con un .ttl por documento.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "build" / "corpus",
    )
    parser.add_argument(
        "--ontology",
        type=Path,
        default=root / "ontology" / "LeCO.ttl",
    )
    parser.add_argument(
        "--shapes",
        type=Path,
        default=root / "shapes" / "LeCO_shapes.ttl",
        help="Perfil CORE.",
    )
    parser.add_argument("--validate-core", action="store_true")
    parser.add_argument("--reason", action="store_true")
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    files = discover_rdf_files(input_dir)
    if not files:
        raise SystemExit(f"No se encontraron archivos Turtle en {input_dir}")

    union, dataset, documents, input_sum, overlaps = build_union_and_dataset(files)

    corpus_path = output_dir / "corpus_graph.ttl"
    dataset_path = output_dir / "corpus_dataset.trig"
    manifest_path = output_dir / "corpus_manifest.json"

    union.serialize(destination=corpus_path, format="turtle")
    dataset.serialize(destination=dataset_path, format="trig")

    core_conforms = None
    if args.validate_core:
        core_report = output_dir / "corpus_core_report.ttl"
        core_conforms, _ = validate_core(
            union, args.ontology.resolve(), args.shapes.resolve(), core_report
        )

    reasoning_stats = None
    if args.reason:
        reasoned_path = output_dir / "corpus_reasoned.ttl"
        before, after = reason_corpus(
            union, args.ontology.resolve(), reasoned_path
        )
        reasoning_stats = {
            "input_union_plus_ontology_triples": before,
            "reasoned_triples": after,
            "added_by_reasoning": after - before,
            "output": str(reasoned_path),
        }

    write_manifest(
        manifest_path,
        input_dir,
        documents,
        input_sum,
        union,
        overlaps,
        core_conforms=core_conforms,
        reasoning_stats=reasoning_stats,
    )

    print("LeCO corpus graph")
    print(f"Documents: {len(documents)}")
    print(f"Input triples (sum): {input_sum:,}")
    print(f"Union triples:       {len(union):,}")
    print(f"Deduplicated:        {input_sum - len(union):,}")
    print(f"Named graphs:        {len(documents)}")
    print(f"Cross-document local subjects: {len(overlaps)}")
    if args.validate_core:
        print(f"Global CORE SHACL: {'✓' if core_conforms else '✗'}")
    if reasoning_stats:
        print(
            "Reasoning: "
            f"{reasoning_stats['input_union_plus_ontology_triples']:,} "
            f"→ {reasoning_stats['reasoned_triples']:,} triples"
        )
    print("\nOutputs:")
    print(f"  Union:    {corpus_path}")
    print(f"  Dataset:  {dataset_path}")
    print(f"  Manifest: {manifest_path}")
    if args.validate_core:
        print(f"  CORE:     {output_dir / 'corpus_core_report.ttl'}")
    if reasoning_stats:
        print(f"  Reasoned: {output_dir / 'corpus_reasoned.ttl'}")


if __name__ == "__main__":
    main()
