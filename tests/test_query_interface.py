from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "leco_query_app.py"

def test_app_python_syntax():
    ast.parse(APP.read_text(encoding="utf-8"))

def test_app_references_corpus_artifacts():
    text = APP.read_text(encoding="utf-8")
    assert "corpus_graph.ttl" in text
    assert "corpus_reasoned.ttl" in text
    assert "corpus_dataset.trig" in text

def test_app_supports_saved_queries_and_csv_download():
    text = APP.read_text(encoding="utf-8")
    assert 'QUERY_DIR = ROOT / "queries" / "corpus"' in text
    assert "download_button" in text
    assert "to_csv" in text
