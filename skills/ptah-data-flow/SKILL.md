---
name: ptah-data-flow
description: Use when a user needs to turn a rough list, appended seed file, folder of raw data, CSV, HTML export, nested list, markdown, PDF, event-heavy Airtable base, or broken Ptah publish flow into a clean Ptah-ready dataset. Also use for published-state maintenance, website-liveness audits and retirement, compact taxonomy or capability labels, model-backed curation, Ptah Airtable connection setup, gateway or custom-domain deployment, and contrast-safe logo or image attachment repair including Logo.dev identity checks and missing-logo completeness gates. This skill treats Airtable as storage and publish plumbing, not the main editing surface.
---
# ptah-data-flow

Use this skill to onboard, repair, extend, publish, or maintain Ptah data.

## Invariants

- Work locally first. Keep one canonical dataset and derive publish artifacts from it.
- The downstream contract is the current 12 Ptah fields: `Id`, `Category`, `Subcategory`, `Name`, `Website`, `Logo`, `Description`, `Year Founded`, `Email`, `Tech Capabilities`, `Updated At`, and `AI Context`.
- Treat `Id` as an opaque text identifier even when every current value looks numeric.
- Treat Airtable as storage and publish plumbing, not the primary editing model.
- Preserve raw source labels, initial classifications, stable source ids, and final Ptah classifications as distinct data.
- Inspect full-dataset distributions when designing or materially revising a taxonomy. For routine assignments under a stable taxonomy, validate only the changed rows and their category/subcategory pairs.
- Assume Ptah on one computer is the only writer unless the project state or user says otherwise. Do not design routine work around hypothetical concurrency.
- Prefer the smallest safe delta after first publish. For routine narrow maintenance, preserve unrelated fields by omitting them from the payload; a successful Airtable API response is sufficient confirmation.
- Treat source registration types, ownership, and legal status as evidence rather than final taxonomy. Classify by primary organizational function and operating model unless the user defines another axis.
- Keep website health, entity operating status, publication state, and logo health as separate signals.
- Audit placeholder, individual, and non-organization registrations before setting publication controls. Never blanket-publish an event export.
- Store secrets in an ignored working-area `.env`; never print or record secret values.
- Use only the current environment, the active workspace `.env`, or an explicitly named credential source. Never probe unrelated project tokens.
- Continue through obvious unblocked transforms. State plainly whether the result is local, curated, publish-ready, or published.

## First move

1. Read `./ptah-data-flow.state.json` when present. It is the compact current-state handoff.
2. Read `./ptah-data-flow.progress.md` only when state is absent, the user asks for history, or the current decision needs older evidence.
3. Inspect the explicit working area and identify the dataset, source of truth, current stage, remote target, and next bounded transform.
4. Read [references/stages.md](references/stages.md) only when stage routing or exit criteria are unclear.
5. Read only the task-specific references below. Do not preload every reference.

## Reference routing

- Publish contract or canonical shape: [references/contracts.md](references/contracts.md)
- Taxonomy: [references/taxonomy.md](references/taxonomy.md)
- Sparse-source enrichment: [references/enrichment.md](references/enrichment.md)
- Event attendee or affiliation-assisted enrichment: [references/event-affiliation-enrichment.md](references/event-affiliation-enrichment.md)
- Gemini rewrite runners: [references/rewrite-runners.md](references/rewrite-runners.md)
- Credential sourcing or ambiguous secret references: [references/credential-sourcing.md](references/credential-sourcing.md)
- Airtable schema, PAT, table, view, or safe PATCH: [references/airtable-boundary.md](references/airtable-boundary.md)
- Gateway, custom hostname, or deployment: [references/gateway-deployment.md](references/gateway-deployment.md)
- Website correction or retirement: [references/website-liveness.md](references/website-liveness.md)
- Explicit logo or attachment work only: [references/attachment-images.md](references/attachment-images.md)
- State and handoff format: [references/progress-log.md](references/progress-log.md)
- Bundled entrypoints: [references/artifacts.md](references/artifacts.md)
- Prior reusable lessons: [references/field-notes.md](references/field-notes.md)

## Stage routing

- Stage 0: unknown state or ambiguous failure; identify source, boundary, and next transform.
- Stage 1: recover one structured source from rough or heterogeneous input.
- Stage 2: canonicalize, deduplicate, preserve identifiers, diagnose missingness, and assess taxonomy readiness. If grounding is sparse, enrich descriptions or evidence before Stage 3.
- Stage 3: design and assign one defensible taxonomy after inspecting the grounded dataset. Treat an earlier name-only taxonomy as provisional and re-evaluate it after enrichment.
- Stage 4: enrich and curate sparse or inconsistent fields with recorded evidence.
- Stage 5: validate the contract, audit Airtable, publish, and verify the first or otherwise high-risk publication.
- Stage 5b: activate and verify the gateway, deployment, and final hostname.
- Stage 6: repair drift incrementally; route upstream when the defect is actually data quality.

