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

- `./ptah-data-flow.state.json`
- `./ptah-data-flow.progress.md`
- optional: `./ptah-data-flow.feedback.md`

Read current state for normal continuations; use the progress log only for history or missing context.

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
- optimized image directory plus source/optimized manifest
- attachment-only Airtable verification report

The exact names can vary. What matters is that the agent treats one of them as the current source of truth and records that in current state.

## Legible artifact layout

Organize substantial runs so a person can identify each artifact's role at a
glance. A useful default is:

```text
source/       recovered source records and raw provenance
canonical/    the active canonical dataset and taxonomy
reports/      coverage, grounding, validation, and acceptance reports
publish/      derived Ptah and Airtable payloads
assets/       decoded and reviewed binary assets
tmp/          transient captures, transfer encodings, and retry fragments
```

Keep the exact structure proportional to the project. Small runs may use fewer
directories while retaining the same conceptual separation.

Prefer readable CSV or JSON for records and provenance, and native binary files
for images or documents. Treat Base64 and compressed transfer parts as temporary
transport representations: decode them into their durable form during intake and
keep any short-lived transfer artifacts under temporary storage. Record the one
active canonical dataset and the latest authoritative report paths in current
state.

### Bundled boundary tools

- [`scripts/ptah_contract.json`](../scripts/ptah_contract.json)
- [`scripts/check_skill.py`](../scripts/check_skill.py)
- [`scripts/audit_ptah_dataset.py`](../scripts/audit_ptah_dataset.py)
- [`scripts/inspect_airtable_table.mjs`](../scripts/inspect_airtable_table.mjs)
- [`scripts/upsert_airtable_csv.mjs`](../scripts/upsert_airtable_csv.mjs)
- [`scripts/optimize_airtable_attachments.py`](../scripts/optimize_airtable_attachments.py)
- [`scripts/build_contrast_logo_card.py`](../scripts/build_contrast_logo_card.py)
- [`scripts/rewrite_ai_context_gemini_batched.py`](../scripts/rewrite_ai_context_gemini_batched.py)

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
