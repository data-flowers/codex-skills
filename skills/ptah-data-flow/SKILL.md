---
name: ptah-data-flow
description: Use when a user needs to turn a rough list, appended seed file, folder of raw data, CSV, HTML export, nested list, markdown, PDF, event-heavy Airtable base, or broken Ptah publish flow into a clean Ptah-ready dataset. Also use for published-state maintenance, compact taxonomy or capability labels, model-backed curation, Ptah Airtable connection setup, gateway or custom-domain deployment, and contrast-safe logo or image attachment repair. This skill treats Airtable as storage and publish plumbing, not the main editing surface.
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
- When reclassifying a source taxonomy, keep three distinct layers: initial classification copied from the source signal, final re-evaluated Ptah classification, and untouched original source labels. Preserve originals in helper fields or context without allowing them to overwrite the final assignment.
- Do not be myopic. Before deciding on taxonomy, rewrites, or cleanup rules, inspect the whole dataset or the relevant distribution.
- Always do a second look after a meaningful stage output. Do not wait for the user to explicitly ask for review.
- Maintain a local progress log so the workflow can survive interrupted sessions. Read it at the start if it exists, and update it after each meaningful stage output.
- When the workflow needs tokens or API keys, store them in a local `.env` file under the working area when possible, and make sure that file is excluded from git. Do not keep retyping secrets inline in commands if a local `.env` can carry them.
- When the user refers to an already-shared Airtable PAT, Gemini key, or another local project/key source, find that key in the named local source and copy only the required environment variable(s) into the current working area's `.env`. Do this instead of asking the user to paste the secret again. Never print the secret, paste it into the progress log, or leave it only in an inline shell command.
- Stay self-contained. Default to the skill bundle, the user's explicit working area, and the workflow artifacts created during the current run. The working area may be a file, a folder, or a small set of clearly named paths. Do not inspect unrelated workspace files, repo precedent, or local pipelines for guidance. Only expand scope if the user explicitly names the file or folder, or asks for integration with existing local code.
- Establish dataset scope before running batch logic. If the working area contains multiple datasets, first identify the active dataset, dataset-specific source of truth, and dataset-specific output paths before adapting or running any script.
- When source recovery depends on live web pages or APIs, make fetches retry-safe. One transient network failure should not collapse the whole run.
- If the source is website-backed and some rows come back sparse or blocked, record those rows explicitly and support a targeted refresh pass later instead of forcing a full rebuild.
- After a network-context change such as VPN, proxy, or auth improvement, prefer a targeted re-fetch of sparse rows before declaring the source permanently weak.
- For post-publish maintenance, prefer the smallest safe delta: detect missing, malformed, or stale rows; generate only those rows; patch only the intended field(s); then re-export and verify the remote result.
- Do not pull logos by default. Unless the user explicitly asks for logos or image attachments, do not research, fetch, download, generate, convert, optimize, upload, replace, remove, or completeness-audit them. Leave new `Logo` values blank and preserve existing Airtable attachments by omitting `Logo` from imports and PATCH payloads. A `Logo` field in the source or target schema does not count as an instruction to populate it.
- Only for explicitly requested attachment work, use the fast path in `references/airtable-boundary.md`: find the live record id, choose the official stable image URL, compact oversized assets first, PATCH only `Logo`, and verify metadata plus the Airtable-served image or thumbnail.
- Before creating any logo fallback, exhaust first-party asset discovery: inspect HTML icon links, web manifests, metadata, CSS/JS references, official asset directories, and reasonable same-origin sibling filenames and formats. Fetch and visually compare all plausible candidates; a tiny root favicon is not proof that no better official asset exists. Prefer a verified official asset, otherwise leave `Logo` blank. Never invent or publish a text wordmark or generic mark without explicit user approval.
- When image attachment work is explicitly requested and source images may be large or a recurring refresh is needed, read `references/attachment-images.md` and adapt or run `scripts/optimize_airtable_attachments.py`. Default to a 256-pixel maximum dimension, use 128 pixels for simple small-card icons when sufficient, and treat 512 pixels as a ceiling reserved for verified high-density or detailed-logo needs. Preserve aspect ratio, never upscale raster sources, convert to WebP, strip metadata, keep a local manifest, replace upload-first, and run preservation checks.
- Treat direct SVG and ICO attachments as unsupported. Download and convert them locally before any Airtable upload or URL-based attachment PATCH: rasterize SVG at twice the intended final dimension with a 1024-pixel intermediate cap, select the smallest ICO frame that meets the final target or otherwise its largest frame, and publish the resulting validated PNG or WebP instead of the original source URL. The bundled attachment optimizer performs this normalization to WebP during its prepare phase.
- Treat logo visibility as part of attachment validity, not a cosmetic afterthought. Detect transparent or near-white marks, preview every candidate at full and 36-pixel thumbnail sizes on both white and black surfaces, and composite white/translucent marks onto an official brand or site-theme background before publishing. When either card edge can disappear, use `scripts/build_contrast_logo_card.py` to add dual white/black keylines. Require a fully opaque final asset and verify the Airtable-served bytes and thumbnails—not only the local source and attachment metadata.
- Treat model-backed curation as an external data boundary. Require an explicitly requested or approved model pass, record the approved field allowlist and context-length cap, send only those minimum public-facing fields, and exclude internal provenance, confidence notes, private contact data, and unrelated columns by default.
- Never use a full-record Airtable update for a single-field maintenance job. Use record-scoped PATCH payloads that include only the field being changed, so attachment fields such as `Logo` are preserved.
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
   - [references/gateway-deployment.md](references/gateway-deployment.md) when Ptah connection activation, a gateway repository, Cloudflare Pages, a custom hostname, DNS, or production deployment is in play
   - [references/attachment-images.md](references/attachment-images.md) only when the user explicitly asks for logos or image attachments to be fetched, compacted, refreshed, or synchronized to Airtable
   - [references/artifacts.md](references/artifacts.md) when you need the allowed working-area model or bundled tool entrypoints
   - [references/field-notes.md](references/field-notes.md) when a prior project surfaces reusable workflow mistakes, source-of-truth changes, taxonomy redundancy, or Airtable update behavior
   - [references/prompt-starters.md](references/prompt-starters.md) when the user is vague, resuming interrupted work, or needs a clean continuation prompt shape
