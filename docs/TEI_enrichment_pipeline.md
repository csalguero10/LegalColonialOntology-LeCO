# TEI enrichment pipeline for LeCO

## Purpose

The source TEI files under `data/documents/<id>/tei.xml` are **never overwritten**.  They represent the first textual encoding of the pilot corpus.

`enrich_tei.py` combines four source artefacts:

- `tei.xml` — textual structure and explicit inline evidence;
- `metadata.json` — archival identity and verified catalogue context;
- `annotations.csv` — the first semantic annotation layer;
- `relations.csv` — provisional explicit/inferred relations from the pilot.

It generates a derived TEI file with a `standOff` layer:

```
data/documents/cab-001-002/tei.xml
        + metadata.json
        + annotations.csv
        + relations.csv
                    ↓
             enrich_tei.py
                    ↓
build/tei_enriched/cab-001-002.xml
```

## What is added

The enriched TEI may contain:

- `listPerson`, `listOrg`, `listPlace` for reusable historical entities;
- `listEvent/event` for LeCO jurisdictional acts;
- `interpGrp` for local normative rules, legal arguments, historical concepts and categories;
- `listRelation/relation` for participation, office holding, jurisdiction and object properties;
- `precision` for migrated inferences with a confidence level;
- inline `@ref`, `@ana` and `@corresp` pointers linking textual mentions to stand-off semantics.

## Conservative migration policy

The script does **not** treat every legacy relation as an ontological assertion.  Relations that cannot be mapped safely are emitted as warnings in `enrichment_report.json`.

Generated interpretive relations use `subtype="inferred"` or `subtype="humanInterpretation"` and retain `@source` pointers to documentary evidence.

## Commands

One document:

```bash
python scripts/enrich_tei.py data/documents/cab-001-002
```

Whole corpus:

```bash
python scripts/enrich_tei.py data/documents --all
```

Output is written to `build/tei_enriched/`.

## Next stage

The enriched file is the canonical input for the full mapping-profile mode of `tei_to_rdf.py`:

```bash
python scripts/tei_to_rdf.py build/tei_enriched/cab-001-002.xml --validate
```

The expected pipeline is:

`source TEI → enriched TEI → LeCO RDF → SHACL → reasoning → SPARQL`.
