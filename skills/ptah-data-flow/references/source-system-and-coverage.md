# Source system, identity, and coverage

Use this reference for directories, event sites, catalogues, paginated listings,
and other sources where a collection surface points to entity profiles.

## Principle: understand the source as a system

Model the source before scaling extraction:

- collection surfaces enumerate the population
- stable source identifiers anchor entities
- entity surfaces provide profile evidence
- relationships connect entities to halls, lists, groups, or editions
- the destination defines the publication boundary

Trace one representative entity through these layers. Inspect links, embedded
structured data, page source, and network-backed endpoints to identify the most
reliable enumeration and profile-access pattern. Prefer deterministic entity
requests from stable identifiers; use interactive browsing for discovery,
authenticated access, or fields that genuinely require rendering.

## Principle: establish an identity spine

Preserve identity before enrichment. When the source exposes these values, keep:

- canonical `id`
- stable `sourceId`
- raw source name and canonical name
- direct `sourceProfileUrl`
- collection memberships and placement
- aliases, normalized-name matches, and reviewed identity corrections

Treat names as attributes. Join and refresh through stable identifiers. Record
the reconciliation basis for any row that needs more than an exact identifier
match.

## Principle: make scope countable

Define the population once and express completeness against it. Keep a source
manifest beside the canonical dataset:

```json
{
  "version": 1,
  "dataset": "example-directory",
  "scopeRule": "Entities linked from the selected collections",
  "population": {
    "discovered": 365,
    "inScope": 361,
    "excluded": 4
  },
  "crawl": {
    "target": "discovered",
    "attempted": 365,
    "recovered": 365,
    "failedSourceIds": []
  },
  "identity": {
    "stableSourceIdsAvailable": true,
    "profileUrlsAvailable": true
  }
}
```

`discovered` equals `inScope + excluded`. The crawl target is either the full
discovered population or the in-scope population. `recovered + failures` equals
`attempted`. The canonical row count equals `inScope`.

Use precise coverage statements such as `361/361 in-scope entities recovered`.
Keep excluded and failed identifiers explicit so a future refresh can reproduce
the same boundary.

## Principle: build the evidence layer before interpretation

Assemble one evidence packet per entity from the strongest available material:

1. official source profile and structured source fields
2. source product, service, or organization tags
3. first-party website content
4. supported fallback evidence
5. clearly labeled identity-only inference

Track a compact `evidenceBasis` such as `profile+tags`, `tags-only`,
`first-party-website`, or `name-only`. Keep evidence URLs and retrieval status in
the canonical dataset or provenance sidecar. Generated descriptions remain a
derived presentation layer and retain their evidence reference and AI marker.

Summarize evidence combinations across the full population before taxonomy
design. The distribution reveals which rows support deterministic assignment
and which rows form the review queue.

## Principle: use a resilient recovery ladder

Apply increasingly interpretive recovery methods while preserving the outcome
of each step:

1. structured endpoint or embedded data
2. direct entity page using the stable identifier
3. rendered browser-compatible request
4. first-party indexed page or another supported fallback
5. documented unresolved status

Use realistic browser headers and response limits appropriate to modern sites.
Keep retrieval status separate from evidence quality: a reachable page may still
contain generic platform text, while a recovered indexed page may provide strong
first-party evidence.

## Deterministic acceptance

For a multi-surface or crawlable source, run the source manifest through the
dataset gate:

```bash
python3 scripts/audit_ptah_dataset.py entities.canonical.json \
  --kind canonical \
  --source-manifest source-manifest.json \
  --require-gate taxonomy \
  --output grounding-audit.json
```

The audit reconciles population arithmetic, canonical row count, crawl totals,
source-id uniqueness, profile-URL coverage when declared available, and the
relationship between evidence basis and taxonomy confidence.
