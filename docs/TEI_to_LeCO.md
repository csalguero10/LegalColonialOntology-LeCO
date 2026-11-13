# TEI → LeCO/RDF — pipeline and mapping specification

> 🌐 **English** · [Español](#version-en-espanol) — the original Spanish version is kept below.

Consolidated document. These were previously four separate files (`TEI_enrichment_pipeline.md`,
`TEI_to_LeCO_converter.md`, `TEI_to_LeCO_mapping.md`, `Jurisdiction_inference_v0_1.md`); they
are grouped here in the order in which they operate on the corpus.

## Contents

1. [TEI enrichment](#1-tei-enrichment-enrich_teipy)
2. [TEI → RDF converter: usage](#2-tei--rdf-converter-usage-tei_to_rdfpy)
3. [Formal mapping specification](#3-formal-mapping-specification)
4. [Derived jurisdictional inference (D001–D005)](#4-derived-jurisdictional-inference-d001d005)

---

## 1. TEI enrichment (`enrich_tei.py`)

### Purpose

The source TEI files in `data/documents/<id>/tei.xml` are **never overwritten**. They
represent the first textual encoding of the pilot corpus.

`enrich_tei.py` combines four source artefacts:

- `tei.xml` — textual structure and explicit inline evidence;
- `metadata.json` — archival identity and verified catalogue context;
- `annotations.csv` — the first semantic annotation layer;
- `relations.csv` — provisional explicit/inferred relations from the pilot.

It generates a derived TEI with a `standOff` layer:

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

### What is added

The enriched TEI may contain:

- `listPerson`, `listOrg`, `listPlace` for reusable historical entities;
- `listEvent/event` for LeCO jurisdictional acts;
- `interpGrp` for local normative rules, legal arguments, concepts and historical categories;
- `listRelation/relation` for participation, office holding, jurisdiction and object properties;
- `precision` for migrated inferences with a confidence level;
- inline `@ref`, `@ana` and `@corresp` pointers linking textual mentions to the stand-off semantics.

### Conservative migration policy

The script does **not** treat every legacy relation as an ontological assertion. Relations
that cannot be mapped safely are emitted as warnings in `enrichment_report.json`.

Generated interpretive relations use `subtype="inferred"` or
`subtype="humanInterpretation"` and keep `@source` pointers to the documentary evidence.

### Running

One document:

```bash
python scripts/enrich_tei.py data/documents/cab-001-002
```

Full corpus:

```bash
python scripts/enrich_tei.py data/documents --all
```

Output in `build/tei_enriched/`.

### Next stage

The enriched TEI is the canonical input for the full mode (`mapping-profile`) of
`tei_to_rdf.py`:

```bash
python scripts/tei_to_rdf.py build/tei_enriched/cab-001-002.xml --validate
```

The expected pipeline is:

`source TEI → enriched TEI → LeCO RDF → SHACL → reasoning → SPARQL`.

---

## 2. TEI → RDF converter: usage (`tei_to_rdf.py`)

### Corpus layout

The converter assumes the existing layout and does **not** create a second TEI collection:

```text
data/
└── documents/
    └── cab-001-002/
        ├── metadata.json
        ├── annotations.csv
        ├── relations.csv
        └── tei.xml
```

Generated RDF is kept outside the source data:

```text
build/
├── rdf/
│   └── cab-001-002.ttl
└── shacl_reports/
    └── cab-001-002.ttl
```

### Usage

One document:

```bash
python scripts/tei_to_rdf.py data/documents/cab-001-002
```

One document + SHACL:

```bash
python scripts/tei_to_rdf.py data/documents/cab-001-002 --validate
```

Full corpus:

```bash
python scripts/tei_to_rdf.py data/documents --all
```

Full corpus + SHACL:

```bash
python scripts/tei_to_rdf.py data/documents --all --validate
```

A machine-readable summary is written to `build/rdf/conversion_report.json`.

### Two input modes

**`mapping-profile`** — the TEI contains `standOff` entities/events/relations following
`mapping/tei_to_leco.yaml`. This is the canonical mode and produces SHACL-ready LeCO data.

**`legacy-inline`** — older pilot TEI with inline `persName`, `orgName`, `term`, `rs`, etc.
but no `standOff`. The converter safely creates the documentary structure, inline
entities/concepts and identifiable acts, but **does not invent complex procedural or
jurisdictional relations from prose**. These files normally need to be migrated to the
mapping profile to fully conform to LeCO SHACL.

`metadata.json` is used as the authoritative fallback for archival identifiers/title/date.
`annotations.csv` and `relations.csv` remain audit/migration sidecars; the converter does not
silently turn their old provisional labels into canonical LeCO assertions.

### URI policy

```text
https://w3id.org/leco/data/{reference_code}/record
https://w3id.org/leco/data/{reference_code}/{xml_id}
```

RDF identity therefore depends on the archival reference code and a stable `xml:id`, never on
mutable labels.

### Important derived rules

The converter only performs structural derivations defined by the mapping profile, for example:

- an act `decidedBy` / `beforeAuthority` an authority inherits that authority's declared jurisdiction;
- an ordered act may inherit the jurisdiction of the order when no other jurisdiction is encoded;
- `decidedBy`, `beforeAuthority`, `sanctions`, `investigates`, etc. may provide the broad event participation required by the application profile;
- a historical concept used in an `ActaCabildoDocumentType` may inherit the single declared Cabildo jurisdiction when the TEI gives no more specific conceptual-use jurisdiction.

These are mapping derivations from already-encoded semantics, not NLP guesses about the prose. The full detail of these rules (D001–D005) is in [section 4](#4-derived-jurisdictional-inference-d001d005).

---

## 3. Formal mapping specification

**Mapping profile:** LeCO-TEI 0.1.0 (implementation in `mapping/tei_to_leco.yaml`, current version 0.2.3)
**LeCO namespace:** `https://w3id.org/leco/ontology#`
**TEI namespace:** `http://www.tei-c.org/ns/1.0`

### 3.1 Purpose

This specification defines how a colonial legal text encoded in TEI is transformed into RDF
conforming to **LegalColonialOntology (LeCO)**, reusing RiC-O, CIDOC CRM, FOAF, SKOS, PROV-O
and OWL-Time.

The mapping is intentionally **two-layered**:

1. **Inline TEI markup** identifies textual fragments and explicit evidence.
2. **`standOff`** annotations declare reusable entities, events and legal relations that must
   not be confused with the surface text.

This follows the TEI model in which `standOff` is a container for linked data, contextual
information and stand-off annotation. TEI also provides `listEvent`/`event` for identifiable
events and `listRelation`/`relation` for explicit relations.

### 3.2 Scope of the mapping

The mapping does **not** treat TEI as an ontology. TEI represents the textual/documentary
layer; LeCO/RDF represents the semantic-relational layer. Therefore:

- `<persName>` is not in itself a `foaf:Person`.
- `<orgName>` is not in itself a `rico:CorporateBody`.
- `<term>` is not in itself a historical concept.
- `<event>` is a TEI declaration from which an RDF event individual is created.
- a textual occurrence and the entity/concept it denotes remain distinct.

### 3.3 URI policy

All local RDF resources are minted from the archival reference code and the TEI `xml:id`:

```text
https://w3id.org/leco/data/{reference_code}/{xml_id}
```

Example:

```text
TEI reference code: co-ahrb-cab-001-d002
xml:id: p_pineda

RDF URI:
https://w3id.org/leco/data/co-ahrb-cab-001-d002/p_pineda
```

The URI **must not be generated from a person's name, label, spelling or interpretation**,
because those values may change during normalisation.

The record URI is:

```text
https://w3id.org/leco/data/{reference_code}/record
```

An absolute URI in `@ref` or `@ana` is kept as is. A local pointer such as `#p_pineda` resolves to the local URI above.

### 3.4 Structural mapping

| TEI source | RDF target | Relation |
|---|---|---|
| `<TEI>` | `leco:LegalDocument`, `rico:Record` | root record |
| `<div xml:id>` | `leco:LegalDocumentPart`, `rico:RecordPart` | `rico:hasDirectConstituent` |
| `<seg xml:id>` | `leco:LegalDocumentPart`, `rico:RecordPart` | `rico:hasDirectConstituent` |
| `<div ana="…DocumentType">` | existing DocumentType concept | `leco:hasDocumentType` |

RiC-O `RecordPart` is used for documentary components, and
`rico:hasDirectConstituent`/`rico:isDirectConstituentOf` represent the direct part-whole
documentary structure.

### 3.5 Inline evidence mapping

Every semantically annotated inline element must carry an `xml:id` and normally a `@ref` to a
declared entity/concept.

Person mention:

```xml
<persName xml:id="m_pineda" ref="#p_pineda">Juan de Pineda</persName>
```

creates a `leco:SemanticAnnotation` whose:

- `leco:annotationBody` = person resource `p_pineda`;
- `leco:attestedIn` = nearest `seg`/`div` ancestor with an `xml:id`;
- `leco:evidenceText` = `Juan de Pineda`;
- `leco:annotationBasis` = `leco:ExplicitTextualEvidence`.

The **person resource itself** is created from the `standOff/listPerson` declaration.

The same pattern is used for `<orgName>`, `<placeName>`, `<term>` and `<rs>`.

### 3.6 Authoritative entity declarations in `standOff`

**Persons:**

```xml
<listPerson>
  <person xml:id="p_pineda">
    <persName>Juan de Pineda</persName>
  </person>
</listPerson>
```

maps to:

```turtle
:p_pineda a rico:Person, crm:E21_Person, foaf:Person ;
    rdfs:label "Juan de Pineda"@es .
```

**Institutions:**

```xml
<listOrg>
  <org xml:id="org_cabildo"
       ana="https://w3id.org/leco/ontology#CabildoType">
    <orgName>Cabildo de Tunja</orgName>
  </org>
</listOrg>
```

maps to an individual of `rico:CorporateBody` and `crm:E74_Group`, linked to the SKOS
institutional type via `leco:hasInstitutionType`.

**Places:** `<place>` declarations map to `rico:Place` and `crm:E53_Place` individuals.

### 3.7 Legal events and acts

TEI `<event>` declarations in `<listEvent>` become historical act/event individuals.

```xml
<event xml:id="ev_appeal"
       ana="https://w3id.org/leco/ontology#Appeal"
       when="1547-09-02"
       corresp="#s4">
  <desc>Apelación de Juan de Pineda.</desc>
</event>
```

maps to:

```turtle
:ev_appeal a leco:Appeal .
:s4 leco:documentsAct :ev_appeal .
```

`@corresp` connects the event to the textual segment that documents it.

### 3.8 N-ary legal relations

Some legal relations cannot be adequately represented as a single binary triple. For these,
the TEI `<relation>` becomes a LeCO/RiC-O relation resource.

**Participation:**

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

This is essential because **Juan de Pineda is not permanently an appellant**: he plays that
procedural role in this particular appeal.

**Office holding:**

```xml
<relation xml:id="rel_office_pineda"
          type="officeHolding"
          active="#p_pineda"
          passive="#org_cabildo"
          ana="https://w3id.org/leco/ontology#OrdinaryMayorOfficeType"
          when="1547"
          source="#s2"/>
```

The converter generates:

1. a `leco:Office` / `rico:Position` individual;
2. a `rico:PositionHoldingRelation`;
3. `rico:relationHasSource` → person;
4. `rico:relationHasTarget` → office;
5. `rico:relationHasDate` → temporal resource;
6. `leco:officeExistsIn` → institution;
7. `leco:hasOfficeType` → `OrdinaryMayorOfficeType`.

This reuses RiC-O instead of introducing a duplicate LeCO office-holding pattern.

**Territorial jurisdiction:**

```xml
<relation xml:id="jur_cabildo"
          type="territorialJurisdiction"
          active="#org_cabildo"
          passive="#pl_tunja"
          ana="https://w3id.org/leco/ontology#TerritorialJurisdiction"/>
```

creates a `leco:TerritorialJurisdiction` individual, links the authority via
`leco:exercisesJurisdiction`, and the jurisdiction to its place via `leco:territorialScope`.

This preserves the distinction: Tunja (Place) ≠ jurisdiction exercised over Tunja (Jurisdiction).

### 3.9 Binary legal relations

A controlled `<relation type="objectProperty">` maps to an RDF object property.

```xml
<relation xml:id="rel_appeals"
          type="objectProperty"
          name="appealsAgainst"
          active="#ev_appeal"
          passive="#ev_sanction"
          source="#s4"/>
```

maps to:

```turtle
:ev_appeal leco:appealsAgainst :ev_sanction .
```

The allowed `@name` values are those in `controlled_types.relation.direct_properties` in
`mapping/tei_to_leco.yaml` (an allowlist enforced at runtime by the converter).

Every binary relation is additionally reified as an `rdf:Statement` for provenance, and its
TEI `<relation>` produces a `leco:SemanticAnnotation` linked to documentary evidence.

### 3.10 Normative rules and arguments

Rules and arguments that need a reusable RDF identity are declared in `standOff` with
`<interpGrp>`.

```xml
<interpGrp type="normativeRules">
  <interp xml:id="rule_duty"
          ana="https://w3id.org/leco/ontology#LegalDuty">
    deber de Alcalde Ordinario
  </interp>
</interpGrp>
```

maps to a `leco:NormativeRule`, additionally typed as `leco:LegalDuty` when specified.

Arguments use:

```xml
<interpGrp type="legalArguments">
  <interp xml:id="arg_breach">incumplimiento con el deber...</interp>
</interpGrp>
```

and can be linked with:

```xml
<relation type="objectProperty"
          name="argumentInvokesRule"
          active="#arg_breach"
          passive="#rule_duty"/>
```

### 3.11 Historical concepts

Known LeCO vocabulary concepts should be referenced directly:

```xml
<term xml:id="m_real_service"
      ref="https://w3id.org/leco/ontology#RealServiceConcept">
  Real Servicio
</term>
```

The textual occurrence generates both an explicit semantic annotation and a
`leco:HistoricalConceptUse` contextualised by documentary evidence.

New corpus-specific concepts can be declared under
`<interpGrp type="localHistoricalConcepts">` and become
`leco:HistoricalLegalConcept` + `skos:Concept` individuals.

### 3.12 Historical socio-legal categories

Categories such as *indios*, *naturales*, *vecinos*, *judíos*, etc. remain SKOS concepts
belonging to LeCO's historical category subclasses.

A lexical occurrence does **not** automatically classify an actor. Classification requires
an explicit stand-off relation:

```xml
<relation type="historicalCategoryAssignment"
          active="#person_or_group"
          passive="https://w3id.org/leco/ontology#Indios"
          source="#segment"/>
```

which creates a `leco:HistoricalCategoryAssignment`.

### 3.13 Explicit evidence vs. inference

The relation's `@subtype` controls the annotation basis:

| TEI `@subtype` | LeCO |
|---|---|
| `explicit` | `leco:ExplicitTextualEvidence` |
| `inferred` | `leco:InferredFromText` |
| `catalog` | `leco:CatalogMetadataBasis` |
| `humanInterpretation` | `leco:HumanInterpretationBasis` |

Every inferred relation must include an `@source` pointing to one or more documentary segments.

Numeric confidence, when available, is represented with TEI `<precision>`:

```xml
<precision target="#rel_part_appeal" confidence="0.90"/>
```

and becomes:

```turtle
:rel_part_appeal-annotation leco:confidenceScore 0.90 .
```

Monetary amounts (fines, mercedes, encomiendas, tributes...) follow the same standalone
element pattern, using TEI's own `<measure>` element instead of inventing a LeCO-specific one:

```xml
<measure target="#ev_sanction_1547" quantity="200" unit="pesos"/>
```

and becomes:

```turtle
:ev_sanction_1547 leco:monetaryAmount 200.0 ;
    leco:hasCurrencyUnit leco:PesoUnit .
```

`@unit` must be one of the controlled labels in `controlled_types.measure.unit`
(`mapping/tei_to_leco.yaml`), currently `peso`, `tomín` and `ducado` — the three units
attested in the pilot corpus. An unrecognised `@unit` still produces `leco:monetaryAmount`
(the number is a textual fact) but not `leco:hasCurrencyUnit`, and the converter emits a
warning instead of guessing a currency.

### 3.14 Dual-nature terms

The mapping formally preserves the dual or triple nature of historically ambiguous terms:

| Term | Event/relation dimension | Documentary/conceptual dimension |
|---|---|---|
| Auto | `leco:AutoDecision` | `leco:AutoDocumentType` |
| Procurador | `leco:ProcuradorOfficeType` | `leco:ProcuradorProceduralRole` when the context requires it |
| Justicia y Regimiento | concrete organisation | `leco:JusticeAndRegimentType` |
| Repartimiento | `leco:RepartimientoAct` | `leco:RepartimientoRegime` |
| Merced | `leco:MercedGrant` | `leco:MercedBenefit` / right |
| Poder | `leco:GrantOfPower` | `leco:RepresentationRelation` + `leco:PowerDocumentType` |
| Encomienda | `leco:EncomiendaGrant` | `leco:EncomiendaRegime` |

No automatic lexical rule may collapse these dimensions.

### 3.15 Validation pipeline

```text
TEI/XML
   ↓
TEI profile validation
   ↓
TEI → LeCO/RDF mapping
   ↓
RDF syntax validation
   ↓
LeCO SHACL
   ↓
OWL-RL reasoning
   ↓
Competency Question SPARQL tests
```

A transformed document is accepted into the pilot knowledge graph only if:

1. all local TEI pointers resolve;
2. the produced RDF parses correctly;
3. SHACL reports `Conforms: True`;
4. the applicable competency-question tests return the expected structures.

### 3.16 Machine-readable specification

The normative mapping rules for the converter are maintained in `mapping/tei_to_leco.yaml`.
That YAML is the implementation-oriented source of truth; this section is the human-readable
specification.

---

## 4. Derived jurisdictional inference (D001–D005)

A reproducible RDF inference layer added to the TEI → LeCO converter. It does not modify any
TEI or fill relations directly in the source files; it operates only on the already-generated
RDF graph, inside `scripts/tei_to_rdf.py` (`_derived_rules`, lines 782–850).

### Rule D001 — authority → jurisdiction

If an act is `leco:decidedBy` or `leco:beforeAuthority` an authority, and that authority
`leco:exercisesJurisdiction` a jurisdiction, the following is derived:

```text
act → leco:withinJurisdiction → jurisdiction
```

### Rule D005 — single participating authority

If an act still has no jurisdiction and has exactly one participating authority — via
`leco:hasParticipant` or `leco:hasParticipation`/`leco:participationActor` — and that
authority exercises exactly one jurisdiction, `leco:withinJurisdiction` is derived.

If there are several possible authorities or jurisdictions, the rule does not fire. The
warning remains for human review (see `QUALITY.md` for the current status of those warnings
on `tei_legal_curated`).

### Provenance

Each derived assertion is kept as an `rdf:Statement` and a `leco:SemanticAnnotation` with:

- `leco:annotationBasis leco:ContextualInferenceBasis`;
- `leco:hasValidationStatus leco:ProposedAnnotation`;
- `leco:attestedIn` pointing to the documentary segments recovered from the premises;
- `leco:confidenceScore` computed conservatively from the premises and never higher than
  `0.95`;
- `prov:wasGeneratedBy` a specific activity (`D001`, `D002`, `D003`, `D004` or `D005`);
- `leco:validationNote` with the rule used.

A derived inference is not marked as explicit textual evidence nor as individually validated
by a person.

### `ContextualInferenceBasis`

LeCO 0.3.2 added the controlled concept:

```turtle
leco:ContextualInferenceBasis a leco:AnnotationBasis ;
    skos:inScheme leco:AnnotationBasisScheme .
```

This distinguishes a structural/contextual derivation from `leco:InferredFromText`.

### Validation

CORE and STRICT require `confidenceScore` and `attestedIn` for `ContextualInferenceBasis` as well.

### Test result on the local curated layer

The local reproduction of the 19 documents showed 107 acts without `withinJurisdiction`
before D005 and 97 after: 10 additional jurisdictions could be derived because there was a
single participating authority with a single jurisdiction. On `build/tei_legal_curated` (final
stage, with participant and legal relation curation already applied) 92 cases remain
unresolved — see the full breakdown in `QUALITY.md`.

---

<a id="version-en-espanol"></a>

> 🌐 [English](#) · **Español** — versión original en español.

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
