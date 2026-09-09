# Routine Airtable maintenance

Use for bounded edits to an already verified table. Read
[airtable-boundary.md](airtable-boundary.md) for first/full publication, schema
changes, or surprising remote behavior.

## Incremental Airtable maintenance

Use this when the table is already published and the user asks to update one row, one new row, missing `AI Context`, stale descriptions, or another narrow data-quality issue.

Default sequence:

1. reuse the recorded Airtable target, stable ids, credential source, and canonical source path
2. identify the smallest target set from the canonical local data and the user's requested change:
   - explicit record id
   - explicit entity name
   - rows where the target field is blank
   - rows whose source-field hash changed since the cached generation
3. generate or repair only those rows
4. validate only the changed values, ids, and category/subcategory pairs locally
5. update the canonical dataset
6. PATCH Airtable by record id or stable merge key with only the intended changed field(s)
7. accept a successful Airtable response as completion and stop

For this routine path, do not run a schema preflight, generic dry run, remote
readback, full export, count check, whole-dataset distribution, state/hash
reconciliation, browser check, or build a snapshot, manifest, guard ledger, or
rollback CSV. Narrow field omission is the preservation mechanism. Add heavier
controls only for a first/full publish, large import or delete, destructive
operation, schema mutation, attachment replacement, publication or
view-membership change, deployment, ambiguous/stale remote state, surprising API
behavior, an explicit user request, or another concrete high-risk condition.

If concurrent writers later become a real operating condition, fetch only the
touched rows immediately before the PATCH and compare only the target fields
with their previous canonical values. Patch matching rows and report conflicting
rows without overwriting them. Do not introduce locks, global diffs, revision
manifests, or full-table reconciliation for normally small concurrent changes.

When a local seed list gained entries:

1. diff the current raw seeds against the source aliases preserved in the
   canonical dataset
2. research and canonicalize only unseen seeds
3. dedupe new candidates against existing websites, names, and known aliases
4. preserve all seed aliases when multiple seeds resolve to one entity
5. assign stable ids only to truly new entities
6. generate a new-row upload artifact and upload only that delta
7. only when explicitly requested, handle new logos as a separate attachment delta
8. for a large batch or publish-state change, perform the applicable
   comprehensive verification; otherwise trust the successful narrow PATCH

For single-field updates, the PATCH payload must be narrow:

```json
{
  "records": [
    {
      "id": "rec...",
      "fields": {
        "AI Context": "..."
      }
    }
  ]
}
```

Do not send full row payloads for maintenance updates. This is especially important for attachment fields such as `Logo`; omitting `Logo` from a PATCH preserves it, while sending a stale or malformed `Logo` value can damage it.

## Bundled update command

`upsert_airtable_csv.mjs` supports both stable-key upserts and known-record
updates. General uploads reject `Logo`, all attachment fields, and `Updated At`.
Blank cells are omitted by default; list intentional clears in `--clear-fields`.
Keys cannot be blank, duplicated, or cleared. Keep `Id` as `singleLineText`.

For a verified target, retain the applicable metadata in a small boundary file:

```json
{
  "version": 1,
  "baseId": "appExample",
  "table": {
    "id": "tblExample",
    "name": "Organizations",
    "fields": [
      {"name": "Id", "type": "singleLineText"},
      {"name": "Description", "type": "multilineText"}
    ]
  }
}
```

This file comes from the already completed inspection; do not add a new schema
request or rewrite it for each routine edit. It must cover the fields being
changed and match the actual target. Keep select choices when relevant.

A CSV with `Record Id,Description` can update existing records directly:

```bash
node scripts/upsert_airtable_csv.mjs --base appExample --table tblExample \
  --csv changed-descriptions.csv --boundary airtable-boundary.json \
  --record-id-column 'Record Id' --execute
```

Use actual `rec...` ids in that column. This path sends only PATCH requests and
cannot create records. For an intended insert/upsert, omit `--record-id-column`
and use a CSV containing the stable text merge key, default `Id`. Add
`--clear-fields Description` only when blank descriptions should erase values.

When useful, validate a delta with `audit_ptah_dataset.py delta.csv --kind delta`.
For taxonomy edits, include the category/subcategory pair and `--taxonomy` so the
changed pair can be checked. Full-dataset gates do not apply to this path.

## Escalating verification

Use comprehensive verification for first/full publication, large imports or
deletes, schema or attachment changes, publication/view changes, deployment,
stale boundaries, surprising responses, or an explicit user request. Read back
the relevant fields and view membership for those operations. Preserve records
on retirement; patch the complete control tuple required by the actual view.

For explicit logo work, follow [attachment images](attachment-images.md).
