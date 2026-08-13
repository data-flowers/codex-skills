# Airtable boundary

Use this reference when publish, schema, permissions, or connection repair is involved.

## Contents

- [Airtable's role](#airtables-role)
- [Normal ownership flow](#normal-ownership-flow)
- [The current downstream contract](#the-current-downstream-contract)
- [Local publish artifact vs upload artifact](#local-publish-artifact-vs-upload-artifact)
- [New-table Updated At provisioning](#new-table-updated-at-provisioning)
- [Clean sibling-table migration](#clean-sibling-table-migration)
- [What to inspect first](#what-to-inspect-first)
- [View semantics and control fields](#view-semantics-and-control-fields)
- [Generic schema audit](#generic-schema-audit)
- [Incremental Airtable maintenance](#incremental-airtable-maintenance)
- [What to ask for before publish](#what-to-ask-for-before-publish)
- [Update behavior for existing Airtable tables](#update-behavior-for-existing-airtable-tables)
- [Post-upload verification](#post-upload-verification)
- [Share step for Ptah connection](#share-step-for-ptah-connection)
- [Ptah Airtable connection API](#ptah-airtable-connection-api)
- [PAT requirements](#pat-requirements)
- [URL and identifier rules](#url-and-identifier-rules)
- [Common permission failures](#common-permission-failures)
- [Field-type expectations](#field-type-expectations)
- [Boundary workflow](#boundary-workflow)
- [Bundled boundary tools](#bundled-boundary-tools)

## Airtable's role

In this workflow, Airtable is:

- storage
- publish plumbing
- schema boundary for Ptah compatibility

It is not the main editing model.

If Airtable gets messy, prefer rebuilding or repairing from the local working dataset before doing manual base surgery.

## Normal ownership flow

The normal flow for this skill is:

1. the user has or creates their own Airtable base
2. the user can import the curated CSV through the Airtable GUI
3. if Ptah connection is the next downstream step, the user shares the Airtable base with the required admin contacts
4. if the user wants the skill to inspect, repair, or upload through the API, the user creates a PAT with the required scopes and access to that base
5. the skill inspects, audits, and repairs the target table shape when there is a safe deterministic path
6. the skill uploads the curated CSV into that base when API publish is actually in scope

Do not assume base creation over API in the default workflow.

Default publish path:

- use the API helpers when the target is known and an authorized PAT is already
  present in the current workspace or explicitly named source
- otherwise use GUI CSV import; do not search unrelated projects for a working PAT
- if the user simply says they want Airtable, default to GUI guidance unless an
  existing remote target and authorized PAT are already recorded in current state

Remote-boundary path:

- only when the progress log already records an Airtable URL or other active remote-boundary state
- or when the user provides an Airtable URL

## The current downstream contract

The target fields are:

1. `Id`
2. `Category`
3. `Subcategory`
4. `Name`
5. `Website`
6. `Logo`
7. `Description`
8. `Year Founded`
9. `Email`
10. `Tech Capabilities`
11. `Updated At`
12. `AI Context`

Do not assume names or types. Inspect the real base.

## Local publish artifact vs upload artifact

A clean local 12-field Ptah CSV is the canonical publish shape, but it is not always the safest API upload file.

CSV is a value transport, not an Airtable schema transport. It cannot encode or preserve computed field types such as `lastModifiedTime`.

After inspecting the Airtable schema, create a separate upload artifact when needed. This artifact may:

- omit fields that are blank and incompatible with the remote type, such as empty attachment fields
- omit fields that Airtable manages, such as `Updated At`
- omit or defer fields whose source values do not match the remote field type, such as a free-text capability list going into `multipleSelects`
- include only a stable merge key plus one enriched field for partial updates, such as `Id` and `AI Context`

Create a verification manifest beside the upload artifact. Record exact row and
unique-id counts, intended create/update/skip counts, omitted fields, control
field values, placeholder exclusions, and the expected destination-view count.
Treat `Id` as text in both the artifact and remote schema.

Record both artifacts separately in the progress log. Do not treat an upload-safe subset as a replacement for the canonical local Ptah artifact.

For Airtable row import, omitting `Updated At` is mandatory. The local canonical artifact may retain the blank column for the 12-field contract, but no GUI import or API upsert should use that column to create or populate the Airtable field.

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
7. Record the new table and view ids and names in the progress log. Treat that
   clean table as the active boundary; keep the original table recorded as
   untouched or superseded, not silently forgotten.

## What to inspect first

Use:

- [`scripts/inspect_airtable_table.mjs`](../scripts/inspect_airtable_table.mjs)
- [`scripts/audit_airtable_schema.mjs`](../scripts/audit_airtable_schema.mjs)
- [`scripts/mutate_airtable_schema.mjs`](../scripts/mutate_airtable_schema.mjs)

This is useful because it tells you:

- `baseId`
- `tableId`
- `viewId`
- table name
- view name
- record count
- real schema
- field types

It also helps separate:

- permission problems
- base or table lookup problems
- schema drift

## View semantics and control fields

The 12-field contract does not describe every condition that makes a row visible in a published view. Inspect the target view and all control or grouping fields before building the upload artifact.

Common examples include:

- `Published`
- `Status`
- `Record State`
- `Company Group`

Resolve the view's filter conditions when the available API or authenticated UI exposes them. Otherwise infer required states from existing rows, view behavior, or explicit user instructions and record the assumption.

Set each required control field deliberately with its real Airtable type. After upload, verify the destination view count as well as the table count, and read back the control values across all published rows. A correct table count with an empty filtered view is a failed publish.

Do not set `Published=true` across an event-derived dataset before auditing
placeholder, individual, private, student, and “no organization” registrations.
Record explicit include/exclude counts in the upload manifest.

Before changing single-select control fields, inspect their allowed choices. Do not invent states such as `Unpublished` or `Inactive`; use an existing valid value or stop for a schema decision. Treat the complete set of fields used by the view filter as one publication-control tuple. Changing `Published` alone is insufficient when the view also filters on `Status` or `Record State`.

## Generic schema audit

Treat schema audit as a distinct step, not just a quick glance at field names.

At minimum, audit:

- exact field names against the Ptah contract
- hidden header pollution such as BOM or leading/trailing whitespace
- missing required fields
- truly blocking boundary field types, especially `Updated At`

Examples of schema issues this should catch:

- `Id` is really `﻿Id`
- `Updated At` is not a `lastModifiedTime` field
- a required field is missing or renamed

When a schema problem is found:

- record it in the progress log as a schema issue, not a data issue
- repair it directly if the bundled mutation helper can do it
- otherwise tell the user exactly what still needs manual repair
- do not stop on non-blocking Airtable cleanup unless the user explicitly asks for schema cleanup
- `Updated At` is not non-blocking cleanup; if it is not `lastModifiedTime`, the boundary is still blocked

This makes the workflow more generic than special-casing one broken header.

Use the bundled audit helper for this:

- [`scripts/audit_airtable_schema.mjs`](../scripts/audit_airtable_schema.mjs)

Use it before hand-editing the Airtable table when you need a clean answer on whether the remote schema is actually Ptah-compatible.

If the audit reveals a contract mismatch, use the bundled mutation helper next:

- [`scripts/mutate_airtable_schema.mjs`](../scripts/mutate_airtable_schema.mjs)

Use it in this order:

1. inspect
2. audit
3. mutate the schema fixes the helper knows how to make
4. inspect again
5. continue with upload or Ptah connection work

The current direct repairs are:

- rename polluted field names such as `﻿Id` to exact contract names
- create missing contract fields when the helper has a deterministic create path

The helper does not repair Airtable field types. If a non-blocking type cleanup would require the Airtable UI, do not treat it as a blocker by default.

Exception:

- `Updated At` must be a real Airtable `lastModifiedTime` field
- if it is not, treat that as a blocking schema defect
- repair it directly when the API path is available
- otherwise tell the user exactly what manual Airtable change is still required before calling the boundary clean

Practical Airtable limitation:

- Airtable's Metadata API may reject creating a `lastModifiedTime` field with `UNSUPPORTED_FIELD_TYPE_FOR_CREATE`
- Airtable may also reject direct type conversion from `dateTime` to `lastModifiedTime`
- if you try a rename-plus-create repair, make the operation rollback-safe and verify the final field names afterward
- if API repair is rejected, tell the user to repair `Updated At` in the Airtable UI and rerun the schema audit afterward
- for a not-yet-imported table, require that UI repair before importing rows; do not let CSV import create a temporary `dateTime` field

If something still cannot be repaired by the helper and it is actually blocking the downstream flow, call it out plainly as remaining manual repair.

For Ptah connection work, use this inspect step before building the connection payload.

The Airtable URL gives you ids:

- `baseId`
- `tableId`
- `viewId`

The Ptah connection payload needs:

- `baseId`
- `tableName`
- `view`

So the normal sequence is:

1. parse the Airtable URL
2. get the Airtable PAT
3. run [`scripts/inspect_airtable_table.mjs`](../scripts/inspect_airtable_table.mjs)
4. run [`scripts/audit_airtable_schema.mjs`](../scripts/audit_airtable_schema.mjs)
5. if the audit shows a contract mismatch, run [`scripts/mutate_airtable_schema.mjs`](../scripts/mutate_airtable_schema.mjs) and inspect again
6. resolve the real table name and view name from the remote schema
7. write both ids and names into the progress log
8. use those resolved values for Ptah connection `test`
9. if `test` succeeds, run `save`

Do not ask the user to translate Airtable ids into names by hand.

If you already have:

- an Airtable URL
- an Airtable PAT

you have enough to inspect the target and resolve the required Airtable names yourself.

You also have enough to run the schema audit and apply safe deterministic schema repairs yourself.

## Incremental Airtable maintenance

Use this when the table is already published and the user asks to update one row, one new row, missing `AI Context`, stale descriptions, or another narrow data-quality issue.

Default sequence:

1. read the progress log for the current Airtable URL, ids, PAT status, and source-of-truth paths
2. re-export the current view from Airtable
3. identify the smallest target set:
   - explicit record id
   - explicit entity name
   - rows where the target field is blank
   - rows whose source-field hash changed since the cached generation
4. generate or repair only those rows
5. validate locally
6. PATCH Airtable by record id with only the intended changed field(s)
7. re-export Airtable and verify the remote values

When a local seed list gained entries:

1. diff the current raw seeds against the source aliases preserved in the
   canonical dataset
2. research and canonicalize only unseen seeds
3. dedupe new candidates against existing websites, names, and known aliases
4. preserve all seed aliases when multiple seeds resolve to one entity
5. assign stable ids only to truly new entities
6. generate a new-row upload artifact and upload only that delta
7. only when explicitly requested, handle new logos as a separate attachment delta
8. re-read the full view and verify total ids, published state, AI Context, and
   preservation of existing attachments; verify logo counts only when logo work
   was explicitly in scope

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

### Logo attachment fast path

Use this when the user asks to add or replace a logo for one known entity in an already-published Airtable table.

If the source is oversized, multiple logos need recurring refreshes, or
optimized Airtable storage is part of the request, read
[`attachment-images.md`](attachment-images.md) and use or adapt
[`scripts/optimize_airtable_attachments.py`](../scripts/optimize_airtable_attachments.py).

1. read the progress log for the Airtable ids, PAT status, and current export path
2. locate the live target row by current Airtable export or filtered records API; prefer the Airtable `record_id` over CSV `Id`
3. build and review a first-party candidate inventory before selecting one stable,
   official, publicly reachable image URL:
   - inspect HTML icon links, manifests, metadata, CSS/JS references, official
     asset directories, and reasonable same-origin sibling filenames and formats
   - do not stop at a tiny root favicon when the site may expose a larger logo,
     animated favicon, app icon, wordmark, or product mark elsewhere
   - download and visually compare plausible candidates; reject unrelated UI
     glyphs or decorative assets even when their paths contain `logo` or `icon`
   - prefer an explicit official logo/brand asset, then a verified official
     favicon, site icon, or app icon suitable for card use
   - avoid broad image search unless the official site does not expose a usable asset
   - avoid date/header/hero assets when a standalone square or wordmark logo exists
   - if the logo is white on transparent and cards are likely light, prefer an official square icon or colored-background variant
   - if the first-party pass finds nothing suitable, leave `Logo` blank; create
     a non-official wordmark only with explicit user approval and provenance
   - treat SVG and ICO as source formats only; convert them locally to a reviewed
     PNG or WebP and do not PATCH the original URL into Airtable
4. check the image once before patching:
   - `HEAD` or download should return `200`
   - content type should be a supported raster image type Airtable can ingest;
     direct SVG and ICO attachments are unsupported
   - dimensions should be suitable for display, usually square or a clear wordmark
   - if either dimension exceeds the viewer's realistic render size, transform
     it locally before upload; use a 256-pixel maximum dimension by default and
     treat 512 pixels as a ceiling for verified high-density or detailed needs
   - inspect alpha and contrast on both light and dark card surfaces; for a
     white/translucent mark, composite it onto an official brand or site-theme
     background and run the optimizer with `--require-opaque`
5. PATCH only the `Logo` field:

```json
{
  "records": [
    {
      "id": "rec...",
      "fields": {
        "Logo": [
          {
            "url": "https://example.com/logo.png",
            "filename": "entity-logo.png"
          }
        ]
      }
    }
  ]
}
```

6. verify the same record after Airtable processes the attachment:
   - `Logo` attachment count is exactly what was intended
   - attachment `type`, `size`, `width`, `height`, URL, and thumbnails are present when available
   - untouched fields such as `Name`, `Website`, `AI Context`, and `Published` still have expected values
   - download the Airtable-served full image and generated thumbnail; require
     the full-file hash to match the reviewed asset and the thumbnail to remain
     opaque when a contrast background was required
7. re-export the view only after the successful patch if the local export is used as a handoff artifact
8. update the progress log with the record id, source image URL, attachment count, dimensions, and refreshed export path

This fast path should normally avoid full schema audits, AI generation, full CSV rewrites, and repeated page scraping unless the remote boundary is unknown or the logo source is ambiguous.

For transformed attachments, upload the optimized bytes first, identify the
new attachment id, then PATCH only `Logo` to retain that id. Never clear the
old attachment before the upload succeeds.

SVG/ICO conversion is always a transformed-attachment workflow. Run the local
prepare phase first, then upload and attach the converted raster bytes. A public
SVG/ICO URL is not a valid fast-path attachment payload.

Preservation checks after maintenance:

- compare untouched fields for every patched record before and after upload when a local pre-patch export exists
- always check attachment presence/count for `Logo` on touched rows
- if a URL-like Airtable attachment export changes but the attachment is still present, treat that as likely Airtable URL rotation, not automatically as data loss
- if an attachment count changes, stop and report the row ids before doing further writes
- re-run the schema audit if the update touched boundary setup or if the remote behavior looks surprising

## What to ask for before publish

Priority rule:

- first check the progress log for an existing Airtable URL, base, table, view, and PAT status
- if that remote state is already recorded, treat it as the current boundary context
- only ask the user again if the progress log is missing that information or looks stale

If the user wants remote Airtable work, the key input is:

- an Airtable URL

If the user provides an Airtable URL:

- treat that as the remote target
- record the URL and parsed ids in the progress log
- ask for the Airtable PAT immediately
- ask for the full Airtable PAT secret, not just the visible token id shown later in the Airtable UI
- tell the user to copy and save the full PAT when they create it, because Airtable may only show the short token id after the first view
- once the PAT is received, prefer storing it in a working-area `.env` file that is excluded from git and run API helpers through environment variables rather than repeating the token inline in commands
- do not paste raw PAT values into the progress log or routine handoff notes; record only whether the token is present and where the local `.env` lives if that path matters
- do not continue with remote inspection or upload until the PAT is available
- once the PAT is available, inspect and audit the remote schema before upload or Ptah connection work
- if the audit shows a contract mismatch, use the bundled mutation helper instead of asking the user to rename fields by hand

If the user refers to an existing Airtable key instead of pasting one, for example "use the Airtable token from aipanic" or "use the existing PAT from euro-stack":

- find the referenced local `.env` or trusted workspace source
- copy the Airtable secret and any explicitly needed Airtable ids into the current working area's `.env`
- keep the current target base/table/view ids authoritative if the user supplied a new target; do not accidentally reuse stale ids from the source `.env`
- make sure the current working area's `.env` is gitignored
- record only `Airtable PAT: present` in the progress log, plus the fact that the token was copied from a local named source if useful
- do not print the token or keep using inline secret-bearing commands once the local `.env` exists

If the user says only “use the PAT” and the active environment has no PAT:

- do not enumerate or test credentials from unrelated projects
- ask the user to name the authorized source or configure the active `.env`
- read [credential-sourcing.md](credential-sourcing.md) for the shared rule

If the user has no Airtable URL yet:

- do not pretend remote inspection is possible
- default to GUI CSV import guidance
- ask the user to create or choose the Airtable base and send the URL if they want the skill to inspect, repair, or upload the remote table

If the user does not have a base yet, the default path is:

- ask them to create or choose the Airtable base first
- then continue with schema inspection and upload


## Update behavior for existing Airtable tables

Prefer minimal, targeted Airtable changes. When the table already contains records, do not delete and reupload the table by default.

Default order for API updates:

1. build the canonical local artifact
2. derive an upload-safe subset with only the merge key and changed fields
3. dry-run schema validation
4. patch/upsert only those fields
5. read back count and a small field sample

Full replacement is allowed only when one of these is true:

- the user explicitly asks to replace or discard existing rows
- stale rows must be removed and there is no reliable delete-by-diff path
- the table is a disposable staging table
- record identity does not matter and this is recorded in the progress log

For taxonomy-only updates, preserve Airtable record identity when possible. Patch `Category`, `Subcategory`, and any regenerated text fields against a stable key such as `Id`; do not resend attachment, multiselect, or Airtable-managed fields unless they actually need to change.

For capability-only updates on compact viewers, derive an `Id`, `Tech Capabilities` artifact. Prefer exactly three high-signal semicolon-delimited labels around 16 characters or fewer each, PATCH only those fields, and verify publish state, AI Context, attachments, and record identity afterward.

For publish-state changes, PATCH only the stable key plus every control field
required by the destination view, using real typed values. For example, a
retirement may require `Published=false`, `Status=Retired`, and
`Record State=Retired`; derive the actual tuple from the view and schema instead
of assuming these labels exist. If the same bounded operation also fills
`AI Context`, include it in the narrow artifact; verify every changed field and
confirm that logos and record identity remain unchanged.

If rows must be removed, prefer a targeted delete of only rows absent from the trusted source over deleting every record and reuploading the survivors.

## Post-upload verification

After an API upload or partial update:

- inspect the table or view again to verify record count
- read back a small sample of the intended fields, such as `Id`, `Name`, and `AI Context`
- for enrichment updates, count created vs updated records and confirm the update did not create duplicates
- verify destination-view count and every publish-control or grouping field required for rows to appear downstream
- for retirement, verify the full table still contains the preserved records, the published view excludes them, and no unrelated records left the view
- verify preserved original taxonomy helper fields or context markers when reclassification was part of the request
- record the verification in the progress log
- reconcile the compact state file in the same successful operation; remove
  resolved blockers and stale next actions

After a GUI CSV import:

- enable **Exclude first row in import** when the CSV contains headers
- map every intended field and confirm omitted fields were not recreated
- require the preview count to equal the manifest count before selecting Import
- cancel rather than accepting an unexplained off-by-one count
- verify `Id` remains text and `Updated At` remains `lastModifiedTime`

## Share step for Ptah connection

After the user has imported the CSV into Airtable and has the correct table/view:

1. click the `Share` button
2. under `Invite collaborators`, use the invite-by-email field
3. add:
   - `aleks@data.flowers`
   - `Davor Strehar`
4. uncheck `Notify people`

After that, the base is ready for the Ptah connection flow.

If the user asks how to continue after GUI import, this should be the default next step.

## Ptah Airtable connection API

If a running Ptah admin surface is in scope, the bundled frontend shows a deterministic Airtable connection admin API:

- `POST /airtable-admin/test`
- `POST /airtable-admin`

The frontend form sends these payload fields:

- `id`
- `name`
- `baseId`
- `tableName`
- `view`
- `fieldMap`
- `layoutOverrides`
- `mapInfo`
- `lastModifiedField`
- `createdAt`
- `updatedAt`

Do not guess this payload shape from memory. Reuse the bundled helper:

- [`scripts/ptah_airtable_connection.mjs`](../scripts/ptah_airtable_connection.mjs)

Use this helper for:

- `test`
- `save`

For this skill, keep the user-facing workflow simple:

- `test` the connection
- `save` a connection

If the connection settings changed, save a fresh connection and record the new connection id in the progress log.

If Ptah connection setup is in scope:

- first inspect the Airtable target so you have the real table name and view name
- build the Ptah payload from `baseId` plus the resolved `tableName` and `view`, not from Airtable table/view ids
- test the Ptah Airtable connection before saving it
- do not ask the user for base name, table name, or view name if those can already be resolved from the Airtable URL plus PAT
- record the Ptah admin origin in the progress log if known
- record the resolved Airtable base, table, and view names after inspect
- record whether the Airtable connection has already been tested
- record the saved Ptah connection id after a successful save
- after save, call the live provider endpoint and verify expected count, unique ids, taxonomy coverage, one representative mapped row, and native timestamp behavior
- prefer the deterministic helper over ad hoc fetch snippets

## PAT requirements

Use a personal access token from:

- `https://airtable.com/create/tokens`

Recommended scopes for this workflow:

- `data.records:read`
- `data.records:write`
- `schema.bases:read`
- `schema.bases:write`

Recommended access:

- grant access to the specific target base or workspace

Important:

- the PAT only works within the permissions of the user who created it
- giving a PAT scopes is not enough; the token must also have access to the target base or workspace
- if the user copied or newly created a base, make sure that base was added to the PAT's resource access
- use the full PAT secret for API calls, not the short token id that Airtable may still show in the developer hub later
- when asking for the PAT, tell the user to save the full secret immediately at creation time
- do not write the PAT value into the progress log; record only whether it is present or missing

## URL and identifier rules

An Airtable URL usually contains:

- base id like `app...`
- table id like `tbl...`
- view id like `viw...`

Do not confuse names with ids.

In practice you may need both:

- ids to address the boundary reliably
- names to explain what the user is looking at

## Common permission failures

### Metadata fetch fails

If schema fetch fails, likely causes include:

- token missing `schema.bases:read`
- token has no access to the target base
- wrong base id

### Records API works but schema API fails

This usually means:

- the token can read records
- but cannot read metadata

Do not call the table “empty with known schema” unless metadata actually succeeded.

### Create or publish fails on a copied base

This often means:

- the copied base was not added to the PAT's access list
- or the PAT is missing write-related schema scope

### User has a PAT but no target base

This is not enough for the normal flow.

Default behavior:

- have the user create or choose the target base first
- then inspect the real schema and upload into that base

Do not promise API-created bases unless the user explicitly has an Airtable plan and API path that supports it.

### User has a target Airtable URL but no PAT

This is a real blocker for remote inspection, repair, or upload.

Default behavior:

- keep working locally if there is still local work to do
- if the next step is remote Airtable work, ask for the PAT immediately
- record PAT status as `missing` in the progress log

## Field-type expectations

Always inspect the actual base. Do not assume from memory.

Examples of field semantics:

- `Category`: may be `singleLineText` or `singleSelect`; check the real schema
- `Subcategory`: usually a text-like field in this workflow, but confirm
- `Updated At`: must be an Airtable `lastModifiedTime` field, not a normal text or date field
- `AI Context`: normal long text is acceptable
- `Published`: when present, use an Airtable checkbox and send JSON booleans,
  not the strings `"true"` or `"false"`

## Boundary workflow

### Before publish

- confirm the user has a PAT with the required scopes
- confirm the PAT has access to the target base or workspace
- confirm whether the target base already exists
- inspect schema
- confirm field order
- confirm field types
- confirm required boundary fields
- confirm base/table/view target
- run the dataset gate and resolve publication eligibility for non-organizations
- write an upload manifest with exact expected create/update/skip and view counts
- for a new table, audit native `Updated At` before importing an upload artifact that omits it

### During repair

- inspect metadata first
- determine whether the issue is access, schema, table lookup, or data quality
- if the issue is data quality, route back upstream

### Upload batching

- For Airtable publish and maintenance jobs, process records in 100-record work batches by default.
- If the Airtable endpoint or helper enforces a lower per-request record limit, keep the 100-record work batch but subchunk internally to the endpoint-safe request size.
- Keep upload output phrased in both layers when relevant: work batches for operator progress, API requests for rate-limit/debugging clarity.

### After publish

- verify record count
- verify a few rows against the working dataset
- rerun the schema audit and confirm `Updated At` remains `lastModifiedTime`
- compare remote counts and samples with the upload manifest
- reconcile `ptah-data-flow.state.json` with verified local and remote facts
- only then debug Ptah viewer behavior

## Bundled boundary tools

- [`scripts/audit_ptah_dataset.py`](../scripts/audit_ptah_dataset.py)
  - deterministic canonical, taxonomy-readiness, publication, upload, and state
    freshness gate
- [`scripts/inspect_airtable_table.mjs`](../scripts/inspect_airtable_table.mjs)
  - schema and record inspection
- [`scripts/audit_airtable_schema.mjs`](../scripts/audit_airtable_schema.mjs)
  - contract-aware Airtable schema audit
- [`scripts/upsert_airtable_csv.mjs`](../scripts/upsert_airtable_csv.mjs)
  - generic dry-run or execute path for batched CSV upserts, including typed
    checkbox conversion for optional control fields such as `Published`
- [`scripts/ptah_airtable_connection.mjs`](../scripts/ptah_airtable_connection.mjs)
  - Ptah Airtable connection test/save helper against `/airtable-admin`
- [`scripts/optimize_airtable_attachments.py`](../scripts/optimize_airtable_attachments.py)
  - SVG/ICO-to-WebP normalization, ImageMagick transform, manifest, upload-first
    attachment replacement, and unrelated-field, opacity, served-byte, and
    thumbnail verification
- [`scripts/build_contrast_logo_card.py`](../scripts/build_contrast_logo_card.py)
  - deterministic opaque brand-card compositing with dual keylines for white and
    black surface compatibility

Use these bundled tools by default. Do not go looking for other Airtable helpers elsewhere in the user's workspace unless the user explicitly points you to one.
