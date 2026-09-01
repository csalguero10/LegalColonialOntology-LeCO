# LeCO QUALITY evidence triage v0.1

`quality_triage.py` conecta cada `sh:Warning` del perfil QUALITY con su evidencia textual sin modificar el corpus ni completar relaciones automáticamente.

## Principio metodológico

Un warning expresa incompletitud deseable, no necesariamente error. El triage debe permitir distinguir después entre:

1. información explícita que el pipeline omitió;
2. información inferible con contexto y procedencia;
3. caso que requiere revisión humana;
4. información genuinamente desconocida.

El script **no decide** entre esas cuatro posibilidades. Solo prepara la evidencia para revisión.

## Entradas

Por defecto:

```text
build/shacl_quality_analysis.csv
build/rdf/<document>.ttl
build/tei_enriched/<document>.xml
data/documents/<document>/tei.xml
```

El texto se toma preferentemente del TEI fuente `data/documents/.../tei.xml`; el TEI enriquecido se usa para resolver `standOff`, `@source` y `@corresp` y como fallback.

## Salidas

```text
build/quality_triage.csv
build/quality_triage.json
build/quality_triage_unresolved.csv
```

La tabla principal contiene una fila por warning y, entre otros, estos campos:

- `document`
- `result_path`
- `focus_node`
- `focus_types`
- `focus_label`
- `evidence_xml_ids`
- `evidence_text`
- `evidence_method`
- `suggested_action`
- `review_status`
- `reviewer_note`

`review_status` comienza en `pending`. La tabla está pensada para revisión humana y puede actualizarse con valores como `explicit_recoverable`, `contextual_inference`, `keep_warning`, `needs_review`.

## Ejecución

Desde la raíz del repositorio:

```bash
python scripts/quality_triage.py
```

Antes debe existir el detalle QUALITY generado por:

```bash
python scripts/analyze_shacl_reports.py \
  --report-dir build/shacl_reports_quality \
  --output build/shacl_quality_analysis.csv \
  --summary-output build/shacl_quality_analysis_summary.csv \
  --json-output build/shacl_quality_analysis.json
```

## Cómo encuentra evidencia

El orden de búsqueda es conservador:

1. `focusNode leco:attestedIn segmento`;
2. `segmento leco:documentsAct focusNode`;
3. evidencia de `leco:SemanticAnnotation` cuyo cuerpo es el nodo;
4. punteros TEI `@corresp` / `@source` del `standOff`;
5. como último recurso, el `xml:id` del segmento preservado dentro de la URI generada.

El quinto mecanismo solo localiza la procedencia estructural del nodo; **no crea ninguna relación jurídica**.
