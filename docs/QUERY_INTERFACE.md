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
