# Exa Websets

Use this reference when Exa is the preferred enrichment or discovery layer.

This is the relevant bundle point for the skill. It is a concise API/workflow reference, not a separate Exa skill.

If `EXA_API_KEY` is not available, fall back to ordinary web search by default rather than blocking the workflow.

## Core model

Base URL:

- `https://api.exa.ai/websets/v0`

Auth:

- send `x-api-key: $EXA_API_KEY`

Websets is asynchronous:

1. create a webset
2. let Exa search and verify results
3. optionally run enrichments
4. wait until the webset is idle
5. list items and merge them back into the working dataset

## Best-fit uses in this workflow

Use Websets to:

- recover websites from names
- gather grounding facts for sparse rows
- search for candidate companies or investors
- enrich known URLs with additional structured fields

If Exa is unavailable:

- use normal web search for targeted lookups
- keep provenance the same way you would for Exa results
- reserve Exa-specific logic for cases where Websets scale or async enrichment is genuinely useful

## Search vs import

If you only have names:

- start with search

If you already have URLs:

- prefer imports plus enrichments

If you need many results and structured follow-up:

- prefer async Websets over lots of ad-hoc one-off searches

## Minimal Python shape

```python
from exa_py import Exa
from exa_py.websets.types import CreateWebsetParameters, CreateEnrichmentParameters
import os

exa = Exa(os.getenv("EXA_API_KEY"))

webset = exa.websets.create(
    params=CreateWebsetParameters(
        search={"query": "early-stage AI investors", "count": 25},
        enrichments=[
            CreateEnrichmentParameters(
                description="Find official website",
                format="text",
            ),
        ],
    )
)

webset = exa.websets.wait_until_idle(webset.id)
items = exa.websets.items.list(webset_id=webset.id)
```

## What to preserve when merging

Keep provenance:

- input entity name
- query or import source
- matched URL
- extracted facts
- evidence URLs
- ambiguity or confidence notes

Do not replace raw source values without leaving a traceable path back to them.

## Why there is no default generic enrich runner

This skill does not bundle one generic Exa runner by default.

Reason:

- search criteria vary by dataset
- enrichment fields vary by dataset
- merge logic varies by dataset
- dedupe and confidence rules vary by dataset

Websets itself is already asynchronous, so a separate generic multiprocessing wrapper is usually not the bottleneck.

The better default is:

1. read this reference
2. write or adapt a dataset-scoped enrichment script in the active working area
3. merge results into the canonical dataset with provenance
4. only then run curation

If `EXA_API_KEY` is missing, replace step 2 with targeted ordinary web search rather than treating the run as blocked.

When writing that enrichment script, you may borrow the runner shape from the bundled Gemini rewrite templates:

- dataset-scoped paths
- cache files
- shard support
- incremental output writes
- conservative worker counts

Reuse the execution pattern, not the dataset-specific prompt or merge logic.

## Parallelism guidance

Do not add concurrency just because you can.

Prefer:

- one dataset-scoped script
- explicit output paths
- restartable runs
- polling or batched follow-up over many overlapping fragile processes

If the dataset is large, parallelize only where it is clearly safe and where the API budget supports it.
