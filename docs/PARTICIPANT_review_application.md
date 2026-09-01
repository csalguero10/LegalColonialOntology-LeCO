# LeCO participant review application v0.1

`apply_participant_reviews.py` turns the approved participant audit into a reproducible TEI curation layer.

## Principle

The script never resolves a participant from a name or free-text note. The only admissible object for an approved assertion is the exact `approved_target_xml_id` reviewed by a human.

For every reviewed row it reconciles only the participant relations captured in the audit snapshot:

- `approved`: removes stale audited `hasParticipant` targets and writes exactly the approved target;
- `keep_warning`: removes any suspect audited target and intentionally leaves the act without a participant assertion;
- `needs_review`: same conservative behavior; no new assertion is generated.

The input `build/tei_curated` is never overwritten. Output goes to `build/tei_participant_curated`.

## Provenance

Approved relations are written as TEI `relation` nodes with:

- `name="hasParticipant"`;
- exact `active` event `xml:id`;
- exact reviewed `passive` person/org `xml:id`;
- `source` pointing to the evidence segment;
- `subtype="explicit"` or `subtype="contextual"`;
- TEI `precision` containing the reviewed confidence.

The existing TEI→RDF converter maps those basis values to `ExplicitTextualEvidence` and `ContextualInferenceBasis` and creates human-validated semantic annotations.

## Run

```bash
python scripts/apply_participant_reviews.py
```

Expected reviewed decisions in the current ledger: 35 approved, 22 keep-warning and 9 needs-review.

Then regenerate RDF from the new layer and validate CORE and QUALITY.
