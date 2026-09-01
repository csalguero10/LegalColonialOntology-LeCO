from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from rdflib import Dataset, Graph, URIRef

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ASSERTED = ROOT / "build" / "corpus" / "corpus_graph.ttl"
DEFAULT_REASONED = ROOT / "build" / "corpus" / "corpus_reasoned.ttl"
DEFAULT_DATASET = ROOT / "build" / "corpus" / "corpus_dataset.trig"
QUERY_DIR = ROOT / "queries" / "corpus"

PREFIXES = """PREFIX leco: <https://w3id.org/leco/ontology#>
PREFIX rico: <https://www.ica.org/standards/RiC/ontology#>
PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
"""

WELCOME_QUERY = PREFIXES + """
SELECT ?document
WHERE {
  ?document a leco:LegalDocument .
}
ORDER BY ?document
LIMIT 100
"""


def path_signature(path: Path):
    if not path.exists():
        return (str(path), None, None)
    stat = path.stat()
    return (str(path), stat.st_mtime_ns, stat.st_size)


@st.cache_resource(show_spinner=False)
def load_graph_cached(path_str: str, mtime_ns: int | None, size: int | None, fmt: str):
    graph = Graph()
    graph.parse(Path(path_str), format=fmt)
    return graph


@st.cache_resource(show_spinner=False)
def load_dataset_cached(path_str: str, mtime_ns: int | None, size: int | None):
    dataset = Dataset()
    dataset.parse(Path(path_str), format="trig")
    return dataset


def load_graph(path: Path, fmt="turtle"):
    sig = path_signature(path)
    if sig[1] is None:
        raise FileNotFoundError(path)
    return load_graph_cached(*sig, fmt)


def load_dataset(path: Path):
    sig = path_signature(path)
    if sig[1] is None:
        raise FileNotFoundError(path)
    return load_dataset_cached(*sig)


def saved_queries(query_dir: Path):
    if not query_dir.exists():
        return {}
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(query_dir.glob("*.rq"))}


def result_to_dataframe(result):
    if getattr(result, "type", None) == "ASK":
        return pd.DataFrame([{"ASK": bool(result.askAnswer)}])
    variables = [str(v) for v in result.vars]
    rows = []
    for row in result:
        rows.append({var: "" if value is None else str(value) for var, value in zip(variables, row)})
    return pd.DataFrame(rows, columns=variables)


