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

## New-table `Updated At` Provisioning

CSV import does not retain Airtable computed-field semantics. Importing an `Updated At` column into a new table can create an ordinary `dateTime` or text field with the right label but the wrong behavior.

For every new or clean sibling table, preserve the native field by duplicating a correctly typed table structure, or create `Updated At` in the Airtable UI as **Last modified time** before row import. Audit the empty table, omit `Updated At` from the upload artifact, import rows, and audit again. Never repair this by uploading timestamp values or renaming a normal date field.

## Partial Enrichment Updates

For enrichment passes after initial upload, prefer pushing only stable key fields plus the enriched target field. This avoids re-sending fields with special Airtable types.

## Compact Capability Labels

Long capability inventories become unreadable on card surfaces. When the user asks for succinct `Tech Capabilities`, select exactly three high-signal labels per row, keep each label around 16 characters or fewer, and validate this invariant in the dataset builder. Patch Airtable with only `Id` and `Tech Capabilities`, then verify published state, AI Context, attachments, and record identity.

## Dual-background Logo Cards

An opaque black card can still lose its edge on black, and a white card can disappear on white. Preserve the official mark and brand/site background, then add an outer white keyline plus an inner black keyline, or an equivalent opposite-color pair. Verify the rendered card and the Airtable-served smallest thumbnail on both pure-white and pure-black surfaces. Do not use a generative redraw when deterministic compositing preserves the real mark.

## Official Asset Discovery Before Fallbacks

A root favicon may be only the most obvious asset, not the best available official mark. When logo work is explicitly requested, inventory HTML icon links, manifests, metadata, CSS/JS references, and plausible same-origin asset directories and sibling filenames before using a third-party service or creating anything. Fetch and visually compare candidates because filenames and directories can contain unrelated UI glyphs. If no official candidate is suitable, leave the logo blank by default; require explicit user approval for a clearly labeled non-official wordmark or generic fallback.

## SVG and ICO Attachment Sources

Treat SVG and ICO as unsupported final attachments even when they are the best official source asset. Normalize them locally before upload. Default to a 256-pixel final maximum, rasterize SVG at 2× the intended output with a 1024-pixel intermediate cap, and select the smallest ICO frame that meets the target or otherwise the largest available frame without upscaling. Use 128 pixels for simple small-card icons when sufficient; reserve the 512-pixel ceiling for verified high-density or detailed-logo needs. Encode the result as a reviewed PNG or WebP, and never place the original SVG/ICO URL directly in an Airtable attachment field.

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

## Reclassification Preservation

When a user asks to start from a source category and then re-evaluate it, preserve three layers: explicit initial classification, final Ptah classification, and untouched original source labels. Verify all three mechanically after publish. Do not reinterpret the source field in place or allow the new taxonomy to overwrite the provenance needed to explain the original classification.

## Evidence-tiered Enrichment

Classify enrichment as direct-source, supported-fallback, or limited. Keep per-row provenance and publish a coverage summary before curation. A small number of limited rows is acceptable when evidence is genuinely weak; fabricated completeness is not.

## Airtable View Controls

Published visibility may depend on fields outside the 12-field contract. Inspect and verify view filters plus control fields such as publish flags, status, record state, and grouping. Verify the filtered destination view count, not only the underlying table count.

## Website Liveness Is Evidence-Tiered

Do not retire an entity from one failed request. Retry scheme and hostname variants, follow redirects, distinguish DNS failure from TLS or automation blocking, and corroborate ambiguous results with an independent resolver or browser-backed source. Treat 401, 403, 429, timeouts, and bot challenges as manual review by default. Separate active, correctable URL, parked suspect, confirmed broken, and manual-review outcomes.

Research rebrands, acquisitions, and successor domains before retiring a row. Update `Website` when the same entity has moved, but reject a similar-looking domain when it belongs to another product. Record evidence and a reason for every correction or retirement.

## Retirement Preserves History

Retirement is normally a publication-state change, not deletion. Keep the row and its source taxonomy, descriptions, attachments, and stable id in the canonical dataset and underlying Airtable table. Exclude it from the filtered view and Ptah publish artifact through the complete valid control-field tuple, then verify both archive count and published count.

## Filtered-view Change Detection

A timestamp query scoped to a filtered view cannot see a record after that record leaves the view. After retirement or removal, test the gateway's update detector and live provider endpoint rather than assuming the cache refreshed. Prefer an explicit cache refresh or table-wide change signal. If none exists, use a reversible update to one still-published signal record only as a last resort: snapshot untouched fields, change the narrow control field, restore it immediately, verify preservation, and record the resulting visible timestamp.

## Website and Logo Health Are Independent

A dead homepage does not prove an Airtable-served logo attachment is broken, and a live homepage does not prove its logo asset has adequate contrast or remains reachable. Keep website-liveness maintenance field-scoped; route attachment failures through the logo workflow only when logo work is explicitly requested.

## Gateway Deployment Scope

A gateway name does not imply SSH. Resolve the real runtime, repository, hosting project, and deployment surface first. Inspect dirty state and deployment scripts for unrelated changes and companion services. Use the narrowest supported deployment path, and require explicit approval before publishing a broader dirty snapshot.

## Custom-domain Acceptance

An immutable hosting deployment may serve the new manifest before the custom domain converges. Do not accept direct access to a newly uploaded config as proof of routing. Require the custom-domain manifest to map the hostname to the intended map, then verify config, provider count, unique ids, taxonomy, settings, and a non-sending invalid submission.

## Canonical Deployment Source

An isolated snapshot can make a safe build possible, but it is not durable configuration ownership. Ensure the deployed map config is merged into the canonical gateway repository or record the persistence risk as open. A future routine deployment must not silently remove the map.
