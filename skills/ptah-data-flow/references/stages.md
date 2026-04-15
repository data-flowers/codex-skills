# Stages

## Global lifecycle

The user may enter from any point:

- only a topic
- only raw files
- a messy working CSV
- an existing Airtable base
- a broken Ptah result

The target does not change. Every successful path converges to one publish shape:

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

Airtable is the storage and publish boundary. It is not the main editing model.

## Stage 0: triage and global view

Goal:

- understand what artifacts exist
- identify the current stage
- choose the next bounded transform

Default rule:

- if the user already has Airtable or Ptah but the failure mode is still ambiguous, start in Stage 0 first
- only move into Stage 6 after you know this is truly a maintenance or repair lane

Questions to answer:

- what is the current source of truth
- what is missing
- what is already published
- is the problem upstream data, boundary setup, or viewer behavior
- which later stages are already obviously on the critical path
- whether those later stages will require external credentials such as `GEMINI_API_KEY` or `EXA_API_KEY`

Early preflight rule:

- if Stage 4 curation or Exa-based enrichment is clearly inevitable, check for the needed key early in Stage 0 rather than discovering the blocker only after finishing deterministic local cleanup
- if `EXA_API_KEY` is missing, ordinary web search is the default fallback unless the user explicitly wants Exa or the job clearly depends on Websets-scale enrichment

## Stage 1: intake and source recovery

Goal:

- convert rough input into one workable source dataset

Common entry cases:

- pasted list
- CSV
- spreadsheet export
- HTML export
- nested list
- markdown or text
- PDF
- topic-based generation

Exit criteria:

- one structured source dataset exists
- row count is understood
- exact duplicates from pagination or export problems are handled
- if rows were removed, a duplicate report exists or the progress log records source rows, dedupe keys, kept rows, and reasons

## Stage 2: canonicalization and diagnosis

Goal:

- convert messy or heterogeneous source data into one canonical working dataset

Exit criteria:

- one working dataset exists
- source identifiers are preserved
- entity kind is understood
- obvious missingness and schema problems are known
- any semantic or website/title dedupe is explainable with source row numbers and merge policy

## Stage 3: taxonomy design and assignment

Goal:

- define `Category` and `Subcategory` in a way that fits both the data and the Ptah contract

Exit criteria:

- category model is explicit
- subcategory model is explicit
- label distribution has been reviewed and, if needed, revised
- diagnostics show which entities landed in the largest labels

## Stage 4: curation and enrichment

Goal:

- improve display quality and AI usefulness without losing grounding

Common work:

- enrich missing core source material such as website, summary facts, or other grounding fields
- rewrite descriptions
- rewrite AI context
- enrich optional fields
- add search-derived candidates and re-merge

Important:

- distinguish “field present” from “field truly curated”
- if rows are too sparse to support good rewrite quality, enrich first and curate second
- before model-backed enrichment or rewrite, check whether the required API key or credential is already available in the environment or current run context
- if there is an explicit rewrite policy, prompt, bundled runner, or model-backed enrichment path for `Description` or `AI Context`, use that path
- deterministic source-derived fact strings belong in working notes, helper columns, or draft diagnostics; they are not a substitute for final curated `AI Context`
- if no such path is available yet, leave the field blank or clearly pending rather than fabricating an ad-hoc placeholder just to satisfy the 12-column shape
- if the intended rewrite or enrich path is clear but blocked only by a missing credential, stop there, mark the blocker clearly, and ask for that credential
- missing `EXA_API_KEY` is not a hard blocker by default; fall back to ordinary web search and keep provenance unless the user specifically asked for Exa
- for model-backed `AI Context`, prefer a sample-first loop: run a small batch, inspect the output, validate structure and grounding, then run the full batch
- when enrichment is added after an initial upload, prefer a partial update artifact keyed by stable `Id` instead of re-sending every field

Exit criteria:

- enough grounded source material exists for the curated fields you plan to fill
- curated fields are usable
- output quality has been reviewed at the distribution level

## Stage 5: publish and verify

Goal:

- map the working dataset into the boundary contract and verify the actual publish target

Important:

- a local 12-field export is a valid stopping point when no Airtable base or Ptah connection is in scope
- distinguish the ideal local Ptah export from the upload artifact that fits the inspected Airtable schema
- do not call a dataset fully publish-ready if enrichment-managed fields are still pending
- do not call a dataset fully publish-ready if the export still contains raw-source-only `Description` rows, deterministic placeholder `AI Context`, or other known curation gaps
- default sequencing is to finish the intended curation pass before the first Airtable upload, unless the user explicitly wants a phased publish
- if a curate step is still clearly available and not blocked, keep going rather than stopping at a draft boundary
- after upload, verify both record count and a small field readback for the fields that were intended to change

Exit criteria:

- field order and types are confirmed
- required boundary fields are correct
- the published data is trustworthy enough to check in Ptah

## Stage 6: maintenance and repair

Goal:

- keep an already-published workflow healthy

Examples:

- schema drift
- PAT or access failures
- stale or weak content
- new data needs merge and dedupe
- taxonomy drift
- viewer complaints

Important:

Maintenance is not a separate system. It is the same lifecycle after first publish.

Priority rule:

- if the user also brings new rows or a new export at the same time, first repair or re-establish the current source of truth
- only then merge new intake into that repaired working dataset

## Second-look rule

After Stage 2, Stage 3, Stage 4, and Stage 5, perform a second look before declaring success.

That review should check:

- full-dataset patterns, not just a few rows
- label distributions
- sparsity and multi-tag behavior
- repeated phrasing in generated fields
- boundary mismatches

Do not wait for the user to ask for this review.
