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
