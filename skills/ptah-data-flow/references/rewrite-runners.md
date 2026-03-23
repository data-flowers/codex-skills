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

Adapt:

- prompt wording
- section structure if the project uses a different contract
- link columns
- context columns

## Default execution pattern

For most datasets:

1. copy the runner into the dataset working area
2. adapt prompt/context and column mapping
3. run a small sample first
4. inspect distribution quality
5. only then run the full batch

The bundled templates already support:

- `--workers`
- `--shard-count`
- `--shard-index`
- `--force`
- incremental flushes

That is usually enough. Do not add more machinery unless the dataset really needs it.