7. Do an early credential preflight when the workflow clearly points toward model-backed Stage 4 work:
   - check whether `GEMINI_API_KEY` is already available if curated `Description` or `AI Context` will be needed
   - check whether `EXA_API_KEY` is already available if external enrichment or discovery will likely be needed
   - if `GEMINI_API_KEY` is missing and curated rewrite is clearly on the critical path, first check whether the user referenced an existing local key source and copy it into the current working area's `.env`; ask only if no referenced/local key can be found
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
- if the user names a source field as the initial category signal, copy it into explicit initial-classification helper fields before re-evaluation; never reinterpret the source field in place
- preserve the original source classification separately from the final `Category` and `Subcategory`, and verify that preservation after publish
- when balancing taxonomy, make `Subcategory` add detail within `Category` rather than repeating it; prefer 2-9 subcategories per category and avoid final buckets with 5 or fewer rows unless the user explicitly wants rare classes preserved
- for mixed speaker-company style datasets, use `Name` for the user-facing display identity the user asked for, and move relationship detail such as affiliation into `Description` or helper columns
- for startup datasets, prefer market verticals or industries for `Subcategory`; do not fall back to alphabetical navigation buckets unless the user explicitly wants navigational groupings instead of semantic taxonomy

Second look:

- inspect final label distribution
- check whether labels are too coarse, too fragmented, too long, or too sparse
- check whether labels fit the real viewer without truncation; prefer compact display labels around 17 characters or fewer when the surface is narrow, while keeping semantic meaning stable
- check whether subcategory names merely restate category names
- revise once if the result still looks weak

### Stage 4: curation and enrichment

Use when descriptions, AI context, or other optional fields are thin, noisy, inconsistent, or stale.

Steps:

