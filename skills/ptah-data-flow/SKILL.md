---
name: ptah-data-flow
description: Use when a user needs to turn a rough list, folder of raw data, CSV, HTML export, nested list, markdown, PDF, Airtable base, or broken Ptah publish flow into a clean Ptah-ready dataset. This skill treats Airtable as storage and publish plumbing, not the main editing surface.
---
# ptah-data-flow

Use this skill when the user is trying to onboard, repair, extend, or maintain data for Ptah.

The invariant is simple:

- users may enter from any situation
- the current stage may be unclear
- the target stays fixed
- the target is the current 12-field Ptah publish contract

This skill is for running local OODA loops around that workflow. It should help the user figure out where they are, what the next bounded transform is, and what to verify before moving on.

## Operating rules

- Work locally first. Reconstruct or repair one clean working dataset before touching Airtable.
- Treat Airtable as storage and publish plumbing, not the main editing UI.
- Keep one canonical working dataset and derive publish artifacts from it.
- Separate source recovery, canonicalization, taxonomy, curation, and publish. Do not blur them together.
- Do not copy noisy raw taxonomies directly into single-value Ptah fields.
- Do not be myopic. Before deciding on taxonomy, rewrites, or cleanup rules, inspect the whole dataset or the relevant distribution.
- Always do a second look after a meaningful stage output. Do not wait for the user to explicitly ask for review.
- Maintain a local progress log so the workflow can survive interrupted sessions. Read it at the start if it exists, and update it after each meaningful stage output.
- Stay self-contained. Default to the skill bundle, the user's explicit working area, and the workflow artifacts created during the current run. The working area may be a file, a folder, or a small set of clearly named paths. Do not inspect unrelated workspace files, repo precedent, or local pipelines for guidance. Only expand scope if the user explicitly names the file or folder, or asks for integration with existing local code.
- Establish dataset scope before running batch logic. If the working area contains multiple datasets, first identify the active dataset, dataset-specific source of truth, and dataset-specific output paths before adapting or running any script.
- When source recovery depends on live web pages or APIs, make fetches retry-safe. One transient network failure should not collapse the whole run.
- If the source is website-backed and some rows come back sparse or blocked, record those rows explicitly and support a targeted refresh pass later instead of forcing a full rebuild.
- After a network-context change such as VPN, proxy, or auth improvement, prefer a targeted re-fetch of sparse rows before declaring the source permanently weak.
- Do not stop at a local draft if the next bounded transform is obvious and all required inputs, credentials, and tools are already available. Continue autonomously.
- If the next step is blocked by a missing external credential, permission, or target identifier, say that explicitly and ask for it directly instead of acting finished.
- When you stop, state the completion status plainly: local draft, curated local artifact, publish-ready artifact, or published result.
- If the user says only `continue`, `resume`, or `review`, assume they want you to recover context from the current working area and progress log before asking for more detail.

## First move

1. Read [references/contracts.md](references/contracts.md).
2. Read [references/stages.md](references/stages.md).
3. Read [references/progress-log.md](references/progress-log.md).
4. Identify the user's current situation:
   - no dataset yet, only a topic or rough idea
   - raw source data exists, but it is messy or heterogeneous
   - a working dataset exists, but taxonomy or content quality is weak
   - Airtable or Ptah exists, but the boundary is broken or stale
   - the viewer looks wrong, and the root cause is unclear
5. Route the user into the current stage.
6. Read only the extra reference that matches the job:
   - [references/taxonomy.md](references/taxonomy.md) when `Category` or `Subcategory` is in play
   - [references/enrichment.md](references/enrichment.md) when source rows are sparse, core fields are missing, or you need an enrich-then-curate plan
   - [references/exa-websets.md](references/exa-websets.md) when Exa-backed enrichment or discovery is in play
   - [references/rewrite-runners.md](references/rewrite-runners.md) when you need to adapt a Gemini batch rewrite runner into the active dataset working area
   - [references/airtable-boundary.md](references/airtable-boundary.md) when publish, schema, PAT, base, table, view, or connection repair is in play
   - [references/artifacts.md](references/artifacts.md) when you need the allowed working-area model or bundled tool entrypoints
   - [references/prompt-starters.md](references/prompt-starters.md) when the user is vague, resuming interrupted work, or needs a clean continuation prompt shape
