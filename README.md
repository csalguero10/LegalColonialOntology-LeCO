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
