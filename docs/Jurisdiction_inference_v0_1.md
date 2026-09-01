# LeCO — inferencia jurisdiccional derivada v0.1

Esta actualización añade una capa de inferencia RDF reproducible al conversor TEI → LeCO. No modifica `build/tei_curated/` ni rellena relaciones directamente en los TEI.

## Regla D001 — autoridad → jurisdicción

Si un acto tiene `leco:decidedBy` o `leco:beforeAuthority` una autoridad, y esa autoridad `leco:exercisesJurisdiction` una jurisdicción, se deriva:

```text
acto → leco:withinJurisdiction → jurisdicción
```

## Regla D005 — autoridad participante única

Si un acto todavía no tiene jurisdicción y posee exactamente una autoridad participante —mediante `leco:hasParticipant` o `leco:hasParticipation`/`leco:participationActor`— y esa autoridad ejerce exactamente una jurisdicción, se deriva `leco:withinJurisdiction`.

Si hay varias autoridades o varias jurisdicciones posibles, la regla no se ejecuta. El warning permanece para revisión humana.

## Provenance

Cada afirmación derivada se conserva como un `rdf:Statement` y una `leco:SemanticAnnotation` con:

- `leco:annotationBasis leco:ContextualInferenceBasis`;
- `leco:hasValidationStatus leco:ProposedAnnotation`;
- `leco:attestedIn` hacia los segmentos documentales recuperados de las premisas;
- `leco:confidenceScore` calculado de forma conservadora a partir de las premisas y nunca superior a `0.95`;
- `prov:wasGeneratedBy` una actividad específica (`D001`, `D002`, `D003`, `D004` o `D005`);
- `leco:validationNote` con la regla utilizada.

Una inferencia derivada no se marca como evidencia textual explícita ni como validada individualmente por una persona.

## ContextualInferenceBasis

LeCO 0.3.2 añade el concepto controlado:

```turtle
leco:ContextualInferenceBasis a leco:AnnotationBasis ;
    skos:inScheme leco:AnnotationBasisScheme .
```

Esto diferencia una derivación estructural/contextual de `leco:InferredFromText`.

## Validación

CORE y STRICT ahora exigen `confidenceScore` y `attestedIn` también para `ContextualInferenceBasis`.

## Resultado de prueba sobre la capa curada local

La reproducción local de los 19 documentos mostró 107 actos sin `withinJurisdiction` antes de D005 y 97 después: 10 jurisdicciones adicionales pudieron derivarse porque había una única autoridad participante con una única jurisdicción. Este número debe verificarse de nuevo en el repositorio de investigación con QUALITY.
