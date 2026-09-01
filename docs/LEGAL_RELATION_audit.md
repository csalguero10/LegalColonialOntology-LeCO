# Auditoría QUALITY de relaciones jurídicas — v0.1

Esta fase revisa únicamente seis relaciones de alto valor jurídico que siguen apareciendo como `sh:Warning` después de la curaduría de participantes:

- `leco:decidedBy`
- `leco:sanctions`
- `leco:appointsPerson`
- `leco:appointsToOffice`
- `leco:appealsAgainst`
- `leco:beforeAuthority`

## Principio

El script es **solo diagnóstico**. No añade relaciones ni modifica TEI/RDF. Su función es poner delante del revisor:

- el acto que dispara el warning;
- su segmento TEI y contexto anterior/posterior;
- personas e instituciones candidatas con `xml:id` exacto;
- eventos jurídicos vecinos con `xml:id` exacto;
- menciones de oficio con `xml:id` exacto.

La revisión humana se anota exclusivamente en:

- `approved_target_xml_id`
- `approved_basis`: `explicit`, `contextual`, `unknown`
- `approved_confidence`: 0–1 si es contextual
- `relation_review_status`: `approved`, `keep_warning`, `needs_review`
- `relation_reviewer_note`

No se deben escribir nombres libres como target. El futuro aplicador solo aceptará `xml:id` aprobados.

## Ejecución

```bash
python scripts/legal_relation_audit.py
```

Entradas por defecto:

```text
build/shacl_quality_participant_analysis.csv
build/tei_participant_curated/*.xml
build/rdf_participant_curated/*.ttl
```

Salidas:

```text
build/legal_relation_audit.csv
build/legal_relation_audit_review_queue.csv
build/legal_relation_audit.json
```

En la situación actual se esperan aproximadamente 30 filas: 11 `decidedBy`, 9 `sanctions`, 3 `appointsPerson`, 3 `appointsToOffice`, 2 `appealsAgainst` y 2 `beforeAuthority`.

## Casos de appointment

`appointsToOffice` merece especial cuidado. La tabla muestra las menciones de oficio inline con su `xml:id`. Aprobar una mención no significa convertir el texto del cargo en una nueva clase ontológica: el aplicador posterior deberá crear/reutilizar una instancia `leco:Office` y normalizarla al tipo amplio correspondiente (`MayorOfficeType`, `JudgeOfficeType`, etc.).