- enrich missing source material when rows are too sparse for good curation
- classify enrichment evidence per row as direct-source, supported fallback, or deliberately limited; summarize coverage and never present limited rows as fully researched
- rewrite display fields for consistency where needed
- keep generated fields rerunnable and reviewable
- if `Description` is being generated deterministically, optimize for concise display copy that avoids repeating data already shown in `Name`
- for website-backed datasets, prefer source URL, role line, affiliation line, and first strong bio sentence as the deterministic enrichment spine; do not fetch profile images unless explicitly requested
- check required external credentials before starting model-backed enrich or rewrite work
- for Gemini-backed batches, run a small sample first, then use a quota-safe full-run cadence: prefer `--workers 5` for normal paid Gemini accounts, but fall back to `--workers 1`, `--request-delay-seconds 4.5` or slower if the account is unknown, free-tier, downgraded, newly throttled, or returns 429/quota errors; keep cache enabled and avoid `--force` unless intentionally regenerating
- if `Description` or `AI Context` has a defined rewrite policy, use it; bundled rewrite runners and templates count as a defined policy
- when `Tech Capabilities` must fit a compact card, default to exactly three semicolon-delimited, high-signal labels per row and keep each label around 16 characters or fewer; preserve capability meaning rather than retaining every implementation detail
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
- inspect the destination view's filters and every publish-control or grouping field that determines whether records appear downstream; do not verify only the 12-field core
- expect practical schema drift from the nominal 12-field contract; common differences include numeric `Id`, attachment-based `Logo`, extra boolean publish flags, and text fields that are narrower than the ideal local draft
- treat Airtable schema audit as its own blocker check: exact field names, hidden BOM/whitespace pollution, missing required fields, and required boundary field types
- treat `Updated At` as a hard requirement: it must be an Airtable `lastModifiedTime` field before the boundary is considered clean
- when creating a new table, provision and verify `Updated At` as a native Airtable `Last modified time` field before importing any rows; CSV import cannot preserve or create computed Airtable field types
- exclude `Updated At` from every Airtable row-import or upsert artifact and let Airtable populate it; never accept `dateTime`, imported timestamps, or a same-named date field as a fallback
- when a blocker is found and the helper can fix it, use the bundled Airtable schema mutation helper, then inspect again
- treat boundary failures as publish problems, not as reasons to edit the base blindly
- do not stop on non-blocking Airtable cleanup unless the user explicitly asks for schema cleanup, but do stop on any `Updated At` mismatch until it is repaired or explicitly escalated as a manual blocker
- prefer finishing the intended curation pass before the first Airtable upload unless the user explicitly wants a phased publish
- do not describe a local export as fully Ptah-ready if `Description` or `AI Context` is still blank, raw-source-only, or explicitly pending
- if the user only asks for Airtable as a destination, default to GUI CSV import first
- only switch into Airtable remote-boundary mode when the progress log already contains a remote Airtable target or the user provides an Airtable URL
- if Airtable remote-boundary mode is in scope, ask early for the Airtable PAT
- once a PAT or other API secret is provided, move it into a local `.env` file in the working area when practical, prefer environment-backed scripts over inline secret-bearing commands, and keep the progress log at `present` or `missing` rather than pasting the secret value
- treat the progress log as the ground truth for whether a remote Airtable or Ptah connection boundary already exists
- if the progress log already contains an Airtable URL, base, table, view, PAT status, Ptah admin origin, or Ptah connection id, continue from that recorded remote state rather than relying only on the user's latest wording
- if the user provides an Airtable URL, treat that as an explicit remote-boundary workflow and ask for the Airtable PAT immediately
- when asking for an Airtable PAT, ask for the full secret token and remind the user to save it at creation time; the later Airtable UI may only show a short token id, which is not enough for API calls
- do not assume the base can be created over API in the normal flow; default to the user creating or choosing their Airtable base first unless they explicitly have an API-supported base-creation path
- if Ptah connection setup is in scope, inspect Airtable first, resolve the real table and view names, test the Ptah connection, and only then save it
- after saving a Ptah connection, read the live provider endpoint and verify expected count, unique ids, taxonomy coverage, a representative mapped row, and the configured native timestamp behavior
- if Airtable URL plus PAT are already available, do not ask the user to explain Airtable ids or manually provide table/view names; resolve them from inspect
- if the target table already contains sample or legacy rows, treat append-versus-replace as an explicit decision unless the user already authorized wiping them
- if the source table is polluted with event or unrelated custom fields and the user wants a clean company/entity map, prefer a clean sibling table containing the 12-field contract plus explicitly retained control fields such as `Published`; leave the source table untouched unless deletion was explicitly requested
- for a clean sibling table, duplicate a correctly typed structure when possible; otherwise create `Updated At` in the Airtable UI as `Last modified time`, audit the empty table, then import the upload artifact and audit again
- when `Published` exists or the user requests a publish state, treat it as an explicit control field outside the 12-field contract, set it deliberately, and verify it after every relevant update
- leave new `Logo` values blank and omit `Logo` from Airtable row imports and upserts unless the user explicitly requested logo population; preserve any existing attachments without treating blank logos as a publish blocker

Second look:

- verify field order, field types, and required boundary fields
- verify the resulting publish artifact before blaming Ptah

### Stage 5b: connect, deploy, and verify the gateway

Use when the user asks to activate a Ptah connection on a gateway, custom hostname, or production viewer.

