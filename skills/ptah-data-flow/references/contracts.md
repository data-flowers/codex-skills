# Ptah data contract

## Product rules

- The user should be able to go from a rough list or a topic to a clean Ptah-ready dataset.
- Airtable is short-term storage and the compatibility layer. It is not the primary editing UI.
- Ptah viewer is the downstream viewer.
- The workflow should feel like one workbench, not a chain of disconnected tools.
- If the user still has to do the real work in Airtable, the workflow has failed.

## Canonical dataset contract

Minimum stable row fields:

- `id`
- `name`
- `categoryId`
- `subcategories`
- `websiteUrl`
- `logoUrl`
- `description`
- `yearFounded`
- `publicEmail`
- `techCapabilities`
- `updatedAt`
- `aiContext`

The canonical dataset may also carry dynamic enrichment or custom columns, but these fields are the stable spine.

## Downstream Ptah / Airtable fields

The current publish target expects these fields in this order:

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

Rules:

- Treat columns 1-11 as the Ptah-safe core.
- `Updated At` should be an Airtable `Last modified time` field.
- `AI Context` is a normal text field.
- Publish should create or repair the table shape for the user rather than forcing manual Airtable prep.
- A 12-field CSV can be a valid local publish-shaped artifact before Airtable exists, but that does not automatically mean every enrichment-managed field is final.
- If the project already has a defined rewrite policy for `Description` or `AI Context`, use that policy or leave the field pending. Bundled rewrite runners and templates count as a defined policy.
- Do not silently invent a substitute format just to fill the column.
- Deterministic fact concatenation is acceptable in working notes or helper columns, but not as a silent replacement for final `AI Context`.

## Module boundary

The stable split is:

- intake
- canonical dataset
- taxonomy / restructure
- enrichment
- publish to storage and Ptah

The spreadsheet or workbench surface is an adapter boundary. It is not the center of the system.

## Category and subcategory rule of thumb

- `Category` should usually represent entity type in this project, such as `Startups & Companies` or `Investors & VCs`.
- `Subcategory` should usually represent one normalized business or investor class under that entity type.
- Raw source taxonomies may be multi-tagged, sparse, or too broad. Normalize them before publish rather than copying them literally.
- If you widen or rename the category away from the obvious default for the dataset, surface that choice explicitly and record the reason in the progress log.
