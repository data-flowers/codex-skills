# Artifacts

This skill should stay self-contained.

By default, it should only rely on:

- user-provided working area
- the local progress log
- the optional local feedback log
- working outputs created during the current workflow
- bundled skill scripts and references

## Allowed working area

### User inputs

Examples:

- one file path
- one folder path
- a small set of explicitly named files
- pasted spreadsheet
- CSV export
- HTML table export
- nested list
- markdown or text list
- PDF

If the user gives a folder, treat that folder as the working area. Inspect only what is needed inside it to identify source artifacts and establish one current source of truth.

If the folder contains multiple plausible datasets, establish a dataset-scoped working area before doing batch work. Prefer one subdirectory or one explicit file group per dataset.

### Workflow memory

- `./ptah-data-flow.progress.md`
- optional: `./ptah-data-flow.feedback.md`

Use the progress log for normal user work.

Use the feedback log only when:

- the user explicitly wants to improve the skill
- the session is a structured test of skill behavior
- there is a material ambiguity in the skill that should be captured for future improvement

### Working outputs

Examples:

- recovered structured CSV
- canonical working dataset
- publish-ready 12-field export
- dataset-specific builder or rewrite script
- dataset-specific cache files

The exact names can vary. What matters is that the agent treats one of them as the current source of truth and records that in the progress log.

### Bundled boundary tools

- [`scripts/inspect_airtable_table.mjs`](../scripts/inspect_airtable_table.mjs)
- [`scripts/upsert_airtable_csv.mjs`](../scripts/upsert_airtable_csv.mjs)

## Not default behavior

Do not, by default:

- scan unrelated repo files for conventions
- assume there is a shared workspace `scripts/` directory
- borrow schema rules from random local code
- depend on a host repo being structured like the author's repo

Only expand outside this working area if the user explicitly names the file or folder, or asks for integration with existing local code.

## Working-area rule

At the start of a run, establish:

- input working area
- active dataset label or slug
- current source of truth
- progress log path
- feedback log path
- intended output files
- any dataset-scoped scripts or caches that belong to this run

Then stay inside that working area unless the user asks you to expand scope.