7. Do an early credential preflight when the workflow clearly points toward model-backed Stage 4 work:
   - check whether `GEMINI_API_KEY` is already available if curated `Description` or `AI Context` will be needed
   - check whether `EXA_API_KEY` is already available if external enrichment or discovery will likely be needed
   - if `GEMINI_API_KEY` is missing and curated rewrite is clearly on the critical path, ask for it early rather than waiting until after all deterministic local steps
   - if `EXA_API_KEY` is missing, do not block by default; fall back to ordinary web search unless the user explicitly wants Exa

## Progress log

Use the progress log as the shared handoff memory between sessions, users, and agents.

- Default path: `./ptah-data-flow.progress.md`
- If the user already has a preferred path, use that instead.
- Read it before doing new work if it exists.
- Update it after every meaningful stage transition or major decision.
- Keep it short and factual. It is for pickup and continuity, not for long prose.
- Record artifacts and paths, but do not paste large datasets into it.

## Stage workflow

### Stage 0: triage and global view

Use when the user enters from an unknown state or gives an underspecified problem.

- Identify what artifacts exist now: source files, working CSVs, Airtable base, Ptah connection, viewer output.
- State the global lifecycle and place the user into the current stage.
- Decide whether the immediate job is intake, canonicalization, taxonomy, curation, publish, or maintenance.
- If the user already has published artifacts but the root cause is still unclear, always start here before routing into Stage 6.

Output:

- current stage
- current source of truth
- next bounded transform

### Stage 1: intake and source recovery

Use when the input is free-form or only partially structured.

Examples:

- spreadsheet paste
- CSV
- HTML export
- nested list
- markdown or text
- PDF
- topic with no dataset yet

Steps:

- recover or generate one tabular working source
- confirm row counts early
- preserve raw files
- remove exact duplicates before semantic cleanup
- if a source has per-row detail pages, keep the list-page extraction separate from the detail-page enrichment pass
- persist the row identifier or source URL needed to re-fetch a single row later

Second look:

- verify that recovered rows actually represent entities and not artifacts of parsing
- verify counts against user expectation or source pagination
- verify which sparse rows are true source gaps versus fetch failures or blocked pages

### Stage 2: canonicalization and diagnosis

Use when multiple sources or messy schemas need to become one working dataset.

Steps:

- normalize into one canonical entity model
- keep source identifiers and entity kind
- inspect missingness and obvious schema drift
- identify candidate columns for downstream fields without assuming header names are enough

Second look:

- inspect the full header set and sample distributions
- verify that raw columns were not naively pushed into Ptah fields

### Stage 3: taxonomy design and assignment

Use when `Category` or `Subcategory` is unclear, weak, noisy, or user-defined.

Required behavior:

- read [references/taxonomy.md](references/taxonomy.md)
- inspect all plausible candidate columns
- ask for clarification only after inspecting the data
- if the user has a taxonomy idea, evaluate it against the real data and Ptah constraints
- if the user does not know, use the default approach from the taxonomy reference
- if the source taxonomy is multi-tagged, choose one final `Subcategory` per row and retain the raw tag set only in helper columns or context fields
- for mixed speaker-company style datasets, use `Name` for the user-facing display identity the user asked for, and move relationship detail such as affiliation into `Description` or helper columns

Second look:

- inspect final label distribution
- check whether labels are too coarse, too fragmented, too long, or too sparse
- revise once if the result still looks weak

### Stage 4: curation and enrichment

Use when descriptions, AI context, or other optional fields are thin, noisy, inconsistent, or stale.

Steps:

- enrich missing source material when rows are too sparse for good curation
- rewrite display fields for consistency where needed
- keep generated fields rerunnable and reviewable
- if `Description` is being generated deterministically, optimize for concise display copy that avoids repeating data already shown in `Name`
- for website-backed datasets, prefer source URL, profile image, role line, affiliation line, and first strong bio sentence as the deterministic enrichment spine
- check required external credentials before starting model-backed enrich or rewrite work
- if `Description` or `AI Context` has a defined rewrite policy, use it; bundled rewrite runners and templates count as a defined policy
- do not substitute a deterministic fact string or source-note concatenation into final `AI Context` just to fill the column
- if the intended rewrite path is not ready yet, leave the field pending rather than inventing a placeholder just to fill the schema
- if the required key is missing but the intended rewrite path is otherwise clear, stop there, record the blocker, and ask the user for the missing key rather than pretending the draft is final