Before a new taxonomy design and before a first or full publication, run `scripts/audit_ptah_dataset.py` or an equivalent deterministic gate. Use `--require-gate taxonomy` before Stage 3 and `--require-gate publication` before a full Stage 5. Do not rerun either whole-dataset gate for a routine narrow Stage 6 edit; validate only the changed ids, fields, and taxonomy pairs.

## Model-backed work

- Treat model calls as an external data boundary. Send only an approved public-field allowlist with explicit context caps.
- Cache by model, prompt version, and a fingerprint of the relevant source fields. An id-only cache key is invalid for mutable rows.
- Record prompt, output, cached token counts, retries, model, stage, and cache hit or miss when the API exposes usage metadata.
- Batch structurally identical requests when validation can still prove every id is returned exactly once.
- Do not repeat derived `AI Context` in taxonomy prompts when a concise description already supplies the same evidence. Include richer context only for sparse rows.
- Do not classify a boundary row from a lossy one-sentence rewrite when primary evidence contains decision-bearing identity or operating-model language. Carry those facts into the taxonomy packet or inspect the source directly.
- Do not award high taxonomy confidence merely because a mapped source type exists. Require agreement between the source type and grounded functional evidence, and make confirmation guards symmetric so explicit function can correct a misleading source type.
- Use deterministic distribution checks for taxonomy design or complete-dataset review; send only changed, low-confidence, boundary, sparse, or oversized-bucket cases to a second model pass.
- Never use a full model pass merely to fill placeholders. Leave blocked fields pending and record the blocker.

## Logo and attachment boundary

- Do not fetch, generate, audit, or alter logos unless the user explicitly requests attachment work.
- For explicit logo work, discover first-party assets before fallbacks. Never invent a mark without approval.
- Validate the current official domain before Logo.dev lookup. Prefer domain lookup with placeholders disabled; quarantine name matches until entity and visual review pass.
- Audit populated and blank rows. Keep a reviewed exception ledger, fail on unexpected blanks, and fail on stale exceptions.
- After any gateway logo loss, reconcile source attachments against durable published assets for every related map; keep intentional source blanks as a separate count.
- Normalize reviewed sources locally to sRGB WebP, preserve aspect ratio, never upscale, default to a 256-pixel ceiling, and keep a content-hashed manifest.
- Verify light/dark and thumbnail visibility. Use a reviewed contrast card only when the official mark needs it.
- Pilot the largest asset, PATCH only the attachment field, stop on the first mismatch, and verify served bytes plus unrelated-field preservation.
- Require durable gateway-local image paths, successful decoding, expected format/dimensions, and one labeled viewer contact sheet covering high-risk identities.

## Airtable and gateway boundary

- Inspect the actual base, table, view, filters, publish controls, and field types once before first publish, when the saved boundary is stale or ambiguous, or when remote behavior is surprising. Reuse that boundary for routine maintenance.
- `Updated At` must be native Airtable `lastModifiedTime`; omit it from row payloads.
- Never use full-record updates for single-field maintenance.
- Preserve existing attachments by omitting `Logo` from general imports and upserts.
- For routine narrow maintenance on a known clean table: validate the changed values locally, update the canonical dataset, PATCH only the stable key and changed fields, accept the successful API response, and stop. Do not add schema preflights, dry runs, remote readbacks, full exports, count checks, state hashes, manifests, snapshots, guard ledgers, rollback CSVs, or browser checks.
- Use comprehensive verification only for first/full publish, large imports or deletes, schema mutation, attachment replacement, publication/view-membership changes, deployment, ambiguous or stale remote state, surprising API behavior, explicit user requests, or another concrete high-risk condition.
- If multiple writers later become a real concern, fetch only the touched rows immediately before writing and compare only the target fields with their previous local values. Patch matches and report conflicts; do not add locks, global diffs, or full-table reconciliation.
- Prefer one consolidated core-data patch, one attachment pass, one gateway refresh, and one final acceptance run when requirements are known together.
- For a comprehensive publish or deployment, verify expected count, unique ids, taxonomy, profiles, publication state, attachments, gateway-local assets, and representative browser rendering as applicable.

## Token-efficient operation

- Prefer one stage orchestrator that writes detailed artifacts to disk and returns a compact JSON summary under 2 KB.
- Keep per-row and per-batch diagnostics in report files. Print milestones every 25-50 records and always print failures immediately.
- Avoid model turns used only to poll a long process. Wait as long as the tool permits and summarize the terminal result once.
- Keep `ptah-data-flow.state.json` under 4 KB. Archive chronology in the progress log without loading it by default.
- Reconcile state at stage milestones, first/full publish, and high-risk operations. Do not rewrite state, counts, or hashes for every routine field edit unless they are the project source of truth for that field.
- Retain final contact sheets and audit reports; keep per-tile previews and transient captures in temporary storage unless evidence retention is required.
- A Codex task uses one configured model. Polling inside that task cannot switch to a cheaper model; use deterministic tools or a separately configured task/automation for detached low-cost monitoring.

## Outputs

- one canonical local dataset
- one publish artifact or successful narrow remote delta
- one compact current-state file when establishing or changing a stage boundary
- one stage verification artifact for first/full publish or high-risk operations
- one gateway acceptance artifact when deployment is in scope
