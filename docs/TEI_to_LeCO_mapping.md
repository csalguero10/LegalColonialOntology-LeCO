# Formal TEI → LeCO/RDF Mapping Specification

**Project:** LegalColonialOntology-LeCO  
**Mapping profile:** LeCO-TEI 0.1.0  
**LeCO namespace:** `https://w3id.org/leco/ontology#`  
**TEI namespace:** `http://www.tei-c.org/ns/1.0`

## 1. Purpose

This specification defines how a TEI-encoded colonial legal text is transformed into RDF conforming to **LegalColonialOntology (LeCO)** while reusing RiC-O, CIDOC CRM, FOAF, SKOS, PROV-O, and OWL-Time.

The mapping is intentionally **two-layered**:

1. **Inline TEI markup** identifies textual spans and explicit evidence.
2. **`standOff` annotations** declare reusable entities, events, and legal relations that should not be confused with the surface text.

This follows the TEI model in which `standOff` is a container for linked data, contextual information, and stand-off annotation. TEI also provides `listEvent`/`event` for identifiable events and `listRelation`/`relation` for explicit relationships. The current TEI P5 Guidelines define these mechanisms directly. See the TEI Guidelines cited in the project documentation.

## 2. Mapping boundary

The mapping does **not** treat TEI as an ontology. TEI represents the textual/documentary layer; LeCO/RDF represents the semantic-relational layer.

Therefore:

- `<persName>` is not itself `foaf:Person`.
- `<orgName>` is not itself `rico:CorporateBody`.
- `<term>` is not itself a historical concept.
- `<event>` is a TEI declaration from which an RDF event individual is created.
- a textual occurrence and the entity/concept it denotes remain distinct.

## 3. URI policy

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

The URI **must not be generated from a person's name, label, spelling, or interpretation**, because those may change during normalization.

The record URI is:

```text
https://w3id.org/leco/data/{reference_code}/record
```

An absolute URI in `@ref` or `@ana` is preserved. A local pointer such as `#p_pineda` resolves to the local URI above.

## 4. Structural mapping

| TEI source | RDF target | Relation |
|---|---|---|
| `<TEI>` | `leco:LegalDocument`, `rico:Record` | root record |
| `<div xml:id>` | `leco:LegalDocumentPart`, `rico:RecordPart` | `rico:hasDirectConstituent` |
| `<seg xml:id>` | `leco:LegalDocumentPart`, `rico:RecordPart` | `rico:hasDirectConstituent` |
| `<div ana="…DocumentType">` | existing DocumentType concept | `leco:hasDocumentType` |

RiC-O's `RecordPart` is used for documentary components and `rico:hasDirectConstituent`/`rico:isDirectConstituentOf` represent direct documentary part-whole structure.

## 5. Inline evidence mapping

Every semantically annotated inline element should carry an `xml:id` and normally a `@ref` to a declared entity/concept.

### Person mention

```xml
<persName xml:id="m_pineda" ref="#p_pineda">Juan de Pineda</persName>
```

creates a `leco:SemanticAnnotation` whose:

- `leco:annotationBody` = person resource `p_pineda`;
- `leco:attestedIn` = nearest ancestor `seg`/`div` with `xml:id`;
- `leco:evidenceText` = `Juan de Pineda`;
- `leco:annotationBasis` = `leco:ExplicitTextualEvidence`.

The **person resource itself** is created from the `standOff/listPerson` declaration.

The same pattern is used for `<orgName>`, `<placeName>`, `<term>`, and `<rs>`.

## 6. Entity authority declarations in `standOff`

### Persons

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

### Institutions

```xml
<listOrg>
  <org xml:id="org_cabildo"
       ana="https://w3id.org/leco/ontology#CabildoType">
    <orgName>Cabildo de Tunja</orgName>
  </org>
</listOrg>
```

maps to an individual of `rico:CorporateBody` and `crm:E74_Group`, linked to the SKOS institutional type through `leco:hasInstitutionType`.

### Places

`<place>` declarations map to `rico:Place` and `crm:E53_Place` individuals.

## 7. Events and legal acts

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

## 8. N-ary legal relations

Some legal relations cannot be represented adequately as a single binary triple. For these, TEI `<relation>` is converted into a LeCO/RiC-O relation resource.

### 8.1 Participation

TEI:

```xml
<relation xml:id="rel_part_appeal"
          type="participation"
          active="#p_pineda"
          passive="#ev_appeal"
          ana="https://w3id.org/leco/ontology#AppellantRole"
          source="#s4"
          subtype="inferred"/>
```

RDF:

```turtle
:rel_part_appeal a leco:Participation ;
    leco:participationActor :p_pineda ;
    leco:participationInAct :ev_appeal ;
    leco:participationRole leco:AppellantRole .
```

