# Field Notes

These are generalized implementation learnings from Ptah onboarding and maintenance work. Keep them project-neutral: do not record client names, exact row counts, base ids, tokens, or other dataset-specific identifiers here.

## Duplicate Reporting

Whenever dedupe changes row count, emit a duplicate report. Include source row numbers, names, websites, dedupe key, kept row, merge policy, and reason.

## Taxonomy Diagnostics

Do not review taxonomy with counts alone. For oversized buckets, list representative row ids and names inside each large bucket. Stage 3 diagnostics should include row id, name, final `Category`, final `Subcategory`, and assignment signal.

## Homogeneous Directories

The default model says `Category = entity type`, but some datasets already share one entity type and need navigation by topic, market, geography, role, or another user-facing axis. When using that exception, record it explicitly in the progress log.

## Airtable Upload Shape

The ideal local Ptah CSV is not always the safest Airtable API upload payload because remote tables may have type drift. Common examples:

- `Id` may be numeric
- `Logo` may be attachments
- `Tech Capabilities` may be multi-select
- `Updated At` must be a `lastModifiedTime` field

Keep the local 12-field Ptah CSV as the canonical publish artifact, but create schema-safe upload payloads when the Airtable API requires typed values.

## `Updated At` Repair Limitation

Do not promise that the Airtable Metadata API can always create or convert `Updated At` to `lastModifiedTime`. If API repair fails, record the failure and ask for manual UI repair.

## Partial Enrichment Updates

For enrichment passes after initial upload, prefer pushing only stable key fields plus the enriched target field. This avoids re-sending fields with special Airtable types.

## Gemini Workflow

When adapting Gemini runners:

1. adapt prompt, context columns, link columns, heading contract, and cache directory
2. run a small sample
3. inspect generated rows
4. validate fill rate, headings, URL leakage, and economy
5. run the full batch
6. push only the enriched field when possible

## Credential Handling

Credential discovery should report only presence and path, never secret values. Avoid commands that can print token values to terminal output.

## Progress Log Hygiene

The progress log should preserve failed repair attempts as findings, but once the user resolves a blocker, rewrite current stage and next moves so future sessions do not treat resolved work as still pending.

## Source Invalidation and Provenance

If the user later declares a source invalid, treat that as a source-of-truth change. Rebuild from the trusted source, regenerate provenance, and remove rows that no longer have provenance in the trusted source. Record the source invalidation in the progress log.

For HTML grids that store only links and logos, row names may be inferred from logo filenames or hostnames. Make that inference explicit in the provenance artifact so reviewers know which names are source text and which are recovered labels.

## Taxonomy Redundancy

Category and subcategory should not repeat each other. If `Category` already says the thing, `Subcategory` must add a useful second dimension or be omitted when the downstream surface supports category-only navigation.

Avoid one-row subcategory buckets unless the user intentionally wants them. After taxonomy assignment, validate distinct label counts, smallest bucket size, and word overlap between parent and child labels.

## Airtable Record Preservation

When updating Airtable, preserve record identity by default. Use upload-safe subset CSVs and patch only changed fields. Avoid delete-and-reupload flows unless the user explicitly asks for replacement or stale rows cannot be removed safely another way.
