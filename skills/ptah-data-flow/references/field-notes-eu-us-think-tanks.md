# Field notes: EU/US think tanks

These notes came from a Ptah onboarding run for a 130-row EU/US think-tank CSV that became 125 deduped entities, a local Ptah CSV, an Airtable upload, and Gemini-generated `AI Context`.

## Learnings

### Duplicate reporting

The run removed 5 duplicate organization groups by normalized website domain/title:

- Finnish Institute of International Affairs / FIIA
- Polish Institute of International Affairs / PISM
- German Institute for International and Security Affairs / SWP
- Istituto Affari Internazionali / IAI
- Bertelsmann Stiftung

The dedupe was correct, but the user later needed a clear explanation. Future runs should emit a duplicate report whenever row count drops. Include source row numbers, titles, websites, dedupe key, kept row, merge policy, and reason.

### Taxonomy diagnostics

Initial topic assignment created oversized security and EU/international affairs buckets. The useful second look was not just counts; it was listing the entities inside each large bucket. Future Stage 3 runs should emit diagnostics with row id, name, final `Category`, final `Subcategory`, and assignment signal.

### Homogeneous directories

The default model says `Category = entity type`, but this dataset was already one entity type and the user wanted topic navigation. A topical model worked better:

- `Category = broad topic`
- `Subcategory = narrower topic`

Record this as an explicit exception when using it.

### Airtable upload shape

The ideal Ptah CSV was not the safest Airtable API upload file because the remote table had type drift:

- `Id` was numeric
- `Logo` was attachments
- `Tech Capabilities` was multi-select
- `Updated At` was initially `dateTime`

The successful pattern was to keep the local 12-field Ptah CSV, then create a separate schema-safe Airtable upload CSV that omitted blank or incompatible fields.

### `Updated At` repair limitation

Even with schema write permissions, Airtable rejected both direct conversion of `Updated At` to `lastModifiedTime` and creation of a replacement `lastModifiedTime` field through the Metadata API. The user had to repair it manually in the Airtable UI. After that, the audit passed.

Future runs should expect this limitation and avoid promising that the API can always create or convert `lastModifiedTime`.

### Partial enrichment updates

`AI Context` was generated after initial upload and then pushed as a two-column update:

- `Id`
- `AI Context`

This avoided re-sending fields with special Airtable types. Use this pattern for enrichment passes.

### Gemini workflow

The reusable Gemini runner worked well after adapting:

- prompt
- context columns
- link columns
- heading contract
- cache directory

The reliable sequence was:

1. run a small sample
2. inspect generated rows
3. validate fill rate, headings, URL leakage, and word count
4. run the full batch
5. push only the enriched field to Airtable

### Credential handling

A quick `grep` for `GEMINI_API_KEY` exposed the secret value in terminal output. Future credential discovery should report only presence and path, never values.

### Progress log hygiene

The progress log should preserve failed repair attempts as findings, but once the user resolves a blocker, the current stage and next moves should be rewritten so future sessions do not treat resolved work as still pending.
