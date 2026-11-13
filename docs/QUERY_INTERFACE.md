# LeCO SPARQL Explorer

> 🌐 **English** · [Español](#version-en-espanol) — the original Spanish version is kept below.

Local web interface for querying the LeCO knowledge graph.

## Installation

Add:

```text
streamlit>=1.36
```

to `requirements.txt` and run:

```bash
pip install -r requirements.txt
```

Or directly:

```bash
pip install streamlit
```

## Launch

From the repository root:

```bash
streamlit run app/leco_query_app.py
```

It will normally open at:

```text
http://localhost:8501
```

## Modes

- **Asserted**: `build/corpus/corpus_graph.ttl`
- **Reasoned**: `build/corpus/corpus_reasoned.ttl`
- **Per-document dataset**: `build/corpus/corpus_dataset.trig`

The distinction between asserted and reasoned is deliberately kept so that results
materialised in the corpus can be separated from results derived by OWL-RL.

## Features

- SPARQL editor;
- saved queries from `queries/corpus/*.rq`;
- asserted/reasoned/named-graphs selector;
- results table;
- full or abbreviated URIs;
- CSV download;
- CONSTRUCT/DESCRIBE and Turtle download;
- URI exploration;
- basic graph statistics.

---

<a id="version-en-espanol"></a>

> 🌐 [English](#) · **Español** — versión original en español.

# LeCO SPARQL Explorer

Interfaz web local para consultar el knowledge graph de LeCO.

## Instalación

Añadir:

```text
streamlit>=1.36
```

a `requirements.txt` y ejecutar:

```bash
pip install -r requirements.txt
```

O directamente:

```bash
pip install streamlit
```

## Arranque

Desde la raíz:

```bash
streamlit run app/leco_query_app.py
```

Normalmente se abrirá:

```text
http://localhost:8501
```

## Modos

- **Afirmado**: `build/corpus/corpus_graph.ttl`
- **Razonado**: `build/corpus/corpus_reasoned.ttl`
- **Dataset por documento**: `build/corpus/corpus_dataset.trig`

La distinción entre afirmado y razonado se conserva deliberadamente para poder
separar resultados materializados en el corpus de resultados derivados por OWL-RL.

## Funciones

- editor SPARQL;
- consultas guardadas de `queries/corpus/*.rq`;
- selector afirmado/razonado/named graphs;
- tabla de resultados;
- URIs completas o abreviadas;
- descarga CSV;
- CONSTRUCT/DESCRIBE y descarga Turtle;
- exploración de una URI;
- estadísticas básicas del grafo.
