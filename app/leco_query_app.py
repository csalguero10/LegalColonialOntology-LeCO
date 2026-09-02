from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import streamlit as st
from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import RDF

ROOT = Path(__file__).resolve().parents[1]
ASSERTED = ROOT / "build" / "corpus" / "corpus_graph.ttl"
REASONED = ROOT / "build" / "corpus" / "corpus_reasoned.ttl"
DATASET = ROOT / "build" / "corpus" / "corpus_dataset.trig"
QUERY_DIR = ROOT / "queries" / "corpus"
QUALITY_DETAIL = ROOT / "build" / "shacl_quality_legal_analysis.csv"
QUALITY_SUMMARY = ROOT / "build" / "shacl_quality_legal_analysis_summary.csv"

LECO = "https://w3id.org/leco/ontology#"
LECO_GRAPH = "https://w3id.org/leco/graph/"

PREFIXES = """PREFIX leco: <https://w3id.org/leco/ontology#>
PREFIX rico: <https://www.ica.org/standards/RiC/ontology#>
PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX time: <http://www.w3.org/2006/time#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

QUERY_TYPES = {
    "Documentos del corpus": "documents",
    "Personas e instituciones que participan en actos": "participants",
    "Apelaciones": "appeals",
    "Decisiones y autoridades": "decisions",
    "Sanciones": "sanctions",
    "Poder y representación": "representation",
    "Arreglos jurídicos (repartimiento/encomienda)": "legal_arrangements",
    "Argumentos y reglas normativas": "legal_arguments",
    "Oficios": "offices",
    "Actos y jurisdicciones": "jurisdictions",
    "Conceptos históricos": "concepts",
    "Tipos de actos": "act_types",
}

ACT_TYPES = {
    "Todos": None,
    "Apelación": "Appeal",
    "Sanción": "Sanction",
    "Nombramiento": "Appointment",
    "Investigación": "Investigation",
    "Comparecencia": "Appearance",
    "Petición": "Petition",
    "Testimonio": "Testimony",
    "Notificación": "Notification",
    "Presentación": "Presentation",
    "Poder": "GrantOfPower",
    "Pregón": "Proclamation",
    "Lectura": "ReadingAct",
    "Obediencia": "Obedience",
    "Juramento": "Oath",
}

OFFICE_TYPES = {
    "Todos": None,
    "Alcalde": "MayorOfficeType",
    "Juez": "JudgeOfficeType",
    "Regidor": "RegidorOfficeType",
    "Alguacil": "BailiffOfficeType",
    "Procurador": "ProcuradorOfficeType",
    "Escribano": "NotaryOfficeType",
    "Gobernador": "GovernorOfficeType",
    "Capitán": "CaptainOfficeType",
    "Oidor": "OidorOfficeType",
    "Corregidor": "CorregidorOfficeType",
    "Contador": "AccountantOfficeType",
    "Cardenal": "CardinalOfficeType",
}


def local_name(uri: str) -> str:
    if "#" in uri:
        return unquote(uri.rsplit("#", 1)[-1])
    return unquote(uri.rstrip("/").rsplit("/", 1)[-1])


def sig(path: Path):
    stat = path.stat()
    return str(path), stat.st_mtime_ns, stat.st_size


@st.cache_resource(show_spinner=False)
def _load_graph(path_str: str, _mtime: int, _size: int):
    return Graph().parse(path_str, format="turtle")


@st.cache_resource(show_spinner=False)
def _load_dataset(path_str: str, _mtime: int, _size: int):
    return Dataset().parse(path_str, format="trig")


def load_graph(path: Path):
    return _load_graph(*sig(path))


def load_dataset(path: Path):
    return _load_dataset(*sig(path))


@st.cache_data(show_spinner=False)
def _load_csv(path_str: str, _mtime: int, _size: int) -> pd.DataFrame:
    return pd.read_csv(path_str)


def load_csv(path: Path) -> pd.DataFrame:
    return _load_csv(*sig(path))


def result_to_df(result):
    if getattr(result, "type", None) == "ASK":
        return pd.DataFrame([{"ASK": bool(result.askAnswer)}])
    variables = [str(v) for v in result.vars]
    return pd.DataFrame(
        [{var: "" if value is None else str(value) for var, value in zip(variables, row)} for row in result],
        columns=variables,
    )


def abbreviate(value: str):
    repl = {
        LECO: "leco:",
        "https://w3id.org/leco/data/": "data:",
        LECO_GRAPH: "graph:",
        "http://www.w3.org/2004/02/skos/core#": "skos:",
        "http://www.w3.org/ns/prov#": "prov:",
        "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
        "https://www.ica.org/standards/RiC/ontology#": "rico:",
        "http://www.cidoc-crm.org/cidoc-crm/": "crm:",
        "http://www.w3.org/2006/time#": "time:",
        "http://xmlns.com/foaf/0.1/": "foaf:",
        "http://www.w3.org/2001/XMLSchema#": "xsd:",
    }
    for prefix, short in repl.items():
        if value.startswith(prefix):
            return short + value[len(prefix):]
    return value


def abbreviate_df(df: pd.DataFrame):
    if df.empty:
        return df.copy()
    return df.map(lambda x: abbreviate(str(x)) if x not in (None, "") else "")


def saved_queries():
    if not QUERY_DIR.exists():
        return {}
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(QUERY_DIR.glob("*.rq"))}


def dataset_documents(ds: Dataset):
    docs = []
    for ctx in ds.contexts():
        uri = str(ctx.identifier)
        if uri.startswith(LECO_GRAPH):
            docs.append((local_name(uri), uri))
    return sorted(set(docs))


def document_prefixes(ds: Dataset):
    mapping = {}
    legal_doc = URIRef(LECO + "LegalDocument")
    for ctx in ds.contexts():
        graph_uri = str(ctx.identifier)
        if not graph_uri.startswith(LECO_GRAPH):
            continue
        doc_id = local_name(graph_uri)
        for subject in ctx.subjects(RDF.type, legal_doc):
            uri = str(subject)
            if uri.endswith("/record"):
                mapping[doc_id] = uri[:-len("record")]
                break
    return mapping


def doc_filter(var: str, doc_id: str | None, prefixes: dict[str, str]):
    if not doc_id or doc_id not in prefixes:
        return ""
    return f'FILTER(STRSTARTS(STR({var}), "{prefixes[doc_id]}"))'


def wrap_graph(body: str, graph_uri: str | None):
    if graph_uri:
        return f"GRAPH <{graph_uri}> {{\n{body}\n}}"
    return body


def make_guided_query(kind: str, *, limit: int, doc_id: str | None, graph_uri: str | None,
                      prefixes: dict[str, str], use_named_graph: bool,
                      act_type: str | None = None, office_type: str | None = None,
                      require_known: bool = False):
    filt = lambda var: doc_filter(var, doc_id, prefixes)
    graph = graph_uri if use_named_graph else None

    if kind == "documents":
        body = "  ?document a leco:LegalDocument ."
        if doc_id and not use_named_graph:
            body += "\n  " + filt("?document")
        return PREFIXES + f"""\nSELECT DISTINCT ?document\nWHERE {{\n{wrap_graph(body, graph)}\n}}\nORDER BY ?document\nLIMIT {limit}\n"""

    if kind == "participants":
        type_line = f"?act a leco:{act_type} ." if act_type else "?act a ?actType ."
        body = f"""  {type_line}
  {{ ?act leco:hasParticipant ?actor . }}
  UNION
  {{
    ?participation a leco:Participation ;
                   leco:participationActor ?actor ;
                   leco:participationInAct ?act .
    OPTIONAL {{ ?participation leco:participationRole ?role . }}
  }}
  OPTIONAL {{ ?actor rdfs:label ?actorLabel . }}
  OPTIONAL {{ ?actor skos:prefLabel ?actorSkosLabel . }}"""
        if doc_id and not use_named_graph:
            body += "\n  " + filt("?act")
        return PREFIXES + f"""\nSELECT DISTINCT ?actor ?actorLabel ?actorSkosLabel ?act ?role\nWHERE {{\n{wrap_graph(body, graph)}\n}}\nORDER BY ?actor ?act\nLIMIT {limit}\n"""

    if kind == "appeals":
        body = """  ?appeal a leco:Appeal .
  OPTIONAL { ?appeal leco:appealsAgainst ?appealedDecision . }
  OPTIONAL { ?appeal leco:beforeAuthority ?authority . }"""
        if require_known:
            body += "\n  FILTER(BOUND(?appealedDecision) || BOUND(?authority))"
        if doc_id and not use_named_graph:
            body += "\n  " + filt("?appeal")
        return PREFIXES + f"""\nSELECT DISTINCT ?appeal ?appealedDecision ?authority\nWHERE {{\n{wrap_graph(body, graph)}\n}}\nORDER BY ?appeal\nLIMIT {limit}\n"""

    if kind == "decisions":
        body = """  ?decision a leco:LegalDecision .
  OPTIONAL { ?decision leco:decidedBy ?authority . }"""
        if require_known:
            body += "\n  FILTER(BOUND(?authority))"
        if doc_id and not use_named_graph:
            body += "\n  " + filt("?decision")
        return PREFIXES + f"""\nSELECT DISTINCT ?decision ?authority\nWHERE {{\n{wrap_graph(body, graph)}\n}}\nORDER BY ?decision\nLIMIT {limit}\n"""

    if kind == "sanctions":
        body = """  ?sanction a leco:Sanction .
  OPTIONAL { ?sanction leco:sanctions ?sanctioned . }
  OPTIONAL { ?sanctioned rdfs:label ?sanctionedLabel . }"""
        if require_known:
            body += "\n  FILTER(BOUND(?sanctioned))"
        if doc_id and not use_named_graph:
            body += "\n  " + filt("?sanction")
        return PREFIXES + f"""\nSELECT DISTINCT ?sanction ?sanctioned ?sanctionedLabel\nWHERE {{\n{wrap_graph(body, graph)}\n}}\nORDER BY ?sanction\nLIMIT {limit}\n"""

    if kind == "representation":
        body = """  ?grant a leco:GrantOfPower .
  OPTIONAL {
    ?grant leco:createsRepresentation ?relation .
    OPTIONAL { ?relation leco:principal ?principal . }
    OPTIONAL { ?relation leco:representative ?representative . }
  }"""
        if require_known:
            body += "\n  FILTER(BOUND(?relation))"
        if doc_id and not use_named_graph:
            body += "\n  " + filt("?grant")
        return PREFIXES + f"""\nSELECT DISTINCT ?grant ?relation ?principal ?representative\nWHERE {{\n{wrap_graph(body, graph)}\n}}\nORDER BY ?grant\nLIMIT {limit}\n"""

    if kind == "legal_arrangements":
        body = """  { ?act a leco:RepartimientoAct . }
  UNION
  { ?act a leco:EncomiendaGrant . }
  OPTIONAL { ?act leco:resultsInLegalArrangement ?arrangement . }"""
        if require_known:
            body += "\n  FILTER(BOUND(?arrangement))"
        if doc_id and not use_named_graph:
            body += "\n  " + filt("?act")
        return PREFIXES + f"""\nSELECT DISTINCT ?act ?arrangement\nWHERE {{\n{wrap_graph(body, graph)}\n}}\nORDER BY ?act\nLIMIT {limit}\n"""

    if kind == "legal_arguments":
        body = """  {
    ?act leco:hasLegalArgument ?argument .
    OPTIONAL { ?argument leco:argumentInvokesRule ?rule . }
  }
  UNION { ?act leco:citesRule ?rule . }
  UNION { ?act leco:appliesRule ?rule . }
  UNION { ?act leco:interpretsRule ?rule . }
  OPTIONAL { ?rule rdfs:label ?ruleLabel . }"""
        if require_known:
            body += "\n  FILTER(BOUND(?rule))"
        if doc_id and not use_named_graph:
            body += "\n  " + filt("?act")
        return PREFIXES + f"""\nSELECT DISTINCT ?act ?argument ?rule ?ruleLabel\nWHERE {{\n{wrap_graph(body, graph)}\n}}\nORDER BY ?act\nLIMIT {limit}\n"""

    if kind == "offices":
        if office_type:
            office_line = f"?office leco:hasOfficeType leco:{office_type} .\n  BIND(leco:{office_type} AS ?officeType)"
        else:
            office_line = "?office leco:hasOfficeType ?officeType ."
        body = f"""  ?office a leco:Office .
  {office_line}
  OPTIONAL {{
    ?holding a rico:PositionHoldingRelation ;
             rico:relationHasTarget ?office ;
             rico:relationHasSource ?person .
  }}"""
        if doc_id and not use_named_graph:
            body += "\n  " + filt("?office")
        return PREFIXES + f"""\nSELECT DISTINCT ?office ?officeType ?person\nWHERE {{\n{wrap_graph(body, graph)}\n}}\nORDER BY ?officeType ?office\nLIMIT {limit}\n"""

    if kind == "jurisdictions":
        type_line = f"?act a leco:{act_type} ." if act_type else "?act a leco:JurisdictionalAct ."
        body = f"""  {type_line}
  OPTIONAL {{ ?act leco:withinJurisdiction ?jurisdiction . }}"""
        if require_known:
            body += "\n  FILTER(BOUND(?jurisdiction))"
        if doc_id and not use_named_graph:
            body += "\n  " + filt("?act")
        return PREFIXES + f"""\nSELECT DISTINCT ?act ?jurisdiction\nWHERE {{\n{wrap_graph(body, graph)}\n}}\nORDER BY ?act\nLIMIT {limit}\n"""

    if kind == "concepts":
        body = """  ?use a leco:HistoricalConceptUse ;
       leco:conceptUsed ?concept .
  OPTIONAL { ?use leco:lexicalForm ?lexicalForm . }
  OPTIONAL { ?use leco:attestedIn ?evidence . }
  OPTIONAL { ?use leco:conceptUseJurisdiction ?jurisdiction . }
  OPTIONAL { ?use leco:conceptUseTime ?time . }"""
        if doc_id and not use_named_graph:
            body += "\n  " + filt("?use")
        return PREFIXES + f"""\nSELECT DISTINCT ?use ?concept ?lexicalForm ?evidence ?jurisdiction ?time\nWHERE {{\n{wrap_graph(body, graph)}\n}}\nORDER BY ?concept ?use\nLIMIT {limit}\n"""

    if kind == "act_types":
        body = """  ?act a ?actType .
  FILTER(STRSTARTS(STR(?actType), STR(leco:)))
  FILTER(?actType != leco:JurisdictionalAct)"""
        if doc_id and not use_named_graph:
            body += "\n  " + filt("?act")
        return PREFIXES + f"""\nSELECT ?actType (COUNT(DISTINCT ?act) AS ?count)\nWHERE {{\n{wrap_graph(body, graph)}\n}}\nGROUP BY ?actType\nORDER BY DESC(?count)\nLIMIT {limit}\n"""

    raise ValueError(kind)


def entity_relations(graph: Graph, uri: str):
    node = URIRef(uri)
    rows = []
    for p, o in graph.predicate_objects(node):
        rows.append({"dirección": "→", "predicado": str(p), "valor": str(o)})
    for s, p in graph.subject_predicates(node):
        rows.append({"dirección": "←", "predicado": str(p), "valor": str(s)})
    return pd.DataFrame(rows)


def sparql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def search_entities(graph: Graph, term: str, limit: int) -> pd.DataFrame:
    escaped = sparql_escape(term.strip())
    if not escaped:
        return pd.DataFrame(columns=["entity", "label", "type"])
    query = PREFIXES + f"""
