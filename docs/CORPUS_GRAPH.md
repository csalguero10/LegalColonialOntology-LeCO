# LeCO — grafo de corpus (`build_corpus_graph.py`)

## Trabajo futuro: reconciliación de entidades entre documentos

`build_corpus_graph.py` reporta `Cross-document local subjects: 0`, es decir, ningún sujeto
local coincide por URI entre documentos. Esto confirma que la extracción por documento no
genera colisiones accidentales de identidad — comportamiento deseado durante la fase de
extracción.

Sin embargo, la misma entidad histórica puede aparecer bajo URIs distintas en cada documento
(p. ej. `cab-001-002/CabildoDeTunja`, `cab-001-003/CabildoDeTunja`, `cab-001-004/CabildoDeTunja`
referidos todos al mismo cabildo). Para preguntas transversales al corpus (CQs que cruzan
documentos) se necesitará una capa de reconciliación de entidades que aún no existe.

Propuesta para cuando se aborde esta fase:

- No fusionar identidades en los grafos por documento — rompería la trazabilidad hacia el
  folio/documento de origen.
- Añadir un grafo de autoridad separado (p. ej. `data/authority/institutions.ttl`) con URIs
  canónicas (`leco:inst/cabildo-tunja`).
- Vincular cada entidad documental a su canónica con `skos:exactMatch` / `skos:closeMatch`,
  no `owl:sameAs` — más seguro y reversible si una vinculación resulta errónea.
- Reutilizar el patrón ya existente de revisión humana (como en `PARTICIPANT.md`,
  `QUALITY.md`, `LEGAL_RELATION.md`): generar candidatos de reconciliación, revisarlos en un
  CSV, y aplicarlos con un script tipo `apply_entity_reconciliation.py` que emita los
  `skos:exactMatch` en el grafo de autoridad, sin tocar los grafos fuente.

Aún no implementado. Esta nota deja constancia de la decisión de diseño para cuando se
priorice la fase.
