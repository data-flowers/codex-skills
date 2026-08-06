# State and progress handoff

Use two artifacts with different purposes:

- `./ptah-data-flow.state.json`: compact current state, read by default
- `./ptah-data-flow.progress.md`: chronological evidence, read only when needed

## Current-state file

Keep the state file under 4 KB. It should answer the next agent's routing
questions without replaying project history.

```json
{
  "version": 1,
  "dataset": "example-map",
  "stage": "stage-6-maintenance",
  "status": "published",
  "sourceOfTruth": "./data/entities.canonical.json",
  "publishArtifact": "./data/entities.ptah.csv",
  "counts": {
    "canonical": 100,
    "published": 97,
    "unpublished": 3
  },
  "remote": {
    "airtableUrl": "https://airtable.com/app.../tbl.../viw...",
    "baseId": "app...",
    "tableId": "tbl...",
    "viewId": "viw...",
    "pat": "present",
    "connectionId": "uuid",
    "gatewayOrigin": "https://example-map.data.flowers"
  },
  "artifacts": {
    "latestVerification": "./data/verification.json",
    "latestManifest": "./data/manifest.json"
  },
  "sourceHash": "sha256:...",
  "canonicalHash": "sha256:...",
  "taxonomyVersion": "v1",
  "blockers": [],
  "next": ["Refresh only changed source rows"],
  "updatedAt": "2026-01-01T00:00:00Z"
}
```

Rules:

- Record secret status only (`present` or `missing`), never values.
- Keep only the latest authoritative artifact for each concern.
- Use stable ids, hashes, counts, and status enums rather than prose.
- Update atomically after a stage succeeds. Do not advance state before
  verification passes.
- Include only one to three next actions and current blockers.
- A newer direct inspection overrides stale state; update the file immediately.

## Historical progress log

Use Markdown for decisions and evidence that should survive but are not required
for every continuation. Append or compact it after:

- source-of-truth changes
- taxonomy revisions
- model-policy changes
- publish or deployment completion
- important failure diagnoses
- retirement, exception, or rollback decisions

Recommended sections:

```md
# Ptah data flow progress

## Current stage
- Dataset: example-map
- Stage: Stage 6 - maintenance

## Completed work
- 2026-01-01: Published 97 rows; verification passed.

## Pitfalls and findings
- Updated At is native Airtable lastModifiedTime.

## Next moves
- Refresh only changed source rows.

## Open questions
- None.
```

Keep chronology factual. Store detailed counts and machine output in JSON reports,
then link their paths instead of pasting them into Markdown.

## Read policy

At task start:

1. Read `ptah-data-flow.state.json` if present.
2. Inspect the latest artifacts named there.
3. Read the progress log only if state is missing, contradictory, or insufficient
   for the current decision, or when the user requests history.

This policy prevents a long project history from becoming recurring model input
while retaining a durable audit trail on disk.