def short_uri(value: str):
    replacements = {
        "https://w3id.org/leco/ontology#": "leco:",
        "https://w3id.org/leco/data/": "data:",
        "https://w3id.org/leco/graph/": "graph:",
        "http://www.w3.org/2004/02/skos/core#": "skos:",
        "http://www.w3.org/ns/prov#": "prov:",
        "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    }
    for prefix, replacement in replacements.items():
        if value.startswith(prefix):
            return replacement + value[len(prefix):]
    return value


def shorten_dataframe(df: pd.DataFrame):
    if df.empty:
        return df.copy()
    return df.applymap(lambda x: short_uri(str(x)) if x not in (None, "") else "")


def graph_stats(graph):
    return {
        "Triples": len(graph),
        "Subjects": len(set(graph.subjects())),
        "Predicates": len(set(graph.predicates())),
        "Objects": len(set(graph.objects())),
    }


def uri_description(graph: Graph, uri: str):
    node = URIRef(uri)
    rows = []
    for p, o in graph.predicate_objects(node):
        rows.append({"direction": "→", "predicate": str(p), "value": str(o)})
    for s, p in graph.subject_predicates(node):
        rows.append({"direction": "←", "predicate": str(p), "value": str(s)})
    return pd.DataFrame(rows)


st.set_page_config(page_title="LeCO SPARQL Explorer", page_icon="⚖️", layout="wide")
st.title("LeCO SPARQL Explorer")
st.caption(
    "Consulta local del knowledge graph colonial. "
    "El grafo afirmado conserva lo materializado; el razonado incorpora inferencias OWL-RL."
)

with st.sidebar:
    st.header("Grafo")
    graph_mode = st.radio(
        "Fuente de consulta",
        ["Afirmado", "Razonado", "Dataset por documento"],
        help=(
            "Afirmado = corpus_graph.ttl. Razonado = corpus_reasoned.ttl. "
            "Dataset = corpus_dataset.trig con named graphs."
        ),
    )

    if graph_mode == "Afirmado":
        selected_path = DEFAULT_ASSERTED
        graph_format = "turtle"
    elif graph_mode == "Razonado":
        selected_path = DEFAULT_REASONED
        graph_format = "turtle"
    else:
        selected_path = DEFAULT_DATASET
        graph_format = "trig"

    try:
        st.code(str(selected_path.relative_to(ROOT)))
    except ValueError:
        st.code(str(selected_path))

    if not selected_path.exists():
        st.error(f"No existe {selected_path}")
        st.stop()

    with st.spinner("Cargando grafo..."):
        graph = load_dataset(selected_path) if graph_mode == "Dataset por documento" else load_graph(selected_path, graph_format)

    stats = graph_stats(graph)
    st.metric("Triples", f"{stats['Triples']:,}")
    st.caption(
        f"{stats['Subjects']:,} sujetos · {stats['Predicates']:,} predicados · {stats['Objects']:,} objetos"
    )

    st.divider()
    st.header("Consultas guardadas")
    queries = saved_queries(QUERY_DIR)
    choices = ["Consulta nueva"] + list(queries)
    selected_query = st.selectbox("Abrir", choices)

    if st.button("Recargar archivos"):
        st.cache_resource.clear()
        st.rerun()


if "editor_text" not in st.session_state:
    st.session_state.editor_text = WELCOME_QUERY
if "selected_query_previous" not in st.session_state:
    st.session_state.selected_query_previous = None

if selected_query != st.session_state.selected_query_previous:
    if selected_query == "Consulta nueva":
        st.session_state.editor_text = PREFIXES + "\nSELECT * WHERE {\n  ?s ?p ?o .\n}\nLIMIT 100\n"
    else:
        st.session_state.editor_text = queries[selected_query]
    st.session_state.selected_query_previous = selected_query

tab_query, tab_entity, tab_help = st.tabs(["Consulta SPARQL", "Explorar URI", "Ayuda"])

with tab_query:
    query_text = st.text_area("SPARQL", key="editor_text", height=360)

    col_run, col_prefix, col_clear = st.columns([1, 1, 4])
    with col_run:
        execute = st.button("▶ Ejecutar", type="primary")
    with col_prefix:
        if st.button("+ Prefijos"):
            current = st.session_state.editor_text
            if "PREFIX leco:" not in current:
                st.session_state.editor_text = PREFIXES + "\n" + current
                st.rerun()
    with col_clear:
        st.caption("SELECT, ASK, CONSTRUCT y DESCRIBE son compatibles con RDFLib.")

    if execute:
        try:
            with st.spinner("Ejecutando SPARQL..."):
                result = graph.query(query_text)

            if getattr(result, "type", None) in {"CONSTRUCT", "DESCRIBE"}:
                result_graph = result.graph
                st.success(f"{len(result_graph):,} triples en el resultado.")
                ttl = result_graph.serialize(format="turtle")
                st.code(ttl[:20000], language="turtle")
                st.download_button(
                    "Descargar Turtle",
                    data=ttl,
                    file_name="leco_query_result.ttl",
                    mime="text/turtle",
                )
            else:
                df = result_to_dataframe(result)
                st.success(f"{len(df):,} fila(s).")
                display_mode = st.radio("Mostrar URIs", ["Completas", "Abreviadas"], horizontal=True)
                shown = df if display_mode == "Completas" else shorten_dataframe(df)
                st.dataframe(shown, use_container_width=True, hide_index=True)
                st.download_button(
                    "Descargar CSV",
                    data=df.to_csv(index=False).encode("utf-8-sig"),
                    file_name="leco_query_result.csv",
                    mime="text/csv",
                )
        except Exception as exc:
            st.error("La consulta no pudo ejecutarse.")
            st.exception(exc)

with tab_entity:
    st.write(
        "Pega una URI del corpus para ver sus relaciones salientes y entrantes."
    )
    uri_value = st.text_input(
        "URI",
        placeholder="https://w3id.org/leco/data/co-ahrb-cab-001-d002/...",
    )
    if uri_value:
        try:
            if graph_mode == "Dataset por documento":
                temp = Graph()
                for context in graph.contexts():
                    for triple in context:
                        temp.add(triple)
                entity_df = uri_description(temp, uri_value.strip())
            else:
                entity_df = uri_description(graph, uri_value.strip())

            if entity_df.empty:
                st.warning("No se encontraron triples para esa URI en el grafo seleccionado.")
            else:
                short_df = entity_df.copy()
                short_df["predicate"] = short_df["predicate"].map(short_uri)
                short_df["value"] = short_df["value"].map(short_uri)
                st.dataframe(short_df, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.exception(exc)

with tab_help:
    st.subheader("¿Qué grafo conviene usar?")
    st.markdown(
        """
**Afirmado**  
Úsalo para ver el grafo materializado del corpus.

**Razonado**  
Úsalo para consultas que dependen de jerarquías OWL/RDFS. Por ejemplo, una instancia
tipada como `leco:Appeal` puede aparecer también como `leco:JurisdictionalAct`
después del razonamiento.

**Dataset por documento**  
Úsalo para consultar la procedencia documental mediante `GRAPH`.
        """
    )

    st.subheader("Ejemplo con named graphs")
    st.code(
        PREFIXES
        + """
SELECT ?documentGraph (COUNT(*) AS ?triples)
WHERE {
  GRAPH ?documentGraph {
    ?s ?p ?o .
  }
}
GROUP BY ?documentGraph
ORDER BY ?documentGraph
""",
        language="sparql",
    )
