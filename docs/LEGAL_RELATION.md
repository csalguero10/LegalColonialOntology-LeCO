# LeCO — legal relation audit and review application

> 🌐 **English** · [Español](#version-en-espanol) — the original Spanish version is kept below.

Consolidated document. These were previously two separate files (`LEGAL_RELATION_audit.md`,
`LEGAL_RELATION_review_application.md`).

## Contents

1. [Legal relation QUALITY audit v0.1 (`legal_relation_audit.py`)](#1-legal-relation-quality-audit-v01-legal_relation_auditpy)
2. [Legal relation review application v0.1 (`apply_legal_relation_reviews.py`)](#2-legal-relation-review-application-v01-apply_legal_relation_reviewspy)

---

## 1. Legal relation QUALITY audit v0.1 (`legal_relation_audit.py`)

This phase reviews only six high-value legal relations that still appear as `sh:Warning`
after participant curation:

- `leco:decidedBy`
- `leco:sanctions`
- `leco:appointsPerson`
- `leco:appointsToOffice`
- `leco:appealsAgainst`
- `leco:beforeAuthority`

### Principle

The script is **diagnostic only**. It does not add relations or modify TEI/RDF. Its purpose
is to put in front of the reviewer:

- the act that triggers the warning;
- its TEI segment and preceding/following context;
- candidate persons and institutions with their exact `xml:id`;
- neighbouring legal events with their exact `xml:id`;
- office mentions with their exact `xml:id`.

Human review is recorded exclusively in:

- `approved_target_xml_id`
- `approved_basis`: `explicit`, `contextual`, `unknown`
- `approved_confidence`: 0–1 if contextual
- `relation_review_status`: `approved`, `keep_warning`, `needs_review`
- `relation_reviewer_note`

Free-text names must not be written as targets. The applier only accepts approved `xml:id`s.

### Running

```bash
python scripts/legal_relation_audit.py
```

Default inputs:

```text
build/shacl_quality_participant_analysis.csv
build/tei_participant_curated/*.xml
build/rdf_participant_curated/*.ttl
```

> Note (2026-09-01): these three paths belonged to the intermediate
> `tei_participant_curated`/`rdf_participant_curated` stage, since removed from `build/` because
> it was superseded by `build/tei_legal_curated` (the audit has already been run and its results
> below remain valid). To re-run the script, that stage must first be regenerated
> (`PARTICIPANT.md` §2).

Outputs:

```text
build/legal_relation_audit.csv
build/legal_relation_audit_review_queue.csv
build/legal_relation_audit.json
```

In the current state roughly 30 rows are expected: 11 `decidedBy`, 9 `sanctions`, 3
`appointsPerson`, 3 `appointsToOffice`, 2 `appealsAgainst` and 2 `beforeAuthority`.

### Appointment cases

`appointsToOffice` deserves particular care. The table shows inline office mentions with
their `xml:id`. Approving a mention does not mean turning the office text into a new
ontological class: the subsequent applier must create/reuse a `leco:Office` instance and
normalise it to the corresponding broad type (`MayorOfficeType`, `JudgeOfficeType`, etc.).

---

## 2. Legal relation review application v0.1 (`apply_legal_relation_reviews.py`)

This stage applies only the human-approved legal relation reviews and creates a new derived
TEI layer.

### Safety rule

`approved_target_xml_id` is the only accepted target identifier. The script does **not**
resolve names, labels, spelling variants or nearest entities.

### Input and output

- Input TEI: `build/tei_participant_curated/*.xml`
- Reviewed decisions: `reviews/legal_relations/legal_relation_audit_review_queue_reviewed.csv`
- Output TEI: `build/tei_legal_curated/*.xml`

Earlier TEI layers are not overwritten.

> Note (2026-09-01): `build/tei_participant_curated` is no longer in `build/` (see above). The
> output, `build/tei_legal_curated`, is the current final TEI layer and is kept.

### Special handling of `appointsToOffice`

The approved target may be an inline mention of a historical office. Since
`leco:appointsToOffice` ranges over a concrete `leco:Office`, the script materialises a
stand-off office resource under `<interpGrp type="offices">`, preserves the lexical form via
`@corresp`, normalises only the office type, and points the appointment relation to that
concrete office resource.

Thus the source form `regidores` is preserved while the office is typed as
`leco:RegidorOfficeType`.

### Provenance

- `approved_basis=explicit` -> `subtype="explicit"`
- `approved_basis=contextual` -> `subtype="contextual"`
- `@source` keeps the event segment and, for contextual relations, the target's contextual
  segment when available.
- `<precision>` records the approved confidence.
- A TEI `<note type="legal-relation-review">` preserves the review justification.

### Modelling review queue

Rows marked `needs_review` are not applied. Run:

```bash
python scripts/build_event_typing_review_queue.py
```

This creates `build/event_typing_review_queue.csv`. These rows may reveal a modelling problem
rather than a missing target: an appointment in progress, a generic/authorised appeal, a
normative sanction, or an authority that cannot be recovered locally.

---

<a id="version-en-espanol"></a>

> 🌐 [English](#) · **Español** — versión original en español.

# LeCO — auditoría y aplicación de revisiones de relaciones jurídicas

Documento consolidado. Antes eran dos archivos separados (`LEGAL_RELATION_audit.md`,
`LEGAL_RELATION_review_application.md`).

## Índice

1. [Auditoría QUALITY de relaciones jurídicas v0.1 (`legal_relation_audit.py`)](#1-auditoría-quality-de-relaciones-jurídicas-v01-legal_relation_auditpy)
2. [Aplicación de revisiones de relaciones jurídicas v0.1 (`apply_legal_relation_reviews.py`)](#2-aplicación-de-revisiones-de-relaciones-jurídicas-v01-apply_legal_relation_reviewspy)

---

## 1. Auditoría QUALITY de relaciones jurídicas v0.1 (`legal_relation_audit.py`)

Esta fase revisa únicamente seis relaciones de alto valor jurídico que siguen apareciendo
como `sh:Warning` después de la curaduría de participantes:

- `leco:decidedBy`
- `leco:sanctions`
- `leco:appointsPerson`
- `leco:appointsToOffice`
- `leco:appealsAgainst`
- `leco:beforeAuthority`

### Principio

El script es **solo diagnóstico**. No añade relaciones ni modifica TEI/RDF. Su función es
poner delante del revisor:

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

No se deben escribir nombres libres como target. El aplicador solo acepta `xml:id` aprobados.

### Ejecución

```bash
python scripts/legal_relation_audit.py
```

Entradas por defecto:

```text
build/shacl_quality_participant_analysis.csv
build/tei_participant_curated/*.xml
build/rdf_participant_curated/*.ttl
```

> Nota (2026-09-01): estas tres rutas correspondían a la etapa intermedia
> `tei_participant_curated`/`rdf_participant_curated`, ya eliminadas de `build/` por estar
> superadas por `build/tei_legal_curated` (la auditoría ya se ejecutó y sus resultados abajo
> siguen vigentes). Para volver a ejecutar el script hay que regenerar primero esa etapa
> (`PARTICIPANT.md` §2).

Salidas:

```text
build/legal_relation_audit.csv
build/legal_relation_audit_review_queue.csv
build/legal_relation_audit.json
```

En la situación actual se esperan aproximadamente 30 filas: 11 `decidedBy`, 9 `sanctions`, 3
`appointsPerson`, 3 `appointsToOffice`, 2 `appealsAgainst` y 2 `beforeAuthority`.

### Casos de appointment

`appointsToOffice` merece especial cuidado. La tabla muestra las menciones de oficio inline
con su `xml:id`. Aprobar una mención no significa convertir el texto del cargo en una nueva
clase ontológica: el aplicador posterior deberá crear/reutilizar una instancia `leco:Office`
y normalizarla al tipo amplio correspondiente (`MayorOfficeType`, `JudgeOfficeType`, etc.).

---

## 2. Aplicación de revisiones de relaciones jurídicas v0.1 (`apply_legal_relation_reviews.py`)

Esta etapa aplica solo las revisiones de relaciones jurídicas aprobadas por humanos y crea una
nueva capa TEI derivada.

### Regla de seguridad

`approved_target_xml_id` es el único identificador de target aceptado. El script **no**
resuelve nombres, etiquetas, variantes ortográficas ni entidades más cercanas.

### Entrada y salida

- TEI de entrada: `build/tei_participant_curated/*.xml`
- Decisiones revisadas: `reviews/legal_relations/legal_relation_audit_review_queue_reviewed.csv`
- TEI de salida: `build/tei_legal_curated/*.xml`

Las capas TEI previas no se sobrescriben.

> Nota (2026-09-01): `build/tei_participant_curated` ya no está en `build/` (ver arriba). La
> salida, `build/tei_legal_curated`, es la capa TEI final vigente y sí se conserva.

### Manejo especial de `appointsToOffice`

El target aprobado puede ser una mención inline de un oficio histórico. Como
`leco:appointsToOffice` tiene rango sobre un `leco:Office` concreto, el script materializa un
recurso de oficio stand-off bajo `<interpGrp type="offices">`, preserva la forma léxica
mediante `@corresp`, normaliza solo el tipo de oficio, y apunta la relación de nombramiento a
ese recurso de oficio concreto.

Así, la forma fuente `regidores` se conserva mientras el oficio se tipa con
`leco:RegidorOfficeType`.

### Procedencia

- `approved_basis=explicit` -> `subtype="explicit"`
- `approved_basis=contextual` -> `subtype="contextual"`
- `@source` conserva el segmento del evento y, para relaciones contextuales, el segmento
  contextual del target cuando está disponible.
- `<precision>` registra la confianza aprobada.
- Una `<note type="legal-relation-review">` TEI preserva la justificación de la revisión.

### Cola de revisión de modelado

Las filas marcadas `needs_review` no se aplican. Ejecutar:

```bash
python scripts/build_event_typing_review_queue.py
```

Esto crea `build/event_typing_review_queue.csv`. Estas filas pueden revelar un problema de
modelado en vez de un target faltante: un nombramiento en curso, una apelación
genérica/autorizada, una sanción normativa, o una autoridad que no se puede recuperar
localmente.
