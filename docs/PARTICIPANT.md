# LeCO — participant audit and review application

> 🌐 **English** · [Español](#version-en-espanol) — the original Spanish version is kept below.

Consolidated document. These were previously two separate files (`PARTICIPANT_audit.md`,
`PARTICIPANT_review_application.md`).

## Contents

1. [Participant audit v0.1 (`participant_audit.py`)](#1-participant-audit-v01-participant_auditpy)
2. [Participant review application v0.1 (`apply_participant_reviews.py`)](#2-participant-review-application-v01-apply_participant_reviewspy)

---

## 1. Participant audit v0.1 (`participant_audit.py`)

### Purpose

Audit every original participant SHACL QUALITY warning, including cases that the previous
curation pass appears to have resolved. This is necessary because free-text review notes are
not a safe, machine-readable source for target identity.

The audit is read-only. It never modifies TEI or RDF.

### Inputs

- `reviews/quality/quality_triage_reviewed.csv`
- `build/tei_curated/*.xml`
- `build/rdf_curated_inferred/*.ttl`

> Note (2026-09-01): the last two paths belonged to the intermediate `tei_curated` stage,
> since removed from `build/` because it was superseded by `build/tei_legal_curated`. The
> script is still valid; to re-run it, that stage must first be regenerated with
> `apply_quality_reviews.py` (see `QUALITY.md` §2).

### Outputs

- `build/participant_audit.csv`: all original participant warnings.
- `build/participant_audit_unresolved.csv`: current resolutions that are unresolved or suspect.
- `build/participant_audit.json`: counts per audit flag.

### Human review columns

Edit only these five columns:

- `approved_target_xml_id`: exact `xml:id` of the approved person or institution.
- `approved_basis`: `explicit`, `contextual`, or `unknown`.
- `approved_confidence`: decimal 0–1 for contextual inferences; empty for explicit evidence.
- `participant_review_status`: `approved`, `keep_warning`, or `needs_review`.
- `participant_reviewer_note`: historical/semantic justification.

Do not write just a name such as "Juan de Pineda" in `approved_target_xml_id`. Use the exact
identifier shown in the entity candidate columns, for example
`person_cab-001-002_cab-001-002_s004_a002`.

### Why exact IDs are required

A previous application pass tried to resolve targets from free-text notes and name aliases.
Historical spelling variation can make that unsafe. An approved exact `xml:id` makes the
human decision machine-actionable and reproducible without fuzzy matching.

---

## 2. Participant review application v0.1 (`apply_participant_reviews.py`)

### Principle

The script never resolves a participant from a name or free-text note. The only admissible
object for an approved assertion is the exact, human-reviewed `approved_target_xml_id`.

For each reviewed row it reconciles only the participant relations captured in the audit
snapshot:

- `approved`: removes the stale audited `hasParticipant` targets and writes exactly the
  approved target;
- `keep_warning`: removes any suspect audited target and intentionally leaves the act without
  a participant assertion;
- `needs_review`: same conservative behaviour; no new assertion is generated.

The input `build/tei_curated` is never overwritten. Output goes to
`build/tei_participant_curated`.

> Note (2026-09-01): both directories (`build/tei_curated` as input,
> `build/tei_participant_curated` as output) are no longer in `build/` — the output was
> superseded by `build/tei_legal_curated` and removed together with its intermediate input. See
> `QUALITY.md` §2 to regenerate `tei_curated` if this step needs to be repeated.

### Provenance

Approved relations are written as TEI `relation` nodes with:

- `name="hasParticipant"`;
- the exact `xml:id` of the `active` event;
- the exact `xml:id` of the reviewed `passive` person/organisation;
- `source` pointing to the evidence segment;
- `subtype="explicit"` or `subtype="contextual"`;
- a TEI `precision` containing the reviewed confidence.

The existing TEI→RDF converter maps those basis values to `ExplicitTextualEvidence` and
`ContextualInferenceBasis` and creates human-validated semantic annotations.

### Running

```bash
python scripts/apply_participant_reviews.py
```

Expected reviewed decisions in the current ledger: 35 approved, 22 keep-warning and 9
needs-review.

Then regenerate RDF from the new layer and validate CORE and QUALITY.

---

<a id="version-en-espanol"></a>

> 🌐 [English](#) · **Español** — versión original en español.

# LeCO — auditoría y aplicación de revisiones de participantes

Documento consolidado. Antes eran dos archivos separados (`PARTICIPANT_audit.md`,
`PARTICIPANT_review_application.md`).

## Índice

1. [Auditoría de participantes v0.1 (`participant_audit.py`)](#1-auditoría-de-participantes-v01-participant_auditpy)
2. [Aplicación de revisiones de participantes v0.1 (`apply_participant_reviews.py`)](#2-aplicación-de-revisiones-de-participantes-v01-apply_participant_reviewspy)

---

## 1. Auditoría de participantes v0.1 (`participant_audit.py`)

### Propósito

Auditar todos los warnings SHACL QUALITY de participantes originales, incluyendo casos que la
pasada de curaduría previa parece haber resuelto. Es necesario porque las notas de revisión en
texto libre no son una fuente segura y legible por máquina para la identidad del target.

La auditoría es de solo lectura. Nunca modifica TEI ni RDF.

### Entradas

- `reviews/quality/quality_triage_reviewed.csv`
- `build/tei_curated/*.xml`
- `build/rdf_curated_inferred/*.ttl`

> Nota (2026-09-01): estas dos últimas rutas correspondían a la etapa intermedia
> `tei_curated`, ya eliminada de `build/` por estar superada por `build/tei_legal_curated`. El
> script sigue siendo válido; para volver a ejecutarlo hay que regenerar primero esa etapa con
> `apply_quality_reviews.py` (ver `QUALITY.md` §2).

### Salidas

- `build/participant_audit.csv`: todos los warnings de participantes originales.
- `build/participant_audit_unresolved.csv`: resoluciones actuales no resueltas o sospechosas.
- `build/participant_audit.json`: conteos por bandera de auditoría.

### Columnas de revisión humana

Solo editar estas cinco columnas:

- `approved_target_xml_id`: `xml:id` exacto de la persona o institución aprobada.
- `approved_basis`: `explicit`, `contextual`, o `unknown`.
- `approved_confidence`: decimal 0–1 para inferencias contextuales; vacío para evidencia explícita.
- `participant_review_status`: `approved`, `keep_warning`, o `needs_review`.
- `participant_reviewer_note`: justificación histórica/semántica.

No escribir solo un nombre como "Juan de Pineda" en `approved_target_xml_id`. Usar el
identificador exacto mostrado en las columnas de candidatos de entidad, por ejemplo
`person_cab-001-002_cab-001-002_s004_a002`.

### Por qué se requieren IDs exactos

Una pasada de aplicación previa intentó resolver targets a partir de notas de texto libre y
alias de nombre. La variación ortográfica histórica puede hacer eso inseguro. Un `xml:id`
exacto aprobado hace que la decisión humana sea procesable por máquina y reproducible sin
coincidencia difusa.

---

## 2. Aplicación de revisiones de participantes v0.1 (`apply_participant_reviews.py`)

### Principio

El script nunca resuelve un participante a partir de un nombre o nota de texto libre. El
único objeto admisible para una aserción aprobada es el `approved_target_xml_id` exacto
revisado por un humano.

Para cada fila revisada reconcilia solo las relaciones de participante capturadas en el
snapshot de auditoría:

- `approved`: elimina los targets `hasParticipant` auditados obsoletos y escribe exactamente
  el target aprobado;
- `keep_warning`: elimina cualquier target sospechoso auditado y deja intencionalmente el
  acto sin aserción de participante;
- `needs_review`: mismo comportamiento conservador; no se genera ninguna aserción nueva.

La entrada `build/tei_curated` nunca se sobrescribe. La salida va a
`build/tei_participant_curated`.

> Nota (2026-09-01): ambos directorios (`build/tei_curated` de entrada,
> `build/tei_participant_curated` de salida) ya no están en `build/` — la salida quedó
> superada por `build/tei_legal_curated` y se eliminó junto con su entrada intermedia. Ver
> `QUALITY.md` §2 para regenerar `tei_curated` si hace falta repetir este paso.

### Procedencia

Las relaciones aprobadas se escriben como nodos TEI `relation` con:

- `name="hasParticipant"`;
- `xml:id` exacto del evento `active`;
- `xml:id` exacto de la persona/organización `passive` revisada;
- `source` apuntando al segmento de evidencia;
- `subtype="explicit"` o `subtype="contextual"`;
- `precision` TEI conteniendo la confianza revisada.

El conversor TEI→RDF existente mapea esos valores de base a `ExplicitTextualEvidence` y
`ContextualInferenceBasis` y crea anotaciones semánticas validadas por humano.

### Ejecución

```bash
python scripts/apply_participant_reviews.py
```

Decisiones revisadas esperadas en el ledger actual: 35 aprobadas, 22 keep-warning y 9
needs-review.

Luego regenerar RDF a partir de la nueva capa y validar CORE y QUALITY.
