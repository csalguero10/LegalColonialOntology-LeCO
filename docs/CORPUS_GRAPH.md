# LeCO — corpus graph (`build_corpus_graph.py`)

> 🌐 **English** · [Español](#version-en-espanol) — the original Spanish version is kept below.

## Future work: cross-document entity reconciliation

`build_corpus_graph.py` reports `Cross-document local subjects: 0`, meaning no local subject
matches by URI across documents. This confirms that per-document extraction does not
produce accidental identity collisions — the desired behaviour during the extraction phase.

However, the same historical entity may appear under different URIs in each document
(e.g. `cab-001-002/CabildoDeTunja`, `cab-001-003/CabildoDeTunja`, `cab-001-004/CabildoDeTunja`,
all referring to the same cabildo). Corpus-wide questions (CQs that span documents) will
require an entity reconciliation layer that does not exist yet.

Proposal for when this phase is tackled:

- Do not merge identities in the per-document graphs — doing so would break traceability back
  to the source folio/document.
- Add a separate authority graph (e.g. `data/authority/institutions.ttl`) with canonical URIs
  (`leco:inst/cabildo-tunja`).
- Link each documentary entity to its canonical counterpart with `skos:exactMatch` /
  `skos:closeMatch`, not `owl:sameAs` — safer and reversible if a link turns out to be wrong.
- Reuse the existing human-review pattern (as in `PARTICIPANT.md`, `QUALITY.md`,
  `LEGAL_RELATION.md`): generate reconciliation candidates, review them in a CSV, and apply
  them with a script such as `apply_entity_reconciliation.py` that emits the
  `skos:exactMatch` statements into the authority graph without touching the source graphs.

Not yet implemented. This note records the design decision for when the phase is
prioritised.

---

<a id="version-en-espanol"></a>

> 🌐 [English](#) · **Español** — versión original en español.

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