This is essential because **Juan de Pineda is not permanently an appellant**; he plays that procedural role in this particular appeal.

### 8.2 Office holding

TEI:

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

This reuses RiC-O rather than introducing a duplicate LeCO office-holding pattern.

### 8.3 Territorial jurisdiction

```xml
<relation xml:id="jur_cabildo"
          type="territorialJurisdiction"
          active="#org_cabildo"
          passive="#pl_tunja"
          ana="https://w3id.org/leco/ontology#TerritorialJurisdiction"/>
```

creates a `leco:TerritorialJurisdiction` individual, links the authority with `leco:exercisesJurisdiction`, and the jurisdiction with its place via `leco:territorialScope`.

This preserves the distinction:

```text
Tunja (Place) ≠ jurisdiction exercised over Tunja (Jurisdiction)
```

## 9. Binary legal relations

A controlled `<relation type="objectProperty">` maps to an RDF object property.

Example:

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

The permitted `@name` values in version 0.1 are:

- `appealsAgainst`
- `beforeAuthority`
- `decidedBy`
- `ordersAct`
- `replacesPerson`
- `opposesParticipation`
- `invokesRule`
- `citesRule`
- `appliesRule`
- `interpretsRule`
- `argumentInvokesRule`
- `hasLegalArgument`
- `inProceeding`
- `hasProceduralAct`
- `directlyPrecedesInSequence` (mapped to RiC-O)

Every binary relation is additionally reified as an `rdf:Statement` for provenance, and its TEI `<relation>` produces a `leco:SemanticAnnotation` linked to documentary evidence.

## 10. Normative rules and arguments

Rules and arguments that need reusable RDF identity are declared in `standOff` with `<interpGrp>`.

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

## 11. Historical concepts

Known LeCO vocabulary concepts should be referenced directly:

```xml
<term xml:id="m_real_service"
      ref="https://w3id.org/leco/ontology#RealServiceConcept">
  Real Servicio
</term>
```

The textual occurrence generates both an explicit semantic annotation and a `leco:HistoricalConceptUse` contextualized by documentary evidence.

New corpus-specific concepts may be declared under:

```xml
<interpGrp type="localHistoricalConcepts">
```

and are converted to `leco:HistoricalLegalConcept` + `skos:Concept` individuals.

## 12. Historical legal/social categories

Categories such as *indios*, *naturales*, *vecinos*, *judíos*, etc. remain SKOS concepts belonging to LeCO historical-category subclasses.

A lexical occurrence does **not** automatically classify an actor.

Classification requires an explicit stand-off relation:

```xml
<relation type="historicalCategoryAssignment"
          active="#person_or_group"
          passive="https://w3id.org/leco/ontology#Indios"
          source="#segment"/>
```

which creates a `leco:HistoricalCategoryAssignment`.

## 13. Explicit evidence vs inference

The relation's `@subtype` controls the annotation basis:

| TEI `@subtype` | LeCO |
|---|---|
| `explicit` | `leco:ExplicitTextualEvidence` |
| `inferred` | `leco:InferredFromText` |
| `catalog` | `leco:CatalogMetadataBasis` |
| `humanInterpretation` | `leco:HumanInterpretationBasis` |

Every inferred relation must include `@source` pointing to one or more documentary segments.

Numerical confidence, when available, is represented with TEI `<precision>`:

```xml
<precision target="#rel_part_appeal" confidence="0.90"/>
```

and becomes:

```turtle
:rel_part_appeal-annotation leco:confidenceScore 0.90 .
```

## 14. Double-nature terms

The mapping formally preserves the double or triple nature of historically ambiguous terms:

| Term | Event/relation dimension | Documentary/conceptual dimension |
|---|---|---|
| Auto | `leco:AutoDecision` | `leco:AutoDocumentType` |
| Procurador | `leco:ProcuradorOfficeType` | `leco:ProcuradorProceduralRole` when context requires |
| Justicia y Regimiento | concrete organization | `leco:JusticeAndRegimentType` |
| Repartimiento | `leco:RepartimientoAct` | `leco:RepartimientoRegime` |
| Merced | `leco:MercedGrant` | `leco:MercedBenefit` / entitlement |
| Poder | `leco:GrantOfPower` | `leco:RepresentationRelation` + `leco:PowerDocumentType` |

No automatic lexical rule is allowed to collapse these dimensions.

## 15. Validation pipeline

The formal transformation pipeline is:

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
2. the produced RDF parses successfully;
3. SHACL reports `Conforms: True`;
4. applicable competency-question tests return the expected structures.

## 16. Machine-readable specification

The normative mapping rules for the converter are maintained in:

```text
mapping/tei_to_leco.yaml
```

The YAML file is the implementation-facing source of truth; this document is the human-readable specification.
