---
name: ptah-data-flow
description: Curate, validate, publish, and maintain Ptah datasets from rough sources. Use for Ptah taxonomy, grounded enrichment, Airtable publishing, website retirement, gateway deployment, and explicitly requested logo repair.
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
- Treat temporal fields as high-risk evidence. Distinguish organization founding, exact legal-entity registration, rename or acquisition dates, historical lineage, and source/profile update dates; record which meaning was chosen.
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
- First/full Airtable publication or schema repair: [references/airtable-boundary.md](references/airtable-boundary.md)
- Routine narrow Airtable edits: [references/airtable-maintenance.md](references/airtable-maintenance.md)
- PAT, target resolution, or Ptah test/save: [references/airtable-connection.md](references/airtable-connection.md)
- Gateway, custom hostname, or deployment: [references/gateway-deployment.md](references/gateway-deployment.md)
- Website correction or retirement: [references/website-liveness.md](references/website-liveness.md)
- Explicit logo or attachment work only: [references/attachment-images.md](references/attachment-images.md)
- State and handoff format: [references/progress-log.md](references/progress-log.md)
- Bundled entrypoints: [references/artifacts.md](references/artifacts.md)
- Prior reusable lessons: [references/field-notes.md](references/field-notes.md)
- Skill source/install synchronization, validation, commit, or release: [references/skill-maintenance.md](references/skill-maintenance.md)

## Stage routing

- Stage 0: unknown state or ambiguous failure; identify source, boundary, and next transform.
- Stage 1: recover one structured source from rough or heterogeneous input.
- Stage 2: canonicalize, deduplicate, preserve identifiers, diagnose missingness, and assess taxonomy readiness. If grounding is sparse, enrich descriptions or evidence before Stage 3.
- Stage 3: design and assign one defensible taxonomy after inspecting the grounded dataset. Treat an earlier name-only taxonomy as provisional and re-evaluate it after enrichment.
- Stage 4: enrich and curate sparse or inconsistent fields with recorded evidence.
- Stage 5: validate the contract, audit Airtable, publish, and verify the first or otherwise high-risk publication.
- Stage 5b: activate and verify the gateway, deployment, and final hostname.
- Stage 6: repair drift incrementally; route upstream when the defect is actually data quality.

Before a new taxonomy design and before a first or full publication, run `scripts/audit_ptah_dataset.py` or an equivalent deterministic gate. Use `--require-gate taxonomy` before Stage 3 and `--require-gate publication --taxonomy taxonomy.json` before a full Stage 5. The publication gate requires the complete artifact shape and checks membership in that taxonomy. Description coverage is separate from evidence review; state freshness is informational. Do not rerun either whole-dataset gate for a routine narrow Stage 6 edit; validate only the changed ids, fields, and taxonomy pairs.

## Model-backed work

- Treat model calls as an external data boundary. Send only an approved public-field allowlist with explicit context caps.
- Use the shared rewrite runtime with dataset configuration; see [rewrite runners](references/rewrite-runners.md). Cache by exact id, model, prompt version, and a fingerprint of the relevant source fields.
- Record prompt, output, cached token counts, retries, model, stage, and cache hit or miss when the API exposes usage metadata.
- Batch structurally identical requests when validation can still prove every id is returned exactly once.
- Do not repeat derived `AI Context` in taxonomy prompts when a concise description already supplies the same evidence. Include richer context only for sparse rows.
- Do not classify a boundary row from a lossy one-sentence rewrite when primary evidence contains decision-bearing identity or operating-model language. Carry those facts into the taxonomy packet or inspect the source directly.
- Do not award high taxonomy confidence merely because a mapped source type exists. Require agreement between the source type and grounded functional evidence, and make confirmation guards symmetric so explicit function can correct a misleading source type.
- Do not let model confidence exceed source quality. A confident extraction from a commercial profile remains secondary evidence and must yield to a first-party history or official registry for the same temporal claim.
- Before accepting `Year Founded`, run temporal sanity and contradiction checks. Future years fail; current-year values require explicit review; anniversary-derived years and dates contradicted by stronger evidence remain pending until resolved.
- Use deterministic distribution checks for taxonomy design or complete-dataset review; send only changed, low-confidence, boundary, sparse, or oversized-bucket cases to a second model pass.
- Never use a full model pass merely to fill placeholders. Leave blocked fields pending and record the blocker.

## Logo and attachment boundary

- Enter this workflow only for explicit attachment work. Preserve existing logos by omitting them from general uploads.
- Follow [attachment-images.md](references/attachment-images.md) for first-party discovery, identity review, contrast, completeness, normalization, and verified replacement. Never invent an official mark.
- Reuse reviewed assets only when source identity and transformation policy still match. Refresh remote sources explicitly when their bytes may have changed in place.

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

- Use the bundled entrypoints and keep detailed artifacts on disk; return compact summaries under 2 KB. Add an orchestrator only when the actual dataset needs one.
- Keep per-row and per-batch diagnostics in report files. Print milestones every 25-50 records and always print failures immediately.
- Avoid model turns used only to poll a long process. Wait as long as the tool permits and summarize the terminal result once.
- Keep `ptah-data-flow.state.json` under 4 KB. Archive chronology in the progress log without loading it by default.
- Reconcile state at stage milestones, first/full publish, and high-risk operations. Do not rewrite state, counts, or hashes for every routine field edit unless they are the project source of truth for that field.
- Retain final contact sheets and audit reports; keep per-tile previews and transient captures in temporary storage unless evidence retention is required.
- A Codex task uses one configured model. Polling inside that task cannot switch to a cheaper model; use deterministic tools or a separately configured task/automation for detached low-cost monitoring.

## Skill self-maintenance

- When the user asks to turn a reusable lesson into this skill, update, commit, push, install, or compare Ptah versions, read [references/skill-maintenance.md](references/skill-maintenance.md).
- Treat the version-controlled repository copy as the release source of truth and the Codex-installed copy as a runtime mirror. Fetch and reconcile the repository before editing; after release, refresh the installed copy from the final repository state and require a full-tree parity check.
- Do not perform repository or installation maintenance during ordinary Ptah data work unless the user asks for it. Committing, pushing, or replacing an installed copy still requires the corresponding user authorization.

## Outputs

- one canonical local dataset
- one publish artifact or successful narrow remote delta
- one compact current-state file when establishing or changing a stage boundary
- one stage verification artifact for first/full publish or high-risk operations
- one gateway acceptance artifact when deployment is in scope
