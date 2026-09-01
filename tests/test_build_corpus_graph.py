from pathlib import Path

from rdflib import Graph, URIRef

from scripts.build_corpus_graph import (
    build_union_and_dataset,
    discover_rdf_files,
    named_graph_uri,
)


def _write(path: Path, text: str):
    path.write_text(text, encoding="utf-8")


def test_union_and_named_graphs(tmp_path):
    a = tmp_path / "cab-001-001.ttl"
    b = tmp_path / "cab-001-002.ttl"

    _write(a, """
        @prefix ex: <https://example.org/> .
        ex:a ex:p ex:x .
        ex:shared ex:p ex:x .
    """)
    _write(b, """
        @prefix ex: <https://example.org/> .
        ex:b ex:p ex:y .
        ex:shared ex:p ex:x .
    """)

    files = discover_rdf_files(tmp_path)
    union, dataset, docs, input_sum, overlaps = build_union_and_dataset(files)

    assert len(files) == 2
    assert input_sum == 4
    assert len(union) == 3
    assert len(docs) == 2
    assert len(dataset.graph(named_graph_uri("cab-001-001"))) == 2
    assert len(dataset.graph(named_graph_uri("cab-001-002"))) == 2


def test_named_graph_policy():
    assert str(named_graph_uri("cab-001-002")) == (
        "https://w3id.org/leco/graph/cab-001-002"
    )


def test_discovers_only_source_turtle_files(tmp_path):
    _write(tmp_path / "cab-001-002.ttl", "@prefix ex: <https://example.org/> . ex:a ex:p ex:b .")
    _write(tmp_path / "corpus_graph.ttl", "@prefix ex: <https://example.org/> . ex:c ex:p ex:d .")
    _write(tmp_path / "corpus_core_report.ttl", "@prefix ex: <https://example.org/> . ex:c ex:p ex:d .")

    files = discover_rdf_files(tmp_path)
    assert [p.name for p in files] == ["cab-001-002.ttl"]
