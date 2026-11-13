# LegalColonialOntology-LeCO

> 🌐 **English** · [Español](#version-en-espanol) — the original Spanish version is kept below.

**LegalColonialOntology (LeCO)** is a domain ontology for representing the documents, actors, offices, procedural roles, acts, jurisdictions, norms, concepts and historical-legal categories of the colonial Ibero-American jurisdictional culture.

Main namespace:

```turtle
@prefix leco: <https://w3id.org/leco/ontology#> .
```

## Repository structure

```text
LegalColonialOntology-LeCO/
├── ontology/
│   ├── LeCO.ttl
│   └── LeCO.owl
├── shapes/
│   └── LeCO_shapes.ttl
├── data/
│   └── pineda_example.ttl
├── queries/
│   └── core/
│       ├── C01_people_in_acts.rq
│       └── ...
├── scripts/
│   ├── check_rdf.py
│   ├── validate_shacl.py
│   ├── reason.py
│   ├── run_queries.py
│   └── run_all.py
├── tests/
│   ├── test_rdf_syntax.py
│   ├── test_shacl.py
│   ├── test_reasoning.py
│   └── test_core_cqs.py
├── docs/
│   └── LeCO_CQ_matrix_v0_3_resolved.xlsx
├── .vscode/
│   ├── settings.json
│   └── tasks.json
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 1. Create the Python environment

Python 3.11 or 3.12 is recommended.

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

In VS Code, select the `.venv` interpreter via **Python: Select Interpreter**.

## 2. Check that the RDF/Turtle files load

```bash
python scripts/check_rdf.py
```

Checks syntax and shows the number of triples in the ontology, the shapes and the example data.

## 3. Validate SHACL

```bash
python scripts/validate_shacl.py
```

SHACL uses three conceptually separate graphs:

- **ontology graph**: `ontology/LeCO.ttl`, defines the semantic model.
- **shapes graph**: `shapes/LeCO_shapes.ttl`, defines which conditions the data must meet.
- **data graph**: `data/pineda_example.ttl`, contains concrete instances.

The script exits with code `0` when the data conforms and `1` when there are violations.

## 4. Run OWL-RL reasoning

```bash
python scripts/reason.py
```

The inferred result is saved to:

```text
build/reasoned_graph.ttl
```

Reasoning complements SHACL but does not replace it. OWL/RDFS makes it possible to infer knowledge; SHACL checks completeness and the constraints of the data profile.

## 5. Run the core Competency Questions

```bash
python scripts/run_queries.py
```

For a specific query:

```bash
python scripts/run_queries.py --query C06
```

The SPARQL queries are in `queries/core/`.

## 6. Run the full test suite

```bash
pytest -q
```

The tests check:

1. RDF/Turtle syntax;
2. SHACL validation of the Pineda example;
3. basic inference of the LeCO hierarchy via OWL-RL;
4. execution of the 12 core Competency Questions.

You can also run:

```bash
python scripts/run_all.py
```

## Project methodological workflow

```text
Source / transcription
        ↓
TEI XML
        ↓
Semantic annotation
        ↓
RDF + LeCO
        ↓
SHACL
        ↓
Validated RDF
        ↓
Reasoning
        ↓
SPARQL / Knowledge Graph
```

## Important

`data/pineda_example.ttl` is a **test fixture**, not the definitive ABox of the corpus. Its purpose is to check that the ontology, shapes and scripts work before transforming the 20 documents.

The next phase of the project is to formally define and test the **TEI → RDF/LeCO** mapping, and then generate a validated ABox for the pilot corpus.

---

<a id="version-en-espanol"></a>

> 🌐 [English](#) · **Español** — versión original en español.

# LegalColonialOntology-LeCO

**LegalColonialOntology (LeCO)** es una ontología de dominio para representar documentos, actores, oficios, roles procesales, actos, jurisdicciones, normas, conceptos y categorías jurídico-históricas de la cultura jurisdiccional colonial iberoamericana.

Namespace principal:

```turtle
@prefix leco: <https://w3id.org/leco/ontology#> .
```

## Estructura del repositorio

```text
LegalColonialOntology-LeCO/
├── ontology/
│   ├── LeCO.ttl
│   └── LeCO.owl
├── shapes/
│   └── LeCO_shapes.ttl
├── data/
│   └── pineda_example.ttl
├── queries/
│   └── core/
│       ├── C01_people_in_acts.rq
│       └── ...
├── scripts/
│   ├── check_rdf.py
│   ├── validate_shacl.py
│   ├── reason.py
│   ├── run_queries.py
│   └── run_all.py
├── tests/
│   ├── test_rdf_syntax.py
│   ├── test_shacl.py
│   ├── test_reasoning.py
│   └── test_core_cqs.py
├── docs/
│   └── LeCO_CQ_matrix_v0_3_resolved.xlsx
├── .vscode/
│   ├── settings.json
│   └── tasks.json
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 1. Crear el entorno Python

Se recomienda Python 3.11 o 3.12.

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

En VS Code selecciona el intérprete de `.venv` desde **Python: Select Interpreter**.

## 2. Comprobar que los RDF/Turtle cargan

```bash
python scripts/check_rdf.py
```

Comprueba sintaxis y muestra el número de triples de la ontología, las shapes y el ejemplo de datos.

## 3. Validar SHACL

```bash
python scripts/validate_shacl.py
```

SHACL usa tres grafos conceptualmente separados:

- **ontology graph**: `ontology/LeCO.ttl`, define el modelo semántico.
- **shapes graph**: `shapes/LeCO_shapes.ttl`, define qué condiciones deben cumplir los datos.
- **data graph**: `data/pineda_example.ttl`, contiene instancias concretas.

El script termina con código `0` cuando los datos conforman y `1` cuando hay violaciones.

## 4. Ejecutar razonamiento OWL-RL

```bash
python scripts/reason.py
```

El resultado inferido se guarda en:

```text
build/reasoned_graph.ttl
```

El razonamiento complementa SHACL, pero no lo sustituye. OWL/RDFS permite inferir conocimiento; SHACL comprueba completitud y restricciones del perfil de datos.

## 5. Ejecutar las Competency Questions núcleo

```bash
python scripts/run_queries.py
```

Para una consulta concreta:

```bash
python scripts/run_queries.py --query C06
```

Las consultas SPARQL están en `queries/core/`.

## 6. Ejecutar toda la batería de tests

```bash
pytest -q
```

Los tests comprueban:

1. sintaxis RDF/Turtle;
2. validación SHACL del ejemplo de Pineda;
3. inferencia básica de la jerarquía LeCO mediante OWL-RL;
4. ejecución de las 12 Competency Questions núcleo.

También puedes ejecutar:

```bash
python scripts/run_all.py
```

## Flujo metodológico del proyecto

```text
Fuente / transcripción
        ↓
TEI XML
        ↓
Anotación semántica
        ↓
RDF + LeCO
        ↓
SHACL
        ↓
RDF validado
        ↓
Reasoning
        ↓
SPARQL / Knowledge Graph
```

## Importante

`data/pineda_example.ttl` es un **test fixture**, no la ABox definitiva del corpus. Su finalidad es comprobar que ontología, shapes y scripts funcionan antes de transformar los 20 documentos.

La próxima fase del proyecto es definir y probar formalmente el mapeo **TEI → RDF/LeCO**, y luego generar una ABox validada para el corpus piloto.
