# LeCO participant audit v0.1

## Purpose

Audit all original SHACL QUALITY participant warnings, including cases that the
previous curation pass appears to have resolved. This is necessary because free-text
review notes are not a safe machine-readable source for target identity.

The audit is read-only. It never modifies TEI or RDF.

## Inputs

- `reviews/quality/quality_triage_reviewed.csv`
- `build/tei_curated/*.xml`
- `build/rdf_curated_inferred/*.ttl`

## Outputs

- `build/participant_audit.csv`: all original participant warnings.
- `build/participant_audit_unresolved.csv`: unresolved or suspicious current resolutions.
- `build/participant_audit.json`: counts by audit flag.

## Human review columns

Only edit these five columns:

- `approved_target_xml_id`: exact TEI `xml:id` of the approved person or institution.
- `approved_basis`: `explicit`, `contextual`, or `unknown`.
- `approved_confidence`: decimal 0–1 for contextual inferences; leave blank for explicit evidence.
- `participant_review_status`: `approved`, `keep_warning`, or `needs_review`.
- `participant_reviewer_note`: historical/semantic rationale.

Do **not** type only a name such as “Juan de Pineda” into `approved_target_xml_id`.
Use the exact identifier shown in the entity candidate columns, e.g.
`person_cab-001-002_cab-001-002_s004_a002`.

## Why exact IDs are required

A previous application pass attempted to resolve targets from free-text notes and
name aliases. Historical spelling variation can make that unsafe. An approved exact
`xml:id` makes the human decision machine-actionable and reproducible without fuzzy
matching.
