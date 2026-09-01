# LeCO — perfil QUALITY: triage, aplicación y estado actual

Documento consolidado. Antes eran tres archivos separados (`QUALITY_evidence_triage.md`,
`QUALITY_review_application.md`, `QUALITY_gaps_tei_legal_curated.md`); se agruparon aquí en
el orden en que operan sobre el corpus: primero cómo se triagan los warnings QUALITY, luego
cómo se aplican las decisiones revisadas, y por último el estado de deuda documentada sobre
la capa final vigente (`build/tei_legal_curated`).

## Índice

1. [Triage de evidencia QUALITY](#1-triage-de-evidencia-quality-quality_triagepy)
2. [Aplicación de revisiones QUALITY](#2-aplicación-de-revisiones-quality-apply_quality_reviewspy)
3. [Deuda de completitud documentada sobre `tei_legal_curated`](#3-deuda-de-completitud-documentada-sobre-build-tei_legal_curated)

---

## 1. Triage de evidencia QUALITY (`quality_triage.py`)

### Principio metodológico

`quality_triage.py` conecta cada `sh:Warning` del perfil QUALITY con su evidencia textual sin
modificar el corpus ni completar relaciones automáticamente.

Un warning expresa incompletitud deseable, no necesariamente error. El triage debe permitir
distinguir después entre:

1. información explícita que el pipeline omitió;
2. información inferible con contexto y procedencia;
3. caso que requiere revisión humana;
4. información genuinamente desconocida.

El script **no decide** entre esas cuatro posibilidades. Solo prepara la evidencia para revisión.

### Entradas

Por defecto:

```text
build/shacl_quality_analysis.csv
build/rdf/<document>.ttl
build/tei_enriched/<document>.xml
data/documents/<document>/tei.xml
```

El texto se toma preferentemente del TEI fuente `data/documents/.../tei.xml`; el TEI
enriquecido se usa para resolver `standOff`, `@source` y `@corresp` y como fallback.

### Salidas

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

`review_status` comienza en `pending`. La tabla está pensada para revisión humana y puede
actualizarse con valores como `explicit_recoverable`, `contextual_inference`, `keep_warning`,
`needs_review`.

### Ejecución

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

### Cómo encuentra evidencia

El orden de búsqueda es conservador:

1. `focusNode leco:attestedIn segmento`;
2. `segmento leco:documentsAct focusNode`;
3. evidencia de `leco:SemanticAnnotation` cuyo cuerpo es el nodo;
4. punteros TEI `@corresp` / `@source` del `standOff`;
5. como último recurso, el `xml:id` del segmento preservado dentro de la URI generada.

El quinto mecanismo solo localiza la procedencia estructural del nodo; **no crea ninguna
relación jurídica**.

---

## 2. Aplicación de revisiones QUALITY (`apply_quality_reviews.py`)

### Objetivo

`quality_triage_reviewed.csv` es un **registro de decisiones humanas**. No es un archivo
temporal de `build/`: debe conservarse en:

```text
reviews/quality/quality_triage_reviewed.csv
```

El script `scripts/apply_quality_reviews.py` lee ese registro y crea una nueva capa TEI:

```text
build/tei_enriched/   → entrada automática
build/tei_curated/    → salida después de revisión humana
```

Nunca sobrescribe los TEI fuente de `data/documents/` ni los TEI enriquecidos.

### Política de aplicación

Los cuatro estados del CSV tienen consecuencias distintas:

- `explicit_recoverable`: se intenta materializar la relación como evidencia textual explícita.
- `contextual_inference`: se intenta materializar únicamente cuando sujeto y objeto pueden
  resolverse de forma inequívoca; se marca `subtype="inferred"` y se añade `tei:precision`.
- `keep_warning`: no se modifica el grafo. La ausencia se conserva deliberadamente.
- `needs_review`: no se modifica el grafo.

**Aprobado no significa adivinado.** Si una fila `explicit_recoverable` o
`contextual_inference` no permite resolver un target único desde el TEI, se registra como
`pending` o `deferred`.

### Nuevas estructuras TEI soportadas

La curaduría puede crear en `standOff`:

```xml
<interpGrp type="offices">
  <interp xml:id="..." ana="https://w3id.org/leco/ontology#NotaryOfficeType">
    Escribano público
  </interp>
</interpGrp>
```

y:

```xml
<interpGrp type="legalArrangements">
  <interp xml:id="..." ana="https://w3id.org/leco/ontology#LegalArrangement">
    Arreglo jurídico asociado al repartimiento
  </interp>
</interpGrp>
```

El conversor actualizado reconoce estos nodos y permite además las relaciones directas
`hasParticipant`, `principal` y `representative`.

Las relaciones de representación (`createsRepresentation`) se mantienen deliberadamente
**diferidas** en esta versión: algunos poderes del corpus nombran más de un procurador y el
perfil actual de `RepresentationRelation` todavía debe revisarse para representar
multiplicidad sin pérdida histórica.

### Ejecución

Desde la raíz del repositorio:

```bash
python scripts/apply_quality_reviews.py
```

Usa por defecto:

```text
reviews/quality/quality_triage_reviewed.csv
build/tei_enriched/
data/documents/
```

y genera:

```text
build/tei_curated/
build/quality_review_application.csv
build/quality_review_application_pending.csv
build/quality_review_application.json
```

En la copia del corpus usada para probar este script se obtuvieron 19 TEI curados y 310
decisiones procesadas. El aplicador conservador materializó 86 decisiones automáticamente; 88
quedaron diferidas, 47 pendientes y 89 no se aplicaron por política (`keep_warning` o
`needs_review`). Los números pueden variar si los TEI enriquecidos cambian.

### Después de aplicar las revisiones

Primero valida CORE sobre la nueva capa curada:

```bash
python scripts/tei_to_rdf.py \
  build/tei_curated \
  --all \
  --output-dir build/rdf_curated \
  --validate \
  --shacl-profile core \
  --report-dir build/shacl_reports_core_curated
```

CORE debería seguir siendo conforme. Si aparece una violación CORE, no continúes rellenando
warnings: primero hay que corregir esa regresión estructural.

Después ejecuta QUALITY:

```bash
python scripts/tei_to_rdf.py \
  build/tei_curated \
  --all \
  --output-dir build/rdf_curated \
  --validate \
  --shacl-profile quality \
  --report-dir build/shacl_reports_quality_curated
```

Y analiza los nuevos reportes:

```bash
python scripts/analyze_shacl_reports.py \
  --report-dir build/shacl_reports_quality_curated \
  --output build/shacl_quality_curated_analysis.csv \
  --summary-output build/shacl_quality_curated_analysis_summary.csv \
  --json-output build/shacl_quality_curated_analysis.json
```

El nuevo total de warnings debe compararse con la línea base anterior (aprox. 309). No se
espera que llegue a cero.

> Nota (2026-09-01): `build/tei_curated`, `build/rdf_curated` y los reportes
> `*_curated`/`*_participant`/`*_inferred` mencionados arriba ya no están en `build/` — se
> eliminaron por ser etapas intermedias ya superadas por `build/tei_legal_curated` (ver
> sección 3). Los comandos de esta sección siguen siendo válidos para **regenerarlos** si se
> necesita repetir el ciclo desde cero; nada de esto se perdió, todo deriva de
> `build/tei_enriched/` + `reviews/quality/quality_triage_reviewed.csv`.

### Cómo leer el reporte de aplicación

`quality_review_application.csv` usa:

- `applied`: relación materializada en `tei_curated`.
- `already_present`: ya estaba representada.
- `deferred`: decisión aprobada que conviene recalcular después de otras relaciones. El caso
  principal es `withinJurisdiction`, porque muchas jurisdicciones pueden derivarse una vez
  recuperado `decidedBy`.
- `pending`: la decisión fue aprobada, pero el target no puede resolverse inequívocamente sin
  más revisión.
- `not_applied_by_policy`: `keep_warning` o `needs_review`.

No edites `build/quality_review_application_pending.csv` como si fuera una lista de errores.
Primero se vuelve a ejecutar QUALITY sobre `tei_curated`; varias filas diferidas pueden
desaparecer automáticamente gracias a reglas derivadas.

---

## 3. Deuda de completitud documentada sobre `build/tei_legal_curated`

### Estado (2026-09-01, ontología LeCO 0.4.0)

Capa TEI auditada: `build/tei_legal_curated` (etapa final del pipeline: enriquecimiento →
curaduría QUALITY → curaduría de participantes → curaduría de relaciones legales).

- **CORE**: 19/19 documentos conformes. 0 violaciones estructurales, 0 warnings de
  conversión (sin punteros rotos, sin referencias sin resolver).
- **QUALITY**: 19/19 documentos conformes (los resultados son severidad `sh:Warning`,
  que no bloquea `conforms`). 163 resultados de completitud sobre el conjunto.

Artefactos oficiales que respaldan estos números:

```text
build/rdf_legal_curated/conversion_report.json
build/shacl_reports_core_legal/*.ttl
build/shacl_reports_quality_legal/*.ttl
build/shacl_quality_legal_analysis.csv
build/shacl_quality_legal_analysis.json
build/shacl_quality_legal_analysis_summary.csv
```

Regenerar con:

```bash
python scripts/tei_to_rdf.py build/tei_legal_curated --all \
  --output-dir build/rdf_legal_curated --validate --shacl-profile quality \
  --report-dir build/shacl_reports_quality_legal
python scripts/analyze_shacl_reports.py \
  --report-dir build/shacl_reports_quality_legal \
  --output build/shacl_quality_legal_analysis.csv \
  --summary-output build/shacl_quality_legal_analysis_summary.csv \
  --json-output build/shacl_quality_legal_analysis.json
```

### Por qué se documenta como deuda aceptada y no como error

Un `sh:Warning` en el perfil QUALITY expresa incompletitud evidencial, no un defecto de
modelado ni de conversión (sección 1 de este documento). Los 163 casos restantes ya pasaron
por las reglas de derivación estructural D001–D005 (`scripts/tei_to_rdf.py:782-847`,
documentadas en `TEI_to_LeCO.md` §4), que se ejecutan por defecto en cada conversión. Lo que
queda es exactamente lo que esas reglas dejan deliberadamente sin resolver: actos sin
autoridad decisora identificable, o con varias autoridades/jurisdicciones posibles donde
resolver automáticamente sería inventar evidencia. Cerrarlos requiere releer el texto fuente
y decidir caso por caso si hay base documental — el mismo tipo de trabajo que ya se hizo para
participantes (`PARTICIPANT.md`) y relaciones legales (`LEGAL_RELATION.md`), con el mismo
ciclo auditoría → CSV de revisión humana → aplicación conservadora. Se decidió no abrir ese
ciclo por ahora; esta sección fija la línea base para cuando se retome.

### Desglose actual (163 resultados)

| Ruta (`sh:resultPath`) | Casos | Documentos afectados | Mensaje |
|---|---:|---:|---|
| `leco:withinJurisdiction` | 92 | 17 | Sin jurisdicción identificada para el acto |
| _(sin resultPath — shape compuesta)_ | 28 | 12 | Acto sin ningún participante identificado |
| `leco:decidedBy` | 10 | 8 | Sin decisor identificado |
| `leco:sanctions` | 9 | 7 | Sin sancionado identificado |
| `leco:createsRepresentation` | 8 | 7 | Otorgamiento de poder sin relación de representación enlazada |
| `leco:appointsPerson` | 3 | 3 | Sin persona nombrada identificada |
| `leco:resultsInLegalArrangement` | 3 | 2 | Repartimiento sin arreglo/régimen jurídico enlazado |
| `leco:appealsAgainst` | 2 | 2 | Sin decisión apelada identificada |
| `leco:appointsToOffice` | 2 | 2 | Sin oficio de nombramiento identificado |
| `leco:beforeAuthority` | 2 | 2 | Sin autoridad de apelación identificada |
| `leco:conceptUseJurisdiction` | 2 | 2 | Uso de concepto histórico sin contexto jurisdiccional |
| `leco:conceptUseTime` | 2 | 1 | Uso de concepto histórico sin contexto temporal |

`leco:withinJurisdiction` concentra el 56% de la deuda y es, por lejos, el candidato más
rentable si en el futuro se abre un nuevo ciclo de revisión.

### Qué no es esta deuda

No incluye `cab-001-058`: ese documento nunca entró al pipeline de enriquecimiento porque
`data/texts/cab-001-058.txt` está vacío (sin transcripción disponible desde la fuente). No es
un defecto del pipeline; no hay texto que curar.
