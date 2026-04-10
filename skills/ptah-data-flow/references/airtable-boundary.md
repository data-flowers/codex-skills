# Airtable boundary

Use this reference when publish, schema, permissions, or connection repair is involved.

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

- GUI CSV import first
- if the user simply says they want Airtable, this is the default answer unless an existing remote Airtable target is already recorded in the progress log

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

If the user has no Airtable URL yet:

- do not pretend remote inspection is possible
- default to GUI CSV import guidance
- ask the user to create or choose the Airtable base and send the URL if they want the skill to inspect, repair, or upload the remote table

If the user does not have a base yet, the default path is:

- ask them to create or choose the Airtable base first
- then continue with schema inspection and upload

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

### During repair

- inspect metadata first
- determine whether the issue is access, schema, table lookup, or data quality
- if the issue is data quality, route back upstream

### After publish

- verify record count
- verify a few rows against the working dataset
- only then debug Ptah viewer behavior

## Bundled boundary tools

- [`scripts/inspect_airtable_table.mjs`](../scripts/inspect_airtable_table.mjs)
  - schema and record inspection
- [`scripts/audit_airtable_schema.mjs`](../scripts/audit_airtable_schema.mjs)
  - contract-aware Airtable schema audit
- [`scripts/upsert_airtable_csv.mjs`](../scripts/upsert_airtable_csv.mjs)
  - generic dry-run or execute path for batched CSV upserts
- [`scripts/ptah_airtable_connection.mjs`](../scripts/ptah_airtable_connection.mjs)
  - Ptah Airtable connection test/save helper against `/airtable-admin`

Use these bundled tools by default. Do not go looking for other Airtable helpers elsewhere in the user's workspace unless the user explicitly points you to one.
