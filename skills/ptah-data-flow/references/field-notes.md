# Reusable field lessons

Use these cases to find the maintained rule. Operational instructions belong in
the linked reference; do not treat historical examples as additional stages.

| Observed problem | Maintained guidance |
|---|---|
| Duplicate rows obscured source counts; homogeneous directories produced redundant categories | [Taxonomy diagnostics and source preservation](taxonomy.md) |
| Name-only assignments became misleading after enrichment; a registration type overrode explicit function | [Grounding and evidence precedence](taxonomy.md) |
| Compressed summaries lost facts needed to distinguish neighboring classes | [Taxonomy conflict patterns](taxonomy.md) |
| Commercial profiles supplied update or acquisition dates as founding years | [Temporal evidence policy](enrichment.md) |
| Attendee affiliations resolved organizations with sparse websites | [Event-affiliation discovery](event-affiliation-enrichment.md) |
| A host platform's login/metadata text was mistaken for an organization description | [Description acceptance](event-affiliation-enrichment.md) |
| CSV headers counted as records; imported timestamps were not native Last modified time | [Publication boundary and native timestamp provisioning](airtable-boundary.md) |
| General imports overwrote attachments; reclassification replaced Airtable record identities | [Narrow field omission and known-record updates](airtable-maintenance.md) |
| An empty filtered view looked like a successful table upload | [Publication-control tuples](airtable-boundary.md) |
| Rewrites throttled, caches collided, and retries disappeared from cost summaries | [Shared execution, pacing, and usage](rewrite-runners.md) |
| Opaque and transparent logos failed on one background; SVG/ICO sources needed normalization | [Attachment identity, conversion, and contrast](attachment-images.md) |
| Website failure was confused with company closure or logo failure | [Independent liveness and retirement signals](website-liveness.md) |
| A filtered view failed to expose retired rows to change detection | [Gateway and publication acceptance](gateway-deployment.md) |
| A deployment snapshot worked but later releases lost the map | [Canonical deployment configuration](gateway-deployment.md) |
| A stale checkout overwrote installed improvements | [Source reconciliation and full-tree parity](skill-maintenance.md) |

Two intake lessons still apply before these specialized workflows:

- If the user invalidates a source, rebuild from trusted sources and recompute
  provenance. Identify rows that no longer have trusted support and handle them
  under the requested removal or retirement scope. Record the source-of-truth change.
- If an HTML grid contains links and logos but no names, names inferred from
  filenames or hosts must be labeled as inference in provenance.

Read [state/progress handoff](progress-log.md) for continuation and
[credential sourcing](credential-sourcing.md) for secrets. Keep project-specific
incidents in the project's history rather than accumulating universal rules here.
