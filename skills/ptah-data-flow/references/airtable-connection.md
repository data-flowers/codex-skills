# Airtable credentials and Ptah connection

Use for credential setup, resolving a target, or testing/saving a Ptah connection.
Read current state first and follow [credential sourcing](credential-sourcing.md).
Reuse the environment or active workspace `.env`; ask for a source only when a
required credential is absent. A saved `pat: present` is a hint, not a secret.

Sharing a base is a separate access change. Use only recipients and permissions
specified by the user for this project, and perform invitations only when the
user requests sharing. This skill has no default collaborator list.

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

If the connection settings changed, save a fresh connection and record the new connection id in current state.

If Ptah connection setup is in scope:

- first inspect the Airtable target so you have the real table name and view name
- build the Ptah payload from `baseId` plus the resolved `tableName` and `view`, not from Airtable table/view ids
- test the Ptah Airtable connection before saving it
- do not ask the user for base name, table name, or view name if those can already be resolved from the Airtable URL plus PAT
- record the Ptah admin origin in current state if known
- record the resolved Airtable base, table, and view names after inspect
- record whether the Airtable connection has already been tested
- record the saved Ptah connection id after a successful save
- after save, call the live provider endpoint and verify expected count, unique ids, taxonomy coverage, one representative mapped row, and native timestamp behavior
- prefer the deterministic helper over ad hoc fetch snippets

## PAT requirements

Use a personal access token from:

- `https://airtable.com/create/tokens`

Grant only scopes needed for the requested operation:

- `data.records:read` for inspection
- `data.records:write` for updates
- `schema.bases:read` for schema inspection
- `schema.bases:write` only for schema mutation

Recommended access:

- grant access to the specific target base or workspace

Important:

- the PAT only works within the permissions of the user who created it
- giving a PAT scopes is not enough; the token must also have access to the target base or workspace
- if the user copied or newly created a base, make sure that base was added to the PAT's resource access
- use the full PAT secret for API calls, not the short token id that Airtable may still show in the developer hub later
- when asking for the PAT, tell the user to save the full secret immediately at creation time
- do not write the PAT value into current state; record only whether it is present or missing

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
- record PAT status as `missing` in current state
