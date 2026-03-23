# Enrichment

Use this reference when the working dataset is too sparse to support good curation.

The missing layer is usually:

1. enrich missing source material
2. then curate display fields from that grounded material

Credential rule:

- this skill does not manage secrets for the user
- it should check whether the required key is already available in the environment or current run context
- if Gemini-backed rewrite is clearly required and `GEMINI_API_KEY` is missing, ask for it early
- if `EXA_API_KEY` is missing, fall back to ordinary web search unless the user explicitly wants Exa or the job clearly needs Websets-style scale

Do not jump straight to rewritten `Description` or `AI Context` if the source rows only have weak inputs such as:

- only `Name`
- only `Name` and `Website`
- blank or shallow descriptions
- no website
- no obvious grounding fields for rewrite

## Order of operations

Default order:

1. recover one canonical working dataset
2. inspect missingness across `Website`, `Description`, `Year Founded`, `Email`, `Logo`, and any other grounding fields
3. enrich the missing source material
4. merge the enrichment results back into the canonical dataset with provenance
5. curate `Description` and `AI Context`
6. review distributions
7. publish only after the intended curation pass is complete

## Exa's role

Exa is an enrichment and discovery layer, not the source of truth by itself.

Use it to:

- recover likely company or investor websites from names
- gather grounding facts for missing or weak descriptions
- collect URLs for later enrichment
- expand the candidate set when the user wants discovery, not just cleanup

Treat Exa output as candidate evidence that must be merged back into the working dataset and reviewed.

If `EXA_API_KEY` is not available:

- use ordinary web search instead of blocking the workflow
- keep the same provenance discipline
- prefer smaller, more targeted lookups instead of pretending you still have Websets-scale async discovery

Read [exa-websets.md](exa-websets.md) when you need the bundled API/workflow reference.

## Preferred Exa mode

For this workflow, the most useful pattern is Websets:

- asynchronous search
- optional verification criteria
- optional enrichments
- polling or webhook completion
- imports when you already know URLs

Practical guidance:

- if you only have names, start with search
- if you already have URLs, prefer imports plus enrichments
- if you need structured discovery for many rows, use async Websets rather than one-off synchronous searching
- if Exa is unavailable, ordinary web search is the default fallback for targeted enrichment

## What to preserve

When you enrich, keep provenance in the working dataset or a sidecar artifact:

- input entity name
- search query or import source
- matched URL
- extracted facts
- evidence URL(s)
- any confidence notes or ambiguity

Do not overwrite the original raw columns without keeping a traceable path back to them.

## Exa API vs vendor skill examples

Prefer the API concepts and request/response model over copying another vendor's skill literally.

External vendor skill examples may still be useful for:

- query variation
- parallel task isolation
- dedupe and merge patterns

But in this skill, they are only design inspiration. The actual workflow should stay grounded in the user's working area and the project's own contracts.

## Rewrite after enrich

Once you have enough grounded source material:

- run the project's `Description` rewrite policy
- run the project's `AI Context` rewrite policy
- keep those passes cacheable, rerunnable, and reviewable
- if those passes need Gemini or another external model API, check for the required key before you start the batch job

If the project already has rewrite scripts, prompts, or templates:

- use them if they fit the current dataset
- otherwise copy and adapt them into the current working area
- bundled rewrite runners and templates inside this skill count as an available rewrite path, not as optional inspiration to ignore
- do not run dataset-specific scripts blindly against a different schema
- before any batch run, verify the script's expected columns, prompt inputs, and output fields against the active dataset
- if multiple datasets share one workspace, keep rewrite scripts, caches, and outputs dataset-scoped rather than reusing one global scratch area

Read [rewrite-runners.md](rewrite-runners.md) when you want bundled Gemini rewrite templates to start from.

## Progress and execution discipline

When model-backed enrichment or rewrite may take time:

- show progress periodically
- keep output paths explicit
- use conservative parallelism that fits the user's machine and API budget
- make the job restartable
- prefer caching and sharding over one giant fragile run
- if the batch cannot start because a required key is missing, say so immediately rather than stopping after only the deterministic local steps
- missing `EXA_API_KEY` alone does not require stopping if ordinary web search can carry the enrich step

## Failure rule

If enrichment still cannot recover enough grounded material:

- leave the field blank or pending
- record the gap in the progress log
- keep any deterministic fact assembly in working notes or helper columns rather than presenting it as final curated `AI Context`
- do not hallucinate a polished final field from almost no evidence
