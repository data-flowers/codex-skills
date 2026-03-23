# Progress log

Use a local Markdown file as the workflow memory across sessions.

Treat this file as the workflow ground truth unless the current artifacts clearly prove it is stale.

## Purpose

This file is the handoff point between:

- the current agent
- a future agent
- the user after an interruption

It should make it easy to answer:

- which dataset this run is about
- where are we now
- what is the current source of truth
- what is the current remote target, if any
- what already happened
- what is blocked
- what should happen next

## Default path

Use:

- `./ptah-data-flow.progress.md`

If the user already has a preferred handoff file, use that instead.

## When to read it

Read it at the start of a session if it exists, especially when:

- the user is continuing prior work
- the workflow is already mid-stage
- Airtable or Ptah already exists
- the agent is resuming after an interruption

If this file already records a remote Airtable boundary, do not ignore that just because the user's latest message is shorter or less specific.

## When to update it

Update it after:

- the active dataset is identified or changed
- a stage is identified
- the source of truth changes
- a dataset is repaired or replaced
- taxonomy is set or revised
- curated fields are regenerated
- publish succeeds or fails
- a blocker or pitfall is discovered

## What to include

Keep these sections:

### Current stage

- active dataset label or slug
- current stage name
- why this is the current stage

### Source of truth

- current working artifact
- local publish artifact if one exists
- remote publish target if one exists
- dataset-scoped scripts or caches if they are now part of the run

When Airtable or another remote boundary exists, record it explicitly:

- Airtable URL if available
- Airtable PAT status: present or missing
- base id and base name if known
- table id and table name if known
- view id and view name if known
- whether the remote schema has been inspected yet
- whether the remote schema has been audited yet
- whether safe schema repairs were applied
- whether the remote has already been published to or is still pending first publish

After Airtable inspect succeeds, prefer recording both ids and names together. Later Ptah connection work depends on the resolved Airtable names, not only the ids from the URL.

Record PAT status only. Do not paste the PAT secret into this file.

When Ptah connection setup is in scope, also record:

- Ptah admin origin if known
- Ptah Airtable connection status: not started, tested, saved, or broken
- Ptah Airtable connection id if known
- if a replacement connection was saved, note that it supersedes the previous one

This remote block should be treated as the current remote state for later sessions unless a newer inspection proves it changed.

### Completed work

- short checklist or dated log of finished steps

### Pitfalls and findings

- important gotchas
- schema surprises
- taxonomy decisions
- permission or boundary problems

### Next moves

- next 1 to 3 bounded actions
- if the next move is blocked, say exactly what is missing, such as `GEMINI_API_KEY`, `EXA_API_KEY`, Airtable PAT, base id, table id, or user confirmation

### Open questions

- decisions still waiting on the user
- missing credentials or target identifiers count as open questions and should be written plainly

## Suggested template

```md
# Ptah data flow progress

## Current stage
- Dataset: miami-tech-vcs
- Stage: Stage 3 - taxonomy design and assignment
- Why: Raw source is canonicalized, but category and subcategory are still unresolved.

## Source of truth
- Working dataset: ./data/entities-working.csv
- Local publish artifact: ./data/entities.ptah.csv
- Airtable URL: https://airtable.com/app.../tbl.../viw...
- Remote publish target: Airtable base app... (`Miami Tech`), table tbl... (`Entities`), view viw... (`Grid view`)
- Airtable PAT: present
- Remote schema inspected: yes
- Remote schema audited: yes
- Remote schema repaired: renamed `﻿Id` to `Id`
- Remote publish status: pending first upload
- Ptah admin origin: http://localhost:3000
- Ptah Airtable connection status: tested
- Ptah Airtable connection id: 123e4567-e89b-12d3-a456-426614174000
- Builder: ./data/build_entities.py

## Completed work
- [x] Recovered HTML exports into one CSV
- [x] Removed exact duplicate rows from paginated exports
- [x] Built one canonical entity dataset
- [ ] Finalize taxonomy
- [ ] Rewrite descriptions
- [ ] Publish and verify

## Pitfalls and findings
- Source has two possible taxonomy columns; both are multi-tag.
- Raw industry labels are too noisy to copy directly into `Subcategory`.
- Airtable metadata requires `schema.bases:read`; records access alone is not enough.

## Next moves
- Inspect full label distribution before locking taxonomy
- Propose normalized `Category` and `Subcategory`
- Review the resulting bucket sizes once labels are assigned

## Open questions
- Does the user want to keep their existing category vocabulary, or use the default entity-type model?
```

## Style rules

- Keep it compact
- Prefer bullets over long paragraphs
- Prefer paths and facts over commentary
- Update it as the workflow moves, not just at the end
- Make it obvious which dataset the notes belong to when multiple datasets share one workspace
