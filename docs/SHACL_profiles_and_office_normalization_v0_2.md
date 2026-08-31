# LeCO SHACL v0.2 — perfiles y normalización de oficios

## 1. Principio de validación

LeCO distingue tres perfiles SHACL:

- `shapes/LeCO_shapes.ttl` — **CORE**: integridad estructural. La ausencia de contexto histórico deseable no invalida por sí sola el grafo.
- `shapes/LeCO_quality_shapes.ttl` — **QUALITY**: completitud histórica expresada como `sh:Warning`.
- `shapes/LeCO_shapes_strict.ttl` — **STRICT**: perfil exigente para gold standards y fixtures curados.

Las ausencias detectadas masivamente en el corpus (`withinJurisdiction`, participante, `decidedBy`, `sanctions`, `appointsPerson`, etc.) se controlan como advertencias de calidad en vez de errores CORE, salvo cuando una relación presente está mal formada.

## 2. Normalización de oficios

El vocabulario de oficios debe ser analíticamente estable, no reproducir como un concepto distinto cada fórmula histórica.

Regla general:

> La forma histórica exacta se conserva en TEI/evidencia; el RDF puede apuntar a un tipo de oficio más amplio y estable.

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

`Procurador` conserva su doble naturaleza: si el contexto es procesal se usa `leco:ProcuradorProceduralRole`; si designa cargo/oficio se usa `leco:ProcuradorOfficeType`.

### Compatibilidad

Los conceptos finos ya existentes —por ejemplo `OrdinaryMayorOfficeType`, `CommissionJudgeOfficeType`, `ChiefBailiffOfficeType`, `ProcuradorGeneralOfficeType` y `PublicNotaryOfficeType`— no se eliminan de golpe. Se conservan como `owl:deprecated true` para no romper RDF o consultas anteriores, pero el nuevo pipeline no debe generarlos.

## 3. Correcciones de mapping

`appointsPerson` y `appointsToOffice` están autorizadas en `mapping/tei_to_leco.yaml`. También se preservan las relaciones de doble naturaleza como `createsRepresentation` y `resultsInLegalArrangement`.

## 4. Ejecución recomendada

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
