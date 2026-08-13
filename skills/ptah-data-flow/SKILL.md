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
- Inspect full-dataset distributions before taxonomy, curation, or cleanup decisions and perform a second look after each meaningful stage.
- Prefer the smallest safe delta after first publish. Patch only intended fields and verify unrelated-field preservation.
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
- Stage 5: validate the contract, audit Airtable, publish the intended delta, and verify it.
- Stage 5b: activate and verify the gateway, deployment, and final hostname.
- Stage 6: repair drift incrementally; route upstream when the defect is actually data quality.

Before Stage 3 and Stage 5, run `scripts/audit_ptah_dataset.py` or an equivalent deterministic gate. Use `--require-gate taxonomy` before Stage 3 and `--require-gate publication` before Stage 5. Stage 3 requires enough grounding for defensible classification. Stage 5 requires explicit publication decisions for placeholders and non-organizations, schema-safe upload fields, and a fresh state file.

## Model-backed work

- Treat model calls as an external data boundary. Send only an approved public-field allowlist with explicit context caps.
- Cache by model, prompt version, and a fingerprint of the relevant source fields. An id-only cache key is invalid for mutable rows.
- Record prompt, output, cached token counts, retries, model, stage, and cache hit or miss when the API exposes usage metadata.
- Batch structurally identical requests when validation can still prove every id is returned exactly once.
- Do not repeat derived `AI Context` in taxonomy prompts when a concise description already supplies the same evidence. Include richer context only for sparse rows.
- Use deterministic distribution checks for complete-dataset review; send only low-confidence, boundary, sparse, or oversized-bucket cases to a second model pass.
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

- Inspect the actual base, table, view, filters, publish controls, and field types before writes.
- `Updated At` must be native Airtable `lastModifiedTime`; omit it from row payloads.
- Never use full-record updates for single-field maintenance.
- Preserve existing attachments by omitting `Logo` from general imports and upserts.
- Prefer one consolidated core-data patch, one attachment pass, one gateway refresh, and one final acceptance run when requirements are known together.
- Verify expected count, unique ids, taxonomy, profiles, publication state, attachments, gateway-local assets, and representative browser rendering.

## Token-efficient operation

- Prefer one stage orchestrator that writes detailed artifacts to disk and returns a compact JSON summary under 2 KB.
- Keep per-row and per-batch diagnostics in report files. Print milestones every 25-50 records and always print failures immediately.
- Avoid model turns used only to poll a long process. Wait as long as the tool permits and summarize the terminal result once.
- Keep `ptah-data-flow.state.json` under 4 KB. Archive chronology in the progress log without loading it by default.
- Reconcile state counts, hashes, resolved blockers, and next actions immediately after every verified stage and again before the final response. A stale state file is a failed handoff.
- Retain final contact sheets and audit reports; keep per-tile previews and transient captures in temporary storage unless evidence retention is required.
- A Codex task uses one configured model. Polling inside that task cannot switch to a cheaper model; use deterministic tools or a separately configured task/automation for detached low-cost monitoring.

## Outputs

- one canonical local dataset
- one publish artifact or verified remote delta
- one compact current-state file
- one stage verification artifact
- one gateway acceptance artifact when deployment is in scope