Required behavior:

- read [references/gateway-deployment.md](references/gateway-deployment.md)
- identify the actual runtime and deployment surface before assuming the gateway is an SSH host
- keep the map configuration in the canonical gateway source repository; an isolated deployment snapshot is not durable source of truth by itself
- inspect repository dirtiness and deployment scripts before production writes, and identify unrelated changes or companion services in the release scope
- require explicit approval if the deployable snapshot contains unrelated changes beyond the requested map
- verify both the immutable deployment URL and the final custom hostname; the custom-domain manifest must route the hostname to the intended map before declaring success
- save a compact deployment-verification artifact and update the progress log with connection, domain, deployment, and live acceptance state

Second look:

- confirm the custom hostname returns the intended manifest and config after propagation
- confirm the provider endpoint returns the expected unique records and taxonomy
- confirm the canonical repository contains the deployed configuration so a later release cannot remove it silently

### Stage 6: maintenance and repair

Use when the user is already post-onboarding and something drifted or broke.

Examples:

- Airtable schema drift
- PAT or access problems
- stale descriptions or AI context
- taxonomy no longer fits
- new rows need merge and dedupe
- a newly added Airtable row needs `Description` or `AI Context`
- viewer complaints need root-cause isolation

Incremental maintenance rule:

- if the user says a new row was added or one field needs refreshing, do not regenerate the whole dataset by default
- if a seed file gained entries, diff the raw seeds against preserved source aliases, canonicalize only the additions, dedupe them against existing entities, assign stable new ids, and publish only the resulting delta before running a full-count verification
- re-export the current remote target first
- identify target rows by record id, missing target field, stale hash, or explicit user-named entity
- generate only those rows, using existing caches where source fields did not change
- patch only the target field, never untouched fields such as `Logo`
- do not research or backfill logos for new or existing rows unless the user explicitly requested logo work
- for logo-only work, prefer a direct record-scoped attachment PATCH over regenerating or re-uploading a CSV
- never PATCH an SVG or ICO source URL into `Logo`; normalize it to a reviewed raster asset first and attach the converted bytes
- for logo-only work, reject white-on-transparent and otherwise low-contrast candidates unless the downstream card background is known to make them visible; preserve the official mark by placing it on a verified brand/site-theme color, and leave the field blank rather than inventing a wordmark unless the user explicitly approves a non-official fallback
- when a logo must survive both pure-white and pure-black surfaces, add dual opposite-color keylines around the opaque brand card and verify both the Airtable-served full file and the smallest available thumbnail before calling it fixed
- for a batch of logo or image replacements, create a local optimized-asset manifest first, pilot the largest source, then use the bundled attachment helper or an adapted dataset-scoped copy
- omit attachment fields from general-purpose Airtable upload artifacts after attachment optimization, unless that upload intentionally owns those attachments
- re-export after patching and verify both content quality and preservation of unrelated fields for the touched rows

Routing rule:

- if the issue is data quality, route back to Stage 2, 3, or 4
- if the issue is boundary setup, route to Stage 5
- if the issue is viewer behavior, verify published data first and only then inspect Ptah constraints
- if maintenance and new intake happen at the same time, first re-establish one trustworthy working dataset, then merge the new intake into that repaired source of truth

## Default field intent

Use these as semantic guides, not rigid formulas:

- `Category`: entity type
  - examples: `Companies`, `Investors`, `Open Source`
- `Subcategory`: one normalized class under that entity type
  - not a raw multi-tag dump
  - for startups, usually a defensible market vertical or industry
- `Name`: primary display identity
- `Website`: primary URL for the published row; when the user wants profile-based navigation, this can be a source profile page rather than a company homepage
- `Logo`: optional; leave blank for new rows and preserve existing attachments unless the user explicitly requests logo work
- `Description`: short display copy for the card surface; do not waste it repeating the exact identity already visible in `Name`
- `Year Founded`: publish-friendly founded date value, shaped to the boundary contract
- `Email`: public contact email
- `Tech Capabilities`: concise, defensible capability labels; for compact cards, prefer exactly three semicolon-delimited labels around 16 characters or fewer each
- `Updated At`: boundary-managed last modified field, not a freeform date cell
- `AI Context`: richer grounded context for downstream AI use

## Outputs to aim for

- one clean local working dataset
- one publish-ready artifact, unless you are explicitly blocked before publish
- one gateway deployment-verification artifact when connection activation or a custom hostname is in scope
- a short note on what changed, what was checked, what status was reached, and what the next loop should be