SELECT DISTINCT ?entity ?label ?type WHERE {{
  {{ ?entity rdfs:label ?label . }}
  UNION
  {{ ?entity skos:prefLabel ?label . }}
  UNION
  {{ ?entity foaf:name ?label . }}
  FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{escaped}")))
  OPTIONAL {{ ?entity a ?type . }}
}}
ORDER BY ?label
LIMIT {limit}
"""
    rows = [
        {"entity": str(entity), "label": str(label), "type": str(etype) if etype else ""}
        for entity, label, etype in graph.query(query)
    ]
    return pd.DataFrame(rows, columns=["entity", "label", "type"])


st.set_page_config(page_title="LeCO Explorer", page_icon="⚖️", layout="wide")
st.title("LeCO Explorer")
st.caption("Consulta histórica guiada y editor SPARQL para el knowledge graph colonial.")

for path in (ASSERTED, REASONED, DATASET):
    if not path.exists():
        st.error(f"Falta el artefacto {path}. Construye primero build/corpus/.")
        st.stop()

asserted = load_graph(ASSERTED)
reasoned = load_graph(REASONED)
dataset = load_dataset(DATASET)
documents = dataset_documents(dataset)
doc_graphs = dict(documents)
prefixes = document_prefixes(dataset)

with st.sidebar:
    st.header("Fuente semántica")
    source = st.radio("Grafo", ["Afirmado", "Razonado"])
    active = asserted if source == "Afirmado" else reasoned
    st.metric("Triples", f"{len(active):,}")
    st.caption(f"{len(documents)} documentos en el dataset.")
    if st.button("Recargar grafos"):
        st.cache_resource.clear()
        st.rerun()

tab_guided, tab_sparql, tab_entity, tab_quality, tab_help = st.tabs(
    ["Consulta guiada", "SPARQL", "Explorar entidad", "Calidad", "Ayuda"]
)

with tab_guided:
    st.subheader("Construir una consulta sin escribir SPARQL")
    c1, c2 = st.columns(2)
    with c1:
        label = st.selectbox("¿Qué quieres consultar?", list(QUERY_TYPES))
        kind = QUERY_TYPES[label]
        doc_choice = st.selectbox("Documento", ["Todos los documentos"] + [d for d, _ in documents])
        doc_id = None if doc_choice == "Todos los documentos" else doc_choice
        limit = st.number_input("Máximo de resultados", min_value=10, max_value=5000, value=250, step=10)
    act_type = office_type = None
    require_known = False
    with c2:
        if kind in {"participants", "jurisdictions"}:
            act_label = st.selectbox("Tipo de acto", list(ACT_TYPES))
            act_type = ACT_TYPES[act_label]
        if kind == "offices":
            office_label = st.selectbox("Tipo de oficio", list(OFFICE_TYPES))
            office_type = OFFICE_TYPES[office_label]
        if kind in {"appeals", "decisions", "jurisdictions", "sanctions", "representation",
                    "legal_arrangements", "legal_arguments"}:
            require_known = st.checkbox("Mostrar solo casos con la relación identificada")
        if kind == "participants":
            st.info("`hasParticipant` puede referirse a personas o instituciones; el rol fino se modela aparte.")
        if kind == "concepts":
            st.info("LeCO distingue el concepto histórico del uso concreto del concepto en un texto.")
        if kind == "jurisdictions" and not act_type and source == "Afirmado":
            st.warning("Con \"Todos\" los tipos de acto, esta consulta filtra por leco:JurisdictionalAct, que solo se asigna directamente vía razonamiento OWL/RDFS. En el grafo Afirmado no devolverá resultados salvo que elijas un tipo de acto específico o cambies a Razonado.")
        if kind == "act_types" and source == "Afirmado":
            st.warning("Para jerarquías de actos, el grafo Razonado suele ser más completo.")

    use_named_graph = bool(doc_id and source == "Afirmado")
    graph_uri = doc_graphs.get(doc_id) if use_named_graph else None
    query = make_guided_query(
        kind,
        limit=int(limit),
        doc_id=doc_id,
        graph_uri=graph_uri,
        prefixes=prefixes,
        use_named_graph=use_named_graph,
        act_type=act_type,
        office_type=office_type,
        require_known=require_known,
    )

    if source == "Razonado" and doc_id:
        st.caption("En el grafo razonado el filtro documental se aplica por prefijo URI, porque el razonamiento no conserva named graphs.")

    b1, b2 = st.columns([1, 4])
    with b1:
        execute = st.button("Consultar", type="primary")
    with b2:
        show_query = st.checkbox("Ver SPARQL generado")
    if show_query:
        st.code(query, language="sparql")

    if execute:
        try:
            target = dataset if use_named_graph else active
            df = result_to_df(target.query(query))
            st.success(f"{len(df):,} resultado(s).")
            if not df.empty:
                st.dataframe(abbreviate_df(df), width="stretch", hide_index=True)
                st.download_button(
                    "Descargar resultados CSV",
                    df.to_csv(index=False).encode("utf-8-sig"),
                    f"leco_{kind}.csv",
                    "text/csv",
                )
        except Exception as exc:
            st.exception(exc)

with tab_sparql:
    st.subheader("Editor SPARQL")
    queries = saved_queries()
    selected = st.selectbox("Consulta guardada", ["Nueva"] + list(queries))
    default = PREFIXES + "\nSELECT * WHERE { ?s ?p ?o . } LIMIT 100"
    if "sparql_selected" not in st.session_state:
        st.session_state.sparql_selected = None
    if "sparql_editor" not in st.session_state:
        st.session_state.sparql_editor = default
    if selected != st.session_state.sparql_selected:
        st.session_state.sparql_editor = default if selected == "Nueva" else queries[selected]
        st.session_state.sparql_selected = selected
    text = st.text_area("SPARQL", key="sparql_editor", height=340)
    if st.button("Ejecutar SPARQL"):
        try:
            result = active.query(text)
            if getattr(result, "type", None) in {"CONSTRUCT", "DESCRIBE"}:
                ttl = result.graph.serialize(format="turtle")
                st.code(ttl[:20000], language="turtle")
                st.download_button("Descargar Turtle", ttl, "leco_result.ttl", "text/turtle")
            else:
                df = result_to_df(result)
                st.success(f"{len(df):,} fila(s).")
                st.dataframe(abbreviate_df(df), width="stretch", hide_index=True)
                st.download_button("Descargar CSV", df.to_csv(index=False).encode("utf-8-sig"), "leco_result.csv", "text/csv")
        except Exception as exc:
            st.exception(exc)

with tab_entity:
    st.subheader("Buscar por nombre")
    term = st.text_input(
        "Nombre o etiqueta (persona, institución, oficio, concepto...)",
        key="entity_search_term",
        placeholder="Juan de Pineda, Cabildo, escribano...",
    )
    if "entity_search_selected" not in st.session_state:
        st.session_state.entity_search_selected = None
    if term:
        matches = search_entities(active, term, 100)
        if matches.empty:
            st.info("Sin coincidencias.")
        else:
            options = {"— elegir de los resultados —": None}
            for row in matches.itertuples(index=False):
                type_short = abbreviate(row.type) if row.type else "?"
                options[f"{row.label} ({type_short}) — {local_name(row.entity)}"] = row.entity
            picked = st.selectbox("Resultados", list(options), key="entity_search_picked")
            if picked != st.session_state.entity_search_selected and options[picked]:
                st.session_state["entity_uri_input"] = options[picked]
            st.session_state.entity_search_selected = picked
            st.dataframe(
                abbreviate_df(matches.rename(columns={"entity": "uri"})),
                width="stretch", hide_index=True,
            )

    st.subheader("Explorar una URI")
    uri = st.text_input(
        "URI de una persona, institución, acto, oficio, concepto o segmento",
        key="entity_uri_input",
        placeholder="https://w3id.org/leco/data/...",
    )
    if uri:
        df = entity_relations(active, uri.strip())
        if df.empty:
            st.warning("La URI no tiene relaciones en el grafo seleccionado.")
        else:
            df["predicado"] = df["predicado"].map(abbreviate)
            df["valor"] = df["valor"].map(abbreviate)
            st.dataframe(df, width="stretch", hide_index=True)

with tab_quality:
    st.subheader("Deuda de completitud QUALITY")
    st.caption(
        "Advertencias sh:Warning del perfil QUALITY sobre build/tei_legal_curated (capa final vigente). "
        "No bloquean CORE: expresan incompletitud evidencial documentada, no errores. Ver QUALITY.md §3."
    )
    if not QUALITY_SUMMARY.exists():
        st.info(
            "No se encontró build/shacl_quality_legal_analysis_summary.csv. Generalo con:\n\n"
            "```\npython scripts/tei_to_rdf.py build/tei_legal_curated --all "
            "--output-dir build/rdf_legal_curated --validate --shacl-profile quality "
            "--report-dir build/shacl_reports_quality_legal\n"
            "python scripts/analyze_shacl_reports.py --report-dir build/shacl_reports_quality_legal "
            "--output build/shacl_quality_legal_analysis.csv "
            "--summary-output build/shacl_quality_legal_analysis_summary.csv "
            "--json-output build/shacl_quality_legal_analysis.json\n```"
        )
    else:
        summary = load_csv(QUALITY_SUMMARY)
        st.metric("Advertencias QUALITY documentadas", int(summary["count"].sum()))

        qc1, qc2 = st.columns(2)
        with qc1:
            doc_choice = st.selectbox(
                "Documento", ["Todos"] + sorted(summary["document"].unique()), key="quality_doc_filter"
            )
        with qc2:
            path_choice = st.selectbox(
                "Propiedad (result_path)",
                ["Todas"] + sorted(summary["result_path"].dropna().unique()),
                key="quality_path_filter",
            )

        view = summary
        if doc_choice != "Todos":
            view = view[view["document"] == doc_choice]
        if path_choice != "Todas":
            view = view[view["result_path"] == path_choice]

        st.dataframe(
            view.sort_values("count", ascending=False), width="stretch", hide_index=True
        )

        st.caption("Patrones más frecuentes en todo el corpus (sin aplicar los filtros de arriba):")
        by_path = summary.groupby("result_path", dropna=False)["count"].sum().sort_values(ascending=False)
        by_path.index = [str(i) if pd.notna(i) else "(sin resultPath)" for i in by_path.index]
        st.bar_chart(by_path)

        st.download_button(
            "Descargar resumen CSV",
            summary.to_csv(index=False).encode("utf-8-sig"),
            "leco_quality_debt_summary.csv",
            "text/csv",
        )

        with st.expander("Ver casos individuales (detalle)"):
            if QUALITY_DETAIL.exists():
                detail = load_csv(QUALITY_DETAIL)
                if doc_choice != "Todos":
                    detail = detail[detail["document"] == doc_choice]
                if path_choice != "Todas":
                    detail = detail[detail["result_path"] == path_choice]
                st.dataframe(
                    detail[["document", "focus_node", "result_path", "message"]],
                    width="stretch", hide_index=True,
                )
            else:
                st.caption("build/shacl_quality_legal_analysis.csv no encontrado.")

with tab_help:
    st.markdown("""
### Consulta guiada
Genera SPARQL automáticamente. **Ver SPARQL generado** permite documentar o aprender la consulta sin obligar a escribirla.

### Afirmado vs. razonado
**Afirmado** contiene el grafo materializado del corpus. **Razonado** añade consecuencias OWL/RDFS; por ejemplo, una `Appeal` puede recuperarse como `JurisdictionalAct` si LeCO define esa jerarquía.

### Filtro por documento
En el grafo afirmado se usa el named graph del documento. En el razonado se usa el prefijo URI documental porque el cierre OWL-RL se materializó en un grafo unión.

### Buscar por nombre
En "Explorar entidad" podés buscar por etiqueta (nombre de persona, institución, oficio, concepto...) antes de necesitar la URI exacta. Elegir un resultado carga su URI abajo automáticamente.

### Pestaña Calidad
Muestra las advertencias `sh:Warning` del perfil QUALITY ya documentadas en `QUALITY.md` §3 — incompletitud evidencial aceptada, no errores de conversión. Se regenera con `scripts/analyze_shacl_reports.py`.

### Advertencia historiográfica
Una celda vacía puede ser una incompletitud deliberadamente conservada por QUALITY, no necesariamente un error.
""")
