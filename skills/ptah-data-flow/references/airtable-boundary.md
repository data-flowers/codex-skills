# Airtable publication boundary

Use for first/full publication, schema changes, or surprising remote state.
For routine edits read [maintenance](airtable-maintenance.md); for credentials
and Ptah test/save read [connection setup](airtable-connection.md).

## Contract and artifacts

Airtable stores and publishes the canonical local data. Field names, canonical
mappings, accepted types, computed fields, and upload exclusions are maintained
in [the executable contract](../scripts/ptah_contract.json). Read
[contracts.md](contracts.md) for domain semantics.

Keep the 12-field Ptah artifact separate from the upload artifact. General
uploads omit `Logo` and `Updated At`; attachment work has its own helper.
`Id` must remain opaque text in both CSV and Airtable. `Published` is an optional
control field outside the core contract and uses real booleans.

Before a full publication, validate the complete canonical or upload shape:

```bash
python3 scripts/audit_ptah_dataset.py entities.canonical.json \
  --kind canonical --taxonomy taxonomy.json --require-gate publication \
  --output publication-audit.json
```

The gate checks field presence, ids, temporal sanity, description coverage,
publication eligibility, and membership in the supplied taxonomy. Optional
values may be blank. Coverage is not evidence verification: review source
quality and unresolved claims separately. State freshness is reported separately
and does not prevent intentional edits from reaching a new milestone.

For high-risk publication, create a manifest with expected rows, unique ids,
create/update/skip counts, omitted fields, controls, exclusions, and destination
view count. Record artifact paths in current state after verification succeeds.

## Establish the remote target

Reuse the target and authorized credential source recorded in current state.
If remote work is requested and the required PAT is missing, ask for the missing
credential source while continuing independent local work. Follow
[credential-sourcing.md](credential-sourcing.md); do not search unrelated projects.
If no base exists, have the user choose or create one. Do not assume API base
creation. GUI CSV import remains available when API access is not configured.

Inspect once before first publish, when the boundary is stale, or when behavior
is surprising:

```bash
node scripts/inspect_airtable_table.mjs --url 'https://airtable.com/appExample/tblExample/viwExample' --json
node scripts/audit_airtable_schema.mjs --base appExample --table tblExample --json
```

Resolve ids and actual table/view names from metadata. The schema audit checks
exact names, invisible name pollution, missing fields, and accepted field types.
Use `mutate_airtable_schema.mjs plan` then `apply` for deterministic missing-field
creation and name repair within the requested scope. It reports type mismatches;
converting types requires a deliberate migration. Reinspect after schema changes.

## New-table `Updated At` provisioning

Use this order whenever creating a new table, including a clean sibling table:

1. Prefer duplicating a table or template whose `Updated At` field is already a native Airtable `Last modified time` field. Remove unwanted fields only after confirming the duplicate preserved the type.
2. If no correctly typed structure exists, create the table and add `Updated At` in the Airtable UI as **Last modified time**. Configure its watched fields according to the table's intended update semantics.
3. Run the schema audit on the empty table and require the Metadata API to report `lastModifiedTime`.
4. Derive an upload artifact that omits `Updated At`.
5. Import or upsert the rows.
6. Run the schema audit again and verify `Updated At` is still `lastModifiedTime`.

Do not:

- import an `Updated At` CSV column and assume Airtable will infer `Last modified time`
- accept a same-named `dateTime`, text, formula, or imported timestamp field
- upload timestamp values into `Updated At`
- declare the boundary clean before both audits pass

If Airtable's Metadata API rejects creation or conversion of `lastModifiedTime`, stop before row import and require UI provisioning. A `dateTime` fallback is a schema defect, not a partial success.

## Clean sibling-table migration

Use this when an existing Airtable table mixes the desired company/entity rows
with event, RSVP, location, or other unrelated fields and the user asks for a
clean map table.

1. Inspect the source table and identify the 12 contract fields plus any control
   fields the user explicitly wants retained, commonly `Published`.
2. Create the clean structure by duplicating a correctly typed table when
   possible. Otherwise create the fields in the Airtable UI and provision
   `Updated At` as **Last modified time** before importing rows. Do not delete or
   destructively reshape the source table unless the user explicitly requests it.
3. Audit the empty table and require `Updated At` to report
   `lastModifiedTime`; do not continue with a `dateTime` fallback.
4. Keep `Published` as a checkbox and decide its initial state explicitly; never
   lose it merely because it sits outside the core contract.
5. Derive and import an upload artifact that omits `Updated At` and `Logo`.
   Populate logos as a separate attachment workflow only when the user
   explicitly requests it.
6. Audit again, then verify row ids, record count, control-field state, AI
   Context completeness, and attachment preservation. Check logo completeness
   only when logo population was explicitly in scope.
7. Record the new table and view ids and names in current state. Treat that
   clean table as the active boundary; keep the original table recorded as
   untouched or superseded, not silently forgotten.

## View semantics and control fields

The 12-field contract does not describe every condition that makes a row visible in a published view. Inspect the target view and all control or grouping fields before building the upload artifact.

Common examples include:

- `Published`
- `Status`
- `Record State`
- `Company Group`

Resolve the view's filter conditions when the available API or authenticated UI exposes them. Otherwise infer required states from existing rows, view behavior, or explicit user instructions and record the assumption.

Set each required control field deliberately with its real Airtable type. After a
first/full publish or a control-field change, verify the destination view count
as well as the table count, and read back the control values across all published
rows. A correct table count with an empty filtered view is a failed publish.

Do not set `Published=true` across an event-derived dataset before auditing
placeholder, individual, private, student, and “no organization” registrations.
Record explicit include/exclude counts in the upload manifest.

Before changing single-select control fields, inspect their allowed choices. Do not invent states such as `Unpublished` or `Inactive`; use an existing valid value or stop for a schema decision. Treat the complete set of fields used by the view filter as one publication-control tuple. Changing `Published` alone is insufficient when the view also filters on `Status` or `Record State`.

## Upload and acceptance

Validate the CSV locally before requests. The upsert helper rejects missing,
blank, or duplicate merge keys; protected columns; invalid types; and malformed
row widths. It omits empty values unless `--clear-fields` explicitly names them.
Use text merge keys and send only the columns intended to change.

```bash
node scripts/upsert_airtable_csv.mjs --base appExample --table tblExample \
  --csv entities.upload.csv --execute
```

It groups work in 100-row batches and sends at most 10 records per API request.
Without `--execute` it prepares a dry run; without `--boundary` it inspects
metadata. The known-boundary path is documented in
[maintenance](airtable-maintenance.md). A failed or uncertain mutation stops;
inspect the affected rows before deciding whether to resume.

After first/full publication or another high-risk operation:

- Verify expected counts, unique ids, intended values, and publication/view membership.
- Confirm `Updated At` remains native `lastModifiedTime` after imports or schema changes.
- Verify preserved taxonomy helpers and attachment values when applicable.
- Reconcile current state from verified artifacts, then diagnose downstream viewer behavior.

For GUI import, exclude the header row, confirm the preview count against the
manifest, map only intended fields, and omit `Logo` and `Updated At`. Cancel an
unexplained count mismatch. A CSV cannot provision native computed-field types.

Proceed to [Ptah connection setup](airtable-connection.md) when requested, and
[gateway deployment](gateway-deployment.md) when hosting is in scope.
