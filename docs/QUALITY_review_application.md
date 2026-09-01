# LeCO — aplicación de revisiones QUALITY v0.1

## Objetivo

`quality_triage_reviewed.csv` es ahora un **registro de decisiones humanas**. No es un archivo temporal de `build/`: debe conservarse en:

```text
reviews/quality/quality_triage_reviewed.csv
```

El script `scripts/apply_quality_reviews.py` lee ese registro y crea una nueva capa TEI:

```text
build/tei_enriched/   → entrada automática
build/tei_curated/    → salida después de revisión humana
```

Nunca sobrescribe los TEI fuente de `data/documents/` ni los TEI enriquecidos.

## Política de aplicación

Los cuatro estados del CSV tienen consecuencias distintas:

- `explicit_recoverable`: se intenta materializar la relación como evidencia textual explícita.
- `contextual_inference`: se intenta materializar únicamente cuando sujeto y objeto pueden resolverse de forma inequívoca; se marca `subtype="inferred"` y se añade `tei:precision`.
- `keep_warning`: no se modifica el grafo. La ausencia se conserva deliberadamente.
- `needs_review`: no se modifica el grafo.

**Aprobado no significa adivinado.** Si una fila `explicit_recoverable` o `contextual_inference` no permite resolver un target único desde el TEI, se registra como `pending` o `deferred`.

## Nuevas estructuras TEI soportadas

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

El conversor actualizado reconoce estos nodos y permite además las relaciones directas `hasParticipant`, `principal` y `representative`.

Las relaciones de representación (`createsRepresentation`) se mantienen deliberadamente **diferidas** en esta versión: algunos poderes del corpus nombran más de un procurador y el perfil actual de `RepresentationRelation` todavía debe revisarse para representar multiplicidad sin pérdida histórica.

## Ejecución

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

En la copia del corpus usada para probar este script se obtuvieron 19 TEI curados y 310 decisiones procesadas. El aplicador conservador materializó 86 decisiones automáticamente; 88 quedaron diferidas, 47 pendientes y 89 no se aplicaron por política (`keep_warning` o `needs_review`). Los números pueden variar si los TEI enriquecidos cambian.

## Después de aplicar las revisiones

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

CORE debería seguir siendo conforme. Si aparece una violación CORE, no continúes rellenando warnings: primero hay que corregir esa regresión estructural.

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

El nuevo total de warnings debe compararse con la línea base anterior (aprox. 309). No se espera que llegue a cero.

## Cómo leer el reporte de aplicación

`quality_review_application.csv` usa:

- `applied`: relación materializada en `tei_curated`.
- `already_present`: ya estaba representada.
- `deferred`: decisión aprobada que conviene recalcular después de otras relaciones. El caso principal es `withinJurisdiction`, porque muchas jurisdicciones pueden derivarse una vez recuperado `decidedBy`.
- `pending`: la decisión fue aprobada, pero el target no puede resolverse inequívocamente sin más revisión.
- `not_applied_by_policy`: `keep_warning` o `needs_review`.

No edites `build/quality_review_application_pending.csv` como si fuera una lista de errores. Primero se vuelve a ejecutar QUALITY sobre `tei_curated`; varias filas diferidas pueden desaparecer automáticamente gracias a reglas derivadas.
