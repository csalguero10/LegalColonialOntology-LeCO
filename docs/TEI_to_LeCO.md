# TEI → LeCO/RDF — pipeline y especificación de mapeo

Documento consolidado. Antes eran cuatro archivos separados (`TEI_enrichment_pipeline.md`,
`TEI_to_LeCO_converter.md`, `TEI_to_LeCO_mapping.md`, `Jurisdiction_inference_v0_1.md`); se
agruparon aquí en el orden en que operan sobre el corpus.

## Índice

1. [Enriquecimiento TEI](#1-enriquecimiento-tei-enrich_teipy)
2. [Conversor TEI → RDF: uso](#2-conversor-tei--rdf-uso-tei_to_rdfpy)
3. [Especificación formal de mapeo](#3-especificación-formal-de-mapeo)
4. [Inferencia jurisdiccional derivada (D001–D005)](#4-inferencia-jurisdiccional-derivada-d001d005)

---

## 1. Enriquecimiento TEI (`enrich_tei.py`)

### Propósito

Los TEI fuente en `data/documents/<id>/tei.xml` **nunca se sobrescriben**. Representan la
primera codificación textual del corpus piloto.

`enrich_tei.py` combina cuatro artefactos fuente:

- `tei.xml` — estructura textual y evidencia inline explícita;
- `metadata.json` — identidad archivística y contexto catalográfico verificado;
- `annotations.csv` — la primera capa de anotación semántica;
- `relations.csv` — relaciones explícitas/inferidas provisionales del piloto.

Genera un TEI derivado con una capa `standOff`:

```text
data/documents/cab-001-002/tei.xml
        + metadata.json
        + annotations.csv
        + relations.csv
                    ↓
             enrich_tei.py
                    ↓
build/tei_enriched/cab-001-002.xml
```

### Qué se añade

El TEI enriquecido puede contener:

- `listPerson`, `listOrg`, `listPlace` para entidades históricas reutilizables;
- `listEvent/event` para actos jurisdiccionales LeCO;
- `interpGrp` para reglas normativas locales, argumentos jurídicos, conceptos y categorías históricas;
- `listRelation/relation` para participación, ocupación de oficio, jurisdicción y propiedades de objeto;
- `precision` para inferencias migradas con nivel de confianza;
- punteros inline `@ref`, `@ana` y `@corresp` que enlazan menciones textuales con la semántica stand-off.

### Política conservadora de migración

El script **no** trata cada relación legacy como una aserción ontológica. Las relaciones que
no se pueden mapear con seguridad se emiten como advertencias en `enrichment_report.json`.

Las relaciones interpretativas generadas usan `subtype="inferred"` o
`subtype="humanInterpretation"` y conservan punteros `@source` hacia la evidencia documental.

### Ejecución

Un documento:

```bash
python scripts/enrich_tei.py data/documents/cab-001-002
```

Corpus completo:

```bash
python scripts/enrich_tei.py data/documents --all
```

Salida en `build/tei_enriched/`.

### Siguiente etapa

El TEI enriquecido es la entrada canónica para el modo completo (`mapping-profile`) de
`tei_to_rdf.py`:

```bash
python scripts/tei_to_rdf.py build/tei_enriched/cab-001-002.xml --validate
```

El pipeline esperado es:

`TEI fuente → TEI enriquecido → RDF LeCO → SHACL → razonamiento → SPARQL`.

---

## 2. Conversor TEI → RDF: uso (`tei_to_rdf.py`)

### Layout del corpus

El conversor asume el layout existente y **no** crea una segunda colección TEI:

```text
data/
└── documents/
    └── cab-001-002/
        ├── metadata.json
        ├── annotations.csv
        ├── relations.csv
        └── tei.xml
```

El RDF generado se mantiene fuera de los datos fuente:

```text
build/
├── rdf/
│   └── cab-001-002.ttl
└── shacl_reports/
    └── cab-001-002.ttl
```

### Uso

Un documento:

```bash
python scripts/tei_to_rdf.py data/documents/cab-001-002
```

Un documento + SHACL:

```bash
python scripts/tei_to_rdf.py data/documents/cab-001-002 --validate
```

Corpus completo:

```bash
python scripts/tei_to_rdf.py data/documents --all
```

Corpus completo + SHACL:

```bash
python scripts/tei_to_rdf.py data/documents --all --validate
```

Se escribe un resumen legible por máquina en `build/rdf/conversion_report.json`.

### Dos modos de entrada

**`mapping-profile`** — el TEI contiene entidades/eventos/relaciones `standOff` siguiendo
`mapping/tei_to_leco.yaml`. Es el modo canónico y genera datos LeCO listos para SHACL.

**`legacy-inline`** — TEI piloto más antiguo con `persName`, `orgName`, `term`, `rs`, etc.
inline pero sin `standOff`. El conversor crea con seguridad la estructura documental, las
entidades/conceptos inline y los actos identificables, pero **no inventa relaciones
procesales o jurisdiccionales complejas a partir de la prosa**. Estos archivos normalmente
requieren migrarse al perfil de mapeo para conformar completamente con SHACL LeCO.

`metadata.json` se usa como respaldo autoritativo para identificadores/título/fecha
archivísticos. `annotations.csv` y `relations.csv` siguen siendo sidecars de
auditoría/migración; el conversor no convierte silenciosamente sus etiquetas provisionales
antiguas en aserciones LeCO canónicas.

### Política de URIs

```text
https://w3id.org/leco/data/{reference_code}/record
https://w3id.org/leco/data/{reference_code}/{xml_id}
```

La identidad RDF depende por tanto del código de referencia archivístico y de un `xml:id`
estable, nunca de etiquetas mutables.

### Reglas derivadas importantes

El conversor solo realiza derivaciones estructurales definidas por el perfil de mapeo, por ejemplo:

- un acto `decidedBy` / `beforeAuthority` una autoridad hereda la jurisdicción declarada de esa autoridad;
- un acto ordenado puede heredar la jurisdicción de la orden cuando no hay otra jurisdicción codificada;
- `decidedBy`, `beforeAuthority`, `sanctions`, `investigates`, etc. pueden aportar participación amplia del evento requerida por el perfil de aplicación;
- un concepto histórico usado en un `ActaCabildoDocumentType` puede heredar la única jurisdicción de Cabildo declarada cuando el TEI no da una jurisdicción de uso conceptual más específica.

Son derivaciones de mapeo a partir de semántica ya codificada, no conjeturas de PLN sobre la prosa. El detalle completo de estas reglas (D001–D005) está en la [sección 4](#4-inferencia-jurisdiccional-derivada-d001d005).

---

## 3. Especificación formal de mapeo

**Perfil de mapeo:** LeCO-TEI 0.1.0 (implementación en `mapping/tei_to_leco.yaml`, versión actual 0.2.3)
**Namespace LeCO:** `https://w3id.org/leco/ontology#`
**Namespace TEI:** `http://www.tei-c.org/ns/1.0`

### 3.1 Propósito

Esta especificación define cómo un texto jurídico colonial codificado en TEI se transforma
en RDF conforme a **LegalColonialOntology (LeCO)**, reutilizando RiC-O, CIDOC CRM, FOAF,
SKOS, PROV-O y OWL-Time.

El mapeo es intencionalmente de **dos capas**:

1. El **marcado TEI inline** identifica fragmentos textuales y evidencia explícita.
2. Las anotaciones **`standOff`** declaran entidades, eventos y relaciones jurídicas
   reutilizables que no deben confundirse con el texto superficial.

Esto sigue el modelo TEI en el que `standOff` es un contenedor para datos enlazados,
información contextual y anotación stand-off. TEI también provee `listEvent`/`event` para
eventos identificables y `listRelation`/`relation` para relaciones explícitas.

### 3.2 Límite del mapeo

El mapeo **no** trata TEI como una ontología. TEI representa la capa textual/documental;
LeCO/RDF representa la capa semántico-relacional. Por tanto:

- `<persName>` no es en sí misma `foaf:Person`.
- `<orgName>` no es en sí misma `rico:CorporateBody`.
- `<term>` no es en sí mismo un concepto histórico.
- `<event>` es una declaración TEI a partir de la cual se crea un individuo de evento RDF.
- una ocurrencia textual y la entidad/concepto que denota siguen siendo distintos.

### 3.3 Política de URIs

Todos los recursos RDF locales se acuñan a partir del código de referencia archivístico y el `xml:id` TEI:

```text
https://w3id.org/leco/data/{reference_code}/{xml_id}
```

Ejemplo:

```text
Código de referencia TEI: co-ahrb-cab-001-d002
xml:id: p_pineda

URI RDF:
https://w3id.org/leco/data/co-ahrb-cab-001-d002/p_pineda
```

La URI **no debe generarse a partir del nombre, etiqueta, ortografía o interpretación de una
persona**, porque esos valores pueden cambiar durante la normalización.

La URI del registro es:

```text
https://w3id.org/leco/data/{reference_code}/record
```

Una URI absoluta en `@ref` o `@ana` se conserva. Un puntero local como `#p_pineda` resuelve a la URI local anterior.

### 3.4 Mapeo estructural

| Fuente TEI | Objetivo RDF | Relación |
|---|---|---|
| `<TEI>` | `leco:LegalDocument`, `rico:Record` | registro raíz |
| `<div xml:id>` | `leco:LegalDocumentPart`, `rico:RecordPart` | `rico:hasDirectConstituent` |
| `<seg xml:id>` | `leco:LegalDocumentPart`, `rico:RecordPart` | `rico:hasDirectConstituent` |
| `<div ana="…DocumentType">` | concepto DocumentType existente | `leco:hasDocumentType` |

`RecordPart` de RiC-O se usa para componentes documentales y
`rico:hasDirectConstituent`/`rico:isDirectConstituentOf` representan la estructura
documental parte-todo directa.

### 3.5 Mapeo de evidencia inline

Todo elemento inline anotado semánticamente debe llevar `xml:id` y normalmente un `@ref` a
una entidad/concepto declarado.

Mención de persona:

```xml
<persName xml:id="m_pineda" ref="#p_pineda">Juan de Pineda</persName>
```

crea una `leco:SemanticAnnotation` cuyo:

- `leco:annotationBody` = recurso de persona `p_pineda`;
- `leco:attestedIn` = ancestro `seg`/`div` más cercano con `xml:id`;
- `leco:evidenceText` = `Juan de Pineda`;
- `leco:annotationBasis` = `leco:ExplicitTextualEvidence`.

El **recurso de persona en sí** se crea a partir de la declaración `standOff/listPerson`.

El mismo patrón se usa para `<orgName>`, `<placeName>`, `<term>` y `<rs>`.

### 3.6 Declaraciones de entidad autoritativas en `standOff`

**Personas:**

```xml
<listPerson>
  <person xml:id="p_pineda">
    <persName>Juan de Pineda</persName>
  </person>
</listPerson>
```

mapea a:

```turtle
:p_pineda a rico:Person, crm:E21_Person, foaf:Person ;
    rdfs:label "Juan de Pineda"@es .
```

**Instituciones:**

```xml
<listOrg>
  <org xml:id="org_cabildo"
       ana="https://w3id.org/leco/ontology#CabildoType">
    <orgName>Cabildo de Tunja</orgName>
  </org>
</listOrg>
```

mapea a un individuo de `rico:CorporateBody` y `crm:E74_Group`, enlazado al tipo
institucional SKOS mediante `leco:hasInstitutionType`.

**Lugares:** las declaraciones `<place>` mapean a individuos `rico:Place` y `crm:E53_Place`.

### 3.7 Eventos y actos jurídicos

Las declaraciones `<event>` de TEI en `<listEvent>` se convierten en individuos de acto/evento histórico.

```xml
<event xml:id="ev_appeal"
       ana="https://w3id.org/leco/ontology#Appeal"
       when="1547-09-02"
       corresp="#s4">
  <desc>Apelación de Juan de Pineda.</desc>
</event>
```

mapea a:

```turtle
:ev_appeal a leco:Appeal .
:s4 leco:documentsAct :ev_appeal .
```

`@corresp` conecta el evento con el segmento textual que lo documenta.

### 3.8 Relaciones jurídicas n-arias

Algunas relaciones jurídicas no pueden representarse adecuadamente como una sola tripla
binaria. Para estas, `<relation>` de TEI se convierte en un recurso de relación LeCO/RiC-O.

**Participación:**

```xml
<relation xml:id="rel_part_appeal"
          type="participation"
          active="#p_pineda"
          passive="#ev_appeal"
          ana="https://w3id.org/leco/ontology#AppellantRole"
          source="#s4"
          subtype="inferred"/>
```

```turtle
:rel_part_appeal a leco:Participation ;
    leco:participationActor :p_pineda ;
    leco:participationInAct :ev_appeal ;
    leco:participationRole leco:AppellantRole .
```

Esto es esencial porque **Juan de Pineda no es permanentemente apelante**: desempeña ese rol
procesal en esta apelación particular.

**Ocupación de oficio:**

```xml
<relation xml:id="rel_office_pineda"
          type="officeHolding"
          active="#p_pineda"
          passive="#org_cabildo"
          ana="https://w3id.org/leco/ontology#OrdinaryMayorOfficeType"
          when="1547"
          source="#s2"/>
```

El conversor genera:

1. un individuo `leco:Office` / `rico:Position`;
2. un `rico:PositionHoldingRelation`;
3. `rico:relationHasSource` → persona;
4. `rico:relationHasTarget` → oficio;
5. `rico:relationHasDate` → recurso temporal;
6. `leco:officeExistsIn` → institución;
7. `leco:hasOfficeType` → `OrdinaryMayorOfficeType`.

Esto reutiliza RiC-O en vez de introducir un patrón LeCO duplicado de ocupación de oficio.

**Jurisdicción territorial:**

```xml
<relation xml:id="jur_cabildo"
          type="territorialJurisdiction"
          active="#org_cabildo"
          passive="#pl_tunja"
          ana="https://w3id.org/leco/ontology#TerritorialJurisdiction"/>
```

crea un individuo `leco:TerritorialJurisdiction`, enlaza la autoridad con
`leco:exercisesJurisdiction`, y la jurisdicción con su lugar vía `leco:territorialScope`.

Esto preserva la distinción: Tunja (Lugar) ≠ jurisdicción ejercida sobre Tunja (Jurisdicción).

### 3.9 Relaciones jurídicas binarias

Una `<relation type="objectProperty">` controlada mapea a una propiedad de objeto RDF.

```xml
<relation xml:id="rel_appeals"
          type="objectProperty"
          name="appealsAgainst"
          active="#ev_appeal"
          passive="#ev_sanction"
          source="#s4"/>
```

mapea a:

```turtle
:ev_appeal leco:appealsAgainst :ev_sanction .
```

Los valores `@name` permitidos son los de `controlled_types.relation.direct_properties` en
`mapping/tei_to_leco.yaml` (allowlist aplicada en tiempo de ejecución por el conversor).

Toda relación binaria se reifica además como un `rdf:Statement` para procedencia, y su
`<relation>` TEI produce una `leco:SemanticAnnotation` enlazada a evidencia documental.

### 3.10 Reglas normativas y argumentos

Las reglas y argumentos que necesitan identidad RDF reutilizable se declaran en `standOff`
con `<interpGrp>`.

```xml
<interpGrp type="normativeRules">
  <interp xml:id="rule_duty"
          ana="https://w3id.org/leco/ontology#LegalDuty">
    deber de Alcalde Ordinario
  </interp>
</interpGrp>
```

mapea a un `leco:NormativeRule`, tipado adicionalmente como `leco:LegalDuty` cuando se
especifica.

Los argumentos usan:

```xml
<interpGrp type="legalArguments">
  <interp xml:id="arg_breach">incumplimiento con el deber...</interp>
</interpGrp>
```

y pueden enlazarse con:

```xml
<relation type="objectProperty"
          name="argumentInvokesRule"
          active="#arg_breach"
          passive="#rule_duty"/>
```

### 3.11 Conceptos históricos

Los conceptos de vocabulario LeCO conocidos deben referenciarse directamente:

```xml
<term xml:id="m_real_service"
      ref="https://w3id.org/leco/ontology#RealServiceConcept">
  Real Servicio
</term>
```

La ocurrencia textual genera tanto una anotación semántica explícita como un
`leco:HistoricalConceptUse` contextualizado por evidencia documental.

Nuevos conceptos específicos del corpus pueden declararse bajo
`<interpGrp type="localHistoricalConcepts">` y se convierten en individuos
`leco:HistoricalLegalConcept` + `skos:Concept`.

### 3.12 Categorías jurídico-sociales históricas

Categorías como *indios*, *naturales*, *vecinos*, *judíos*, etc. siguen siendo conceptos SKOS
pertenecientes a las subclases históricas de categoría de LeCO.

Una ocurrencia léxica **no** clasifica automáticamente a un actor. La clasificación requiere
una relación stand-off explícita:

```xml
<relation type="historicalCategoryAssignment"
          active="#person_or_group"
          passive="https://w3id.org/leco/ontology#Indios"
          source="#segment"/>
```

que crea una `leco:HistoricalCategoryAssignment`.

### 3.13 Evidencia explícita vs. inferencia

El `@subtype` de la relación controla la base de anotación:

| TEI `@subtype` | LeCO |
|---|---|
| `explicit` | `leco:ExplicitTextualEvidence` |
| `inferred` | `leco:InferredFromText` |
| `catalog` | `leco:CatalogMetadataBasis` |
| `humanInterpretation` | `leco:HumanInterpretationBasis` |

Toda relación inferida debe incluir `@source` apuntando a uno o más segmentos documentales.

La confianza numérica, cuando está disponible, se representa con `<precision>` de TEI:

```xml
<precision target="#rel_part_appeal" confidence="0.90"/>
```

y se convierte en:

```turtle
:rel_part_appeal-annotation leco:confidenceScore 0.90 .
```

Los montos monetarios (multas, mercedes, encomiendas, tributos...) siguen el mismo patrón de
elemento independiente, usando el propio elemento `<measure>` de TEI en vez de inventar uno
específico de LeCO:

```xml
<measure target="#ev_sanction_1547" quantity="200" unit="pesos"/>
```

y se convierte en:

```turtle
:ev_sanction_1547 leco:monetaryAmount 200.0 ;
    leco:hasCurrencyUnit leco:PesoUnit .
```

`@unit` debe ser una de las etiquetas controladas en `controlled_types.measure.unit`
(`mapping/tei_to_leco.yaml`), actualmente `peso`, `tomín` y `ducado` — las tres unidades
atestiguadas en el corpus piloto. Un `@unit` no reconocido igual produce
`leco:monetaryAmount` (el número es un hecho textual) pero no `leco:hasCurrencyUnit`, y el
conversor emite una advertencia en vez de adivinar una moneda.

### 3.14 Términos de doble naturaleza

El mapeo preserva formalmente la doble o triple naturaleza de términos históricamente ambiguos:

| Término | Dimensión de evento/relación | Dimensión documental/conceptual |
|---|---|---|
| Auto | `leco:AutoDecision` | `leco:AutoDocumentType` |
| Procurador | `leco:ProcuradorOfficeType` | `leco:ProcuradorProceduralRole` cuando el contexto lo requiere |
| Justicia y Regimiento | organización concreta | `leco:JusticeAndRegimentType` |
| Repartimiento | `leco:RepartimientoAct` | `leco:RepartimientoRegime` |
| Merced | `leco:MercedGrant` | `leco:MercedBenefit` / derecho |
| Poder | `leco:GrantOfPower` | `leco:RepresentationRelation` + `leco:PowerDocumentType` |
| Encomienda | `leco:EncomiendaGrant` | `leco:EncomiendaRegime` |

Ninguna regla léxica automática puede colapsar estas dimensiones.

### 3.15 Pipeline de validación

```text
TEI/XML
   ↓
validación de perfil TEI
   ↓
mapeo TEI → LeCO/RDF
   ↓
validación de sintaxis RDF
   ↓
SHACL LeCO
   ↓
razonamiento OWL-RL
   ↓
tests SPARQL de Competency Questions
```

Un documento transformado se acepta en el grafo de conocimiento piloto solo si:

1. todos los punteros TEI locales resuelven;
2. el RDF producido parsea correctamente;
3. SHACL reporta `Conforms: True`;
4. los tests de competency-questions aplicables devuelven las estructuras esperadas.

### 3.16 Especificación legible por máquina

Las reglas de mapeo normativas para el conversor se mantienen en `mapping/tei_to_leco.yaml`.
Ese YAML es la fuente de verdad orientada a implementación; esta sección es la especificación
legible por humanos.

---

## 4. Inferencia jurisdiccional derivada (D001–D005)

Capa de inferencia RDF reproducible añadida al conversor TEI → LeCO. No modifica ningún TEI
ni rellena relaciones directamente en los archivos fuente; opera únicamente sobre el grafo
RDF ya generado, dentro de `scripts/tei_to_rdf.py` (`_derived_rules`, líneas 782–850).

### Regla D001 — autoridad → jurisdicción

Si un acto tiene `leco:decidedBy` o `leco:beforeAuthority` una autoridad, y esa autoridad
`leco:exercisesJurisdiction` una jurisdicción, se deriva:

```text
acto → leco:withinJurisdiction → jurisdicción
```

### Regla D005 — autoridad participante única

Si un acto todavía no tiene jurisdicción y posee exactamente una autoridad participante
—mediante `leco:hasParticipant` o `leco:hasParticipation`/`leco:participationActor`— y esa
autoridad ejerce exactamente una jurisdicción, se deriva `leco:withinJurisdiction`.

Si hay varias autoridades o varias jurisdicciones posibles, la regla no se ejecuta. El
warning permanece para revisión humana (ver `QUALITY.md` para el estado actual de esos
warnings sobre `tei_legal_curated`).

### Provenance

Cada afirmación derivada se conserva como un `rdf:Statement` y una `leco:SemanticAnnotation` con:

- `leco:annotationBasis leco:ContextualInferenceBasis`;
- `leco:hasValidationStatus leco:ProposedAnnotation`;
- `leco:attestedIn` hacia los segmentos documentales recuperados de las premisas;
- `leco:confidenceScore` calculado de forma conservadora a partir de las premisas y nunca
  superior a `0.95`;
- `prov:wasGeneratedBy` una actividad específica (`D001`, `D002`, `D003`, `D004` o `D005`);
- `leco:validationNote` con la regla utilizada.

Una inferencia derivada no se marca como evidencia textual explícita ni como validada
individualmente por una persona.

### `ContextualInferenceBasis`

LeCO 0.3.2 añadió el concepto controlado:

```turtle
leco:ContextualInferenceBasis a leco:AnnotationBasis ;
    skos:inScheme leco:AnnotationBasisScheme .
```

Esto diferencia una derivación estructural/contextual de `leco:InferredFromText`.

### Validación

CORE y STRICT exigen `confidenceScore` y `attestedIn` también para `ContextualInferenceBasis`.

### Resultado de prueba sobre la capa curada local

La reproducción local de los 19 documentos mostró 107 actos sin `withinJurisdiction` antes de
D005 y 97 después: 10 jurisdicciones adicionales pudieron derivarse porque había una única
autoridad participante con una única jurisdicción. Sobre `build/tei_legal_curated` (etapa
final, con curaduría de participantes y relaciones legales ya aplicada) quedan 92 casos sin
resolver — ver el desglose completo en `QUALITY.md`.
