from pathlib import Path
import ast

APP = Path(__file__).resolve().parents[1] / "app" / "leco_query_app.py"

def test_syntax():
    ast.parse(APP.read_text(encoding="utf-8"))

def test_guided_layer_exists():
    text = APP.read_text(encoding="utf-8")
    assert "Consulta guiada" in text
    assert "make_guided_query" in text
    assert "¿Qué quieres consultar?" in text

def test_guided_domains():
    text = APP.read_text(encoding="utf-8")
    for value in ["Apelaciones", "Decisiones y autoridades", "Oficios", "Actos y jurisdicciones", "Conceptos históricos"]:
        assert value in text

def test_document_and_reasoned_filters():
    text = APP.read_text(encoding="utf-8")
    assert "document_prefixes" in text
    assert "use_named_graph" in text
    assert "Razonado" in text

def test_export_and_transparency():
    text = APP.read_text(encoding="utf-8")
    assert "Ver SPARQL generado" in text
    assert "Descargar resultados CSV" in text
