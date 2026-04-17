# Rewrite runners

Use this reference when the project needs model-backed rewrite passes for fields such as:

- `Description`
- `AI Context`

## Bundled templates

The skill bundles three reusable Python templates:

- [`scripts/gemini_rewrite_common.py`](../scripts/gemini_rewrite_common.py)
- [`scripts/rewrite_descriptions_gemini.py`](../scripts/rewrite_descriptions_gemini.py)
- [`scripts/rewrite_ai_context_gemini.py`](../scripts/rewrite_ai_context_gemini.py)

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
- shard
- parallelize conservatively
- write CSV incrementally

## Before running a copied template

Verify:

- active dataset label and working area are correct
- input and output paths are dataset-scoped
- expected columns match the actual dataset
- prompt/context logic uses the right grounding fields
- cache path is dataset-scoped
- worker count fits the user's machine and API budget
- the API key is discovered without printing the secret value in terminal output

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
6. only then run the full batch
7. write a partial upload artifact keyed by stable `Id` when pushing only the generated field back to Airtable

The bundled templates already support:

- `--workers`
- `--shard-count`
- `--shard-index`
- `--force`
- incremental flushes

That is usually enough. Do not add more machinery unless the dataset really needs it.
