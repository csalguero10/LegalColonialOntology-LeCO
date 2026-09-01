# LeCO — SHACL: perfiles, normalización de oficios y diagnóstico

Documento consolidado. Antes eran dos archivos separados
(`SHACL_profiles_and_office_normalization_v0_2.md`, `SHACL_corpus_diagnostics.md`).

## Índice

1. [Perfiles SHACL y normalización de oficios](#1-perfiles-shacl-y-normalización-de-oficios)
2. [Diagnóstico SHACL del corpus (`analyze_shacl_reports.py`)](#2-diagnóstico-shacl-del-corpus-analyze_shacl_reportspy)

---

## 1. Perfiles SHACL y normalización de oficios

### 1.1 Principio de validación

LeCO distingue tres perfiles SHACL:

- `shapes/LeCO_shapes.ttl` — **CORE**: integridad estructural. La ausencia de contexto
  histórico deseable no invalida por sí sola el grafo.
- `shapes/LeCO_quality_shapes.ttl` — **QUALITY**: completitud histórica expresada como
  `sh:Warning`.
- `shapes/LeCO_shapes_strict.ttl` — **STRICT**: perfil exigente para gold standards y
  fixtures curados.

Las ausencias detectadas masivamente en el corpus (`withinJurisdiction`, participante,
`decidedBy`, `sanctions`, `appointsPerson`, etc.) se controlan como advertencias de calidad
en vez de errores CORE, salvo cuando una relación presente está mal formada. El estado actual
de esas advertencias sobre la capa final vigente está en `QUALITY.md` §3.

### 1.2 Normalización de oficios

El vocabulario de oficios debe ser analíticamente estable, no reproducir como un concepto
distinto cada fórmula histórica.

Regla general:

> La forma histórica exacta se conserva en TEI/evidencia; el RDF puede apuntar a un tipo de
> oficio más amplio y estable.

Ejemplos adoptados:

| Forma en la fuente/anotación | Tipo LeCO normalizado |
|---|---|
| Alcalde, Alcalde Ordinario, Alcaldes Ordinarios | `leco:MayorOfficeType` |
| Juez, Juez de Comisión | `leco:JudgeOfficeType` |
| Alguacil, Alguacil Mayor, Alquacil | `leco:BailiffOfficeType` |
| Procurador, Procurador General | `leco:ProcuradorOfficeType` cuando funciona como oficio |
| Escribano, Escribano Público | `leco:NotaryOfficeType` |
| Regidor / Regidores | `leco:RegidorOfficeType` |
| Diputado / diputados | `leco:DeputyOfficeType` |
| Capitán / Cap | `leco:CaptainOfficeType` |
| Cardenal | `leco:CardinalOfficeType` |
| Contador | `leco:AccountantOfficeType` |

`Procurador` conserva su doble naturaleza: si el contexto es procesal se usa
`leco:ProcuradorProceduralRole`; si designa cargo/oficio se usa `leco:ProcuradorOfficeType`.

El detalle completo de variantes/inflexiones vive en `mapping/office_normalization.yaml`.

#### Compatibilidad

Los conceptos finos ya existentes —por ejemplo `OrdinaryMayorOfficeType`,
`CommissionJudgeOfficeType`, `ChiefBailiffOfficeType`, `ProcuradorGeneralOfficeType` y
`PublicNotaryOfficeType`— no se eliminan de golpe. Se conservan como `owl:deprecated true`
para no romper RDF o consultas anteriores, pero el nuevo pipeline no debe generarlos.

### 1.3 Correcciones de mapping

`appointsPerson` y `appointsToOffice` están autorizadas en `mapping/tei_to_leco.yaml`.
También se preservan las relaciones de doble naturaleza como `createsRepresentation` y
`resultsInLegalArrangement`.

### 1.4 Ejecución recomendada

Validación CORE del corpus:

```bash
python scripts/tei_to_rdf.py build/tei_enriched --all --validate --shacl-profile core
```

Diagnóstico QUALITY:

```bash
python scripts/tei_to_rdf.py build/tei_enriched --all --validate --shacl-profile quality
```

Gold standard / validación estricta:

```bash
python scripts/tei_to_rdf.py build/tei_enriched/cab-001-002.xml --validate --shacl-profile strict
```

Los reportes se separan por perfil para evitar sobrescrituras.

---

## 2. Diagnóstico SHACL del corpus (`analyze_shacl_reports.py`)

### 2.1 Objetivo

`analyze_shacl_reports.py` analiza los reportes Turtle generados por pySHACL para todos los
documentos. No modifica TEI, RDF, ontología ni shapes.

La finalidad es separar empíricamente:

1. errores de integridad que deben seguir siendo `sh:Violation`;
2. ausencia de información histórica que puede ser más adecuada como `sh:Warning`;
3. problemas de mapping o vocabulario controlado;
4. patrones excepcionales que requieren revisión documental.

### 2.2 Entrada

Por defecto:

```text
build/shacl_reports/*.ttl
```

### 2.3 Ejecución

Desde la raíz del repositorio:

```bash
python scripts/analyze_shacl_reports.py
```

### 2.4 Salidas

```text
build/shacl_analysis.csv
build/shacl_analysis_summary.csv
build/shacl_analysis.json
```

**`shacl_analysis.csv`** — una fila por `sh:ValidationResult`, con: `document`,
`report_file`, `conforms`, `severity`, `focus_node`, `source_shape`, `constraint`,
`result_path`, `value`, `message`.

**`shacl_analysis_summary.csv`** — agrupa problemas repetidos dentro de cada documento y
añade `count`.

**`shacl_analysis.json`** — incluye: número de reportes; documentos conformes/no conformes;
número total de resultados; recuento por severidad; estado de cada documento; patrones de
constraint/propiedad en todo el corpus; detalle completo de los resultados.

### 2.5 Interpretación metodológica

El script **no reclasifica** automáticamente una constraint de `Violation` a `Warning`. Esa
decisión se toma después de examinar el patrón en los 19 documentos y regresar a la evidencia
cuando sea necesario.

Un `MinCountConstraintComponent` frecuente sobre `leco:withinJurisdiction`, por ejemplo, no
demuestra por sí mismo que la shape sea demasiado estricta. Solo muestra que la propiedad
falta repetidamente. Habrá que determinar si la ausencia corresponde a:

- una relación que sí está sustentada pero no fue migrada;
- una inferencia estructural justificable;
- una carencia real de la fuente;
- o un requisito SHACL que debería ser de calidad/completitud y no de integridad.

### 2.6 Próximo paso

Después de ejecutar el análisis, revisar primero los patrones más frecuentes y los casos que
afectan a mayor número de documentos. Solo después se modifica `LeCO_shapes.ttl`, el mapping
o el enriquecedor.
