# TEI → LeCO/RDF converter

## Canonical corpus layout

The converter assumes the existing corpus layout and does **not** create a second TEI collection:

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

## Usage

One document:

```bash
python scripts/tei_to_rdf.py data/documents/cab-001-002
```

One document + SHACL:

```bash
python scripts/tei_to_rdf.py data/documents/cab-001-002 --validate
```

Whole corpus:

```bash
python scripts/tei_to_rdf.py data/documents --all
```

Whole corpus + SHACL:

```bash
python scripts/tei_to_rdf.py data/documents --all --validate
```

A machine-readable summary is written to `build/rdf/conversion_report.json`.

## Two input modes

### `mapping-profile`

The TEI contains `standOff` entities/events/relations following `mapping/tei_to_leco.yaml`. This is the canonical mode and is intended to generate SHACL-ready LeCO data.

### `legacy-inline`

Older pilot TEI files contain inline `persName`, `orgName`, `term`, `rs`, etc. but no `standOff`. The converter safely creates the document structure, inline entities/concepts and identifiable acts, but **does not invent complex procedural or jurisdictional relations from prose**. These files will usually require migration to the mapping profile before they can conform fully to LeCO SHACL.

`metadata.json` is used as an authoritative fallback for archival identifiers/title/date. `annotations.csv` and `relations.csv` remain audit/migration sidecars; the converter does not silently turn their older provisional labels into canonical LeCO assertions.

## URI policy

```text
https://w3id.org/leco/data/{reference_code}/record
https://w3id.org/leco/data/{reference_code}/{xml_id}
```

RDF identity therefore depends on the archival reference code and stable `xml:id`, never on mutable labels.

## Important derived rules

The converter performs only structural derivations defined by the mapping profile, for example:

- an act `decidedBy` / `beforeAuthority` an authority inherits the authority's declared jurisdiction;
- an ordered act may inherit the jurisdiction of the order when no jurisdiction is otherwise encoded;
- `decidedBy`, `beforeAuthority`, `sanctions`, `investigates`, etc. can contribute broad event participation required by the application profile;
- a historical concept used in an `ActaCabildoDocumentType` can inherit the unique declared Cabildo jurisdiction when the TEI does not give a more specific concept-use jurisdiction.

These are mapping derivations from already encoded semantics, not NLP guesses from prose.
