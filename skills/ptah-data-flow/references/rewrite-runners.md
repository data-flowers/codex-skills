# Rewrite runners

Use this reference when the project needs model-backed rewrite passes for fields such as:

- `Description`
- `AI Context`

## Contents

- [Bundled templates](#bundled-templates)
- [Why copy and adapt](#why-copy-and-adapt)
- [Before running a copied template](#before-running-a-copied-template)
- [External transmission boundary](#external-transmission-boundary)
- [Gemini rate discipline](#gemini-rate-discipline)
- [Description runner](#description-runner)
- [AI Context runner](#ai-context-runner)
- [Default execution pattern](#default-execution-pattern)
- [Incremental maintenance pattern](#incremental-maintenance-pattern)

## Bundled templates

The skill bundles four reusable Python templates:

- [`scripts/gemini_rewrite_common.py`](../scripts/gemini_rewrite_common.py)
- [`scripts/rewrite_descriptions_gemini.py`](../scripts/rewrite_descriptions_gemini.py)
- [`scripts/rewrite_ai_context_gemini.py`](../scripts/rewrite_ai_context_gemini.py)
- [`scripts/rewrite_ai_context_gemini_batched.py`](../scripts/rewrite_ai_context_gemini_batched.py)

They are not meant to be blindly run against arbitrary datasets.

They are meant to be:

1. copied into the active dataset working area
2. adapted to the dataset's columns, prompts, and grounding sources
3. then run there with dataset-scoped outputs and caches

## Why copy and adapt

The rewrite shape is repeatable, but the actual dataset is not.

Different datasets may vary on:

- which columns exist
- whether `Id` exists yet
- whether the input already has usable descriptions
- whether there are separate raw source files to use as grounding
- what style rules the project wants

So the reusable part is the runner pattern:

- load CSV
- build prompt context
- call Gemini
- validate output
- cache
- fingerprint cache entries from model, prompt version, and transmitted fields
- record API usage metadata when available
- shard
- rate-limit conservatively
- write CSV incrementally

## Before running a copied template

Verify:

- active dataset label and working area are correct
- input and output paths are dataset-scoped
- expected columns match the actual dataset
- prompt/context logic uses the right grounding fields
- cache path is dataset-scoped
- worker count and request delay fit the Gemini quota before the full run
- the API key is discovered without printing the secret value in terminal output

## External transmission boundary

Treat every model request as transmission to an external service.

- Run only when the user explicitly requests or approves the model-backed pass.
- Require an explicit `--context-columns` selection; never default to every CSV
  column merely because it is available.
- Prefer public-facing prompt fields such as `Name`, `Category`, `Subcategory`,
  `Website`, `Description`, `Year Founded`, and `Tech Capabilities`.
- Exclude internal seed aliases, confidence notes, review comments, private
  contact data, raw evidence collections, credentials, and unrelated helper
  columns unless they are essential and separately authorized.
- Keep allowed links equally narrow; the public website is usually enough for a
  grounded rewrite when the working row already contains curated facts.
- If execution is blocked because the payload is too broad, reduce it to the
  minimum necessary fields. Do not route the same sensitive payload through a
  different command or service.

## Gemini rate discipline

Do not hammer Gemini and then recover from 429s. Design the batch to succeed on the first full run.

Default posture:

- Run a tiny sample first, usually 3-5 rows.
- For normal paid Gemini accounts, prefer running the full batch with `--workers 5` after the sample passes. Use a request delay that keeps the combined request rate inside the account's quota. Requests per minute roughly equals `workers * 60 / request_delay_seconds`.
- If the account may be downgraded, free-tier, newly throttled, or shows 429/quota errors, fall back to `--workers 1` and `--request-delay-seconds 4.5` or slower, then resume from cache.
- Remember the user has seen Gemini jobs get throttled when the account was downgraded; do not treat that as evidence that five workers is inherently unsafe on a healthy account.
- Keep caching on by default. Do not use `--force` unless intentionally regenerating.
- Reject an existing cache entry when its source fingerprint does not match the current transmitted fields, model, and prompt policy.
- Flush every 10-20 rows so an interruption preserves useful output.
- Treat a 429 as a configuration failure: lower workers, increase delay, and resume from cache. Do not repeatedly restart at the same rate.
- If sharding across processes, include all shards in the same rate budget. Shards are not a quota bypass.

## Description runner

The description template is designed for:

- one-sentence outputs
- word-count guardrails
- entity-name leakage checks
- URL rejection
- bounded retry with validation feedback

Adapt:

- prompt wording
- context columns
- entity-specific style rules

## AI Context runner

The AI Context template is designed for:

- structured markdown
- heading-order checks

Prefer the batched runner when every row uses the same policy and each result can
be validated by stable id. It defaults to eight entities per request, keeps
per-row cache files, and records one usage event per API call. Use the single-row
runner for unusually large contexts, row-specific policies, or failure isolation.
- URL-free body
- allowed-source-link restriction
- bounded retry with validation feedback

Default AI Context prompt contract:

```text
I need max 200 word summary about the following company:

{company} {url} {description}

sections: what; why; who; for whom; in relation to; what's nice great and superb.
summary needs to be extra compact, dense with info. every extra token hurts.
output simple structured markdown without the source notes. ready for copy paste.
add links to sources at the bottom of the answer, out of the markdown doc.
```

Output rules:

- `AI Context` stores only the simple structured markdown body.
- Do not include links inside `AI Context`.
- Do not include source notes inside `AI Context`.
- Do not repeat information already available in `Name`, `Website`, `Description`, or other explicit fields unless needed for coherence.
- Treat 200 words as a soft ceiling based on economy, not a hard validation rule; prefer much shorter when the source material supports it.
- If source links are produced during review, keep them outside the markdown body and do not publish them into `AI Context`.

Adapt:

- prompt wording
- section structure if the project uses a different contract
- link columns
- context columns

For directory datasets, prefer a compact, grounded prompt with stable headings and explicit caveats. Useful validation checks include:

- every row has a non-empty target field
- headings match the expected order
- body text does not contain raw URLs
- source links, if included, are drawn only from allowed source columns
- generated bodies stay under the chosen word limit

## Default execution pattern

For most datasets:

1. copy the runner into the dataset working area
2. adapt prompt/context and column mapping
3. run a small sample first
4. inspect distribution quality
5. validate fill rate, heading order, URL leakage, source links, and word counts
6. set a quota-safe full-run cadence
7. only then run the full batch
8. write a partial upload artifact keyed by stable `Id` when pushing only the generated field back to Airtable
9. if the user also requested publication, include `Published` only as an explicit boolean control field and verify both the generated field and publish state remotely

The bundled templates already support:

- `--workers`
- `--request-delay-seconds`
- `--shard-count`
- `--shard-index`
- `--force`
- incremental flushes

That is usually enough. Do not add more machinery unless the dataset really needs it.

## Incremental maintenance pattern

For post-publish maintenance, adapt the runner to support a narrow target set instead of rerunning the full dataset.

Useful switches or equivalent local behavior:

- `--missing-only`: process only rows where the target field is blank
- `--record-id rec...`: process one Airtable record id
- `--name "Entity"`: process a user-named entity after confirming the match is unique
- `--category Companies`: scope broad maintenance to one entity class
- `--request-delay N`: respect free-tier model rate limits
- no `--force` by default: reuse cached output unless source fields changed

Cache key guidance:

- include the row id and a hash of source fields used by the prompt
- include source fields such as `Name`, `Website`, `Category`, `Subcategory`, `Description`, `Year Founded`, `Tech Capabilities`, `city`, `focus`, and any current target field used as context
- do not include volatile Airtable attachment URLs or `Updated At` in the rewrite cache key unless the prompt actually depends on them

After generation:

- validate the same constraints used for full batch runs
- write a local output CSV containing all rows so unchanged rows stay available for review
- upload only the selected record ids and only the target field being refreshed
- re-export the remote target and validate the remote values, not just the local output