Second look:

- inspect distribution, not just a couple of examples
- review templating, length consistency, leakage of names or URLs, and overall usefulness

### Stage 5: publish and verify

Use only after the working dataset is clean enough to publish.

Required behavior:

- read [references/airtable-boundary.md](references/airtable-boundary.md)
- validate the 12-field downstream contract
- inspect the actual Airtable schema before assuming types or order
- expect practical schema drift from the nominal 12-field contract; common differences include numeric `Id`, attachment-based `Logo`, extra boolean publish flags, and text fields that are narrower than the ideal local draft
- treat Airtable schema audit as its own blocker check: exact field names, hidden BOM/whitespace pollution, missing required fields, and any truly blocking boundary field types such as `Updated At`
- when a blocker is found and the helper can fix it, use the bundled Airtable schema mutation helper, then inspect again
- treat boundary failures as publish problems, not as reasons to edit the base blindly
- do not stop on non-blocking Airtable cleanup unless the user explicitly asks for schema cleanup
- prefer finishing the intended curation pass before the first Airtable upload unless the user explicitly wants a phased publish
- do not describe a local export as fully Ptah-ready if `Description` or `AI Context` is still blank, raw-source-only, or explicitly pending
- if the user only asks for Airtable as a destination, default to GUI CSV import first
- only switch into Airtable remote-boundary mode when the progress log already contains a remote Airtable target or the user provides an Airtable URL
- if Airtable remote-boundary mode is in scope, ask early for the Airtable PAT
- treat the progress log as the ground truth for whether a remote Airtable or Ptah connection boundary already exists
- if the progress log already contains an Airtable URL, base, table, view, PAT status, Ptah admin origin, or Ptah connection id, continue from that recorded remote state rather than relying only on the user's latest wording
- if the user provides an Airtable URL, treat that as an explicit remote-boundary workflow and ask for the Airtable PAT immediately
- when asking for an Airtable PAT, ask for the full secret token and remind the user to save it at creation time; the later Airtable UI may only show a short token id, which is not enough for API calls
- do not assume the base can be created over API in the normal flow; default to the user creating or choosing their Airtable base first unless they explicitly have an API-supported base-creation path
- if Ptah connection setup is in scope, inspect Airtable first, resolve the real table and view names, test the Ptah connection, and only then save it
- if Airtable URL plus PAT are already available, do not ask the user to explain Airtable ids or manually provide table/view names; resolve them from inspect
- if the target table already contains sample or legacy rows, treat append-versus-replace as an explicit decision unless the user already authorized wiping them

Second look:

- verify field order, field types, and required boundary fields
- verify the resulting publish artifact before blaming Ptah

### Stage 6: maintenance and repair

Use when the user is already post-onboarding and something drifted or broke.

Examples:

- Airtable schema drift
- PAT or access problems
- stale descriptions or AI context
- taxonomy no longer fits
- new rows need merge and dedupe
- viewer complaints need root-cause isolation

Routing rule:

- if the issue is data quality, route back to Stage 2, 3, or 4
- if the issue is boundary setup, route to Stage 5
- if the issue is viewer behavior, verify published data first and only then inspect Ptah constraints
- if maintenance and new intake happen at the same time, first re-establish one trustworthy working dataset, then merge the new intake into that repaired source of truth

## Default field intent

Use these as semantic guides, not rigid formulas:

- `Category`: entity type
  - examples: `Startups & Companies`, `Investors & VCs`
- `Subcategory`: one normalized class under that entity type
  - not a raw multi-tag dump
- `Name`: primary display identity
- `Website`: primary URL for the published row; when the user wants profile-based navigation, this can be a source profile page rather than a company homepage
- `Logo`: public logo URL if available
- `Description`: short display copy for the card surface; do not waste it repeating the exact identity already visible in `Name`
- `Year Founded`: publish-friendly founded date value, shaped to the boundary contract
- `Email`: public contact email
- `Tech Capabilities`: optional capability field if there is a clean and defensible source
- `Updated At`: boundary-managed last modified field, not a freeform date cell
- `AI Context`: richer grounded context for downstream AI use

## Outputs to aim for

- one clean local working dataset
- one publish-ready artifact, unless you are explicitly blocked before publish
- a short note on what changed, what was checked, what status was reached, and what the next loop should be
