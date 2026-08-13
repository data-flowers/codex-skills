# Taxonomy protocol

Use this reference whenever `Category` or `Subcategory` is under discussion.

## Contents

- [Default model](#default-model)
- [Entry gate](#entry-gate)
- [Required sequence](#required-sequence)
- [Source taxonomy preservation](#source-taxonomy-preservation)
- [Shape constraints](#shape-constraints)
- [Common patterns](#common-patterns)
- [What good looks like](#what-good-looks-like)

## Default model

Unless the user has a strong and defensible alternative, default to:

- `Category = entity type`
- `Subcategory = one normalized class`

Examples:

- `Category = Companies`
- `Subcategory = DevTools & Cloud`

- `Category = Investors`
- `Subcategory = Venture Capital`

This default is strong because it survives onboarding, maintenance, and mixed-source datasets better than raw source tags.

## Entry gate

Measure grounding coverage before assigning the final taxonomy. Use descriptions,
verified profile text, or equivalent attributable evidence—not names alone.

- Run `scripts/audit_ptah_dataset.py --require-gate taxonomy` with a declared
  grounding threshold.
- If the gate fails and enrichment is still feasible, enrich sparse rows before
  final taxonomy assignment.
- If the user accepts a sparse-source taxonomy, record the override and the
  evidence limitations.
- When a provisional name-only taxonomy already exists, re-evaluate low-confidence
  and boundary rows after descriptions materially improve.

## Required sequence

### 1. Inventory candidate source columns

Do not lock onto one column too early.

Inspect every plausible candidate:

- explicit category-like fields
- industry fields
- group fields
- tag fields
- source-specific labels
- inferred text fields if the source taxonomy is sparse

### 2. Inspect coverage

Look at:

- non-empty rate
- distinct value count
- whether the column is single-value or multi-value
- whether values are consistent or noisy

Do not assume the best-named column is the best source.

### 3. Inspect full distributions

Before deciding:

- look at top labels
- look at tail labels
- inspect whether one label dominates too much
- inspect whether labels are too fragmented

Do not decide from 5 rows.

### 4. Ask the user about taxonomy intent

Only after inspecting the data, ask whether the user already has a category model in mind.

Possible outcomes:

- they already know what `Category` should mean
- they know what `Subcategory` should mean
- they have labels, but they do not fit the data well
- they do not know and need the default recommendation

### 5. Evaluate fit against the Ptah contract

Remember:

- `Category` and `Subcategory` are single semantic slots in the downstream contract
- raw multi-label source fields often do not fit directly
- if a raw field is multi-tagged, sparse, or too broad, treat it as source material, not final output

### 6. Propose a model

Prefer the smallest defendable taxonomy.

Avoid:

- copying raw multi-tag strings directly
- creating dozens or hundreds of brittle final labels
- using labels that are too long for normal use
- repeating the category meaning in the subcategory label
- one-subcategory categories unless the user explicitly wants a flat taxonomy

### 7. Do a second look

After assigning or proposing labels, review:

- bucket sizes
- overly broad buckets
- tiny buckets that should merge
- long labels that can be compressed
- rendered label fit on the actual viewer; when the surface truncates around 17 characters, shorten both `Category` and `Subcategory` without changing their semantic role
- maximum `Subcategory` label length; revise any label longer than 24 characters unless the user explicitly requires exact source wording
- noisy labels that should normalize
- category/subcategory complementarity: the subcategory should add a useful distinction inside the category, not restate it
- category shape: each category should usually have 2-9 subcategories
- bucket floor: avoid final categories or subcategories with 5 or fewer rows unless the dataset is very small or the user explicitly wants rare classes preserved

Revise once if needed.

## Source taxonomy preservation

When the user asks to start from a source classification and then re-evaluate it, keep three separate layers:

1. **Initial classification**: copy the user-designated source signal into explicit helper fields such as `Initial Category` and `Initial Subcategory` before model or rule-based reassignment.
2. **Final classification**: write the re-evaluated navigation result only to Ptah `Category` and `Subcategory`.
3. **Original classification**: retain the untouched source labels under source-specific helper names and, when useful, a clearly labeled original-tags section in `AI Context`.

Do not rename an original source field to make it look like the final result. If the destination has a grouping field such as `Company Group`, decide explicitly whether it should carry an original source label or the new taxonomy, then verify that mapping after publish.

Review preservation mechanically across the full dataset: no missing original labels, no final assignments accidentally copied back into source fields, and no loss of multi-tag source values.

## Shape constraints

When the user asks for a "balanced" or "meaningful" taxonomy, enforce these checks before publishing:

- Every category has more than one subcategory.
- No category has more than 9 subcategories.
- Every final category has more than 5 rows.
- Every final subcategory has more than 5 rows.
- Every final `Subcategory` label is 24 characters or fewer, including spaces and punctuation, unless the user explicitly requires exact source wording. Use short natural labels such as `Meetings & Events`; never rely on the viewer to truncate a longer label.
- For compact card or filter surfaces, prefer both `Category` and `Subcategory` labels at 17 characters or fewer. Treat visible ellipsis as a taxonomy quality defect, not acceptable presentation. Examples: `Companies`, `Open Source`, `Publishers`, `Dev Workspaces`.
- Subcategory names complement category names. Good: `Category = STEM & Technical Learning`, `Subcategory = Math & Logic Practice`. Weak: `Category = Math Learning`, `Subcategory = Math Games & Practice`.

If the data cannot satisfy these constraints without absurd labels, merge sparse buckets upward. Preserve an intrinsically rare class only when its semantics are materially different, and record the exception and representative rows in the progress log.

## Common patterns

### Pattern: raw source has multiple possible category columns

This is normal. Compare them. Do not pick one just because the header looks best.

### Pattern: raw source has multi-tag fields

This is common in Crunchbase-like data. Use those fields as source material, not final labels.

### Pattern: user has their own labels

Respect the user's intent, but evaluate whether:

- coverage is good enough
- labels fit single-value downstream slots
- the result will still be understandable after publish

### Pattern: no good source taxonomy exists

Use:

- entity type for `Category`
- one normalized class for `Subcategory`

and derive those from the full dataset plus text context.

### Pattern: labels truncate in the viewer

Shorten the display vocabulary while preserving the existing assignments and
parent-child meaning. Update the canonical working dataset first, derive an
`Id`, `Category`, `Subcategory` maintenance artifact, PATCH only those fields,
and verify that publish state, AI Context, and attachments remain unchanged.

### Pattern: startups with weak or missing industry fields

This is common in event sites and sponsor grids.

Use:

- website title
- meta description
- first strong homepage paragraph
- product language in the name or profile copy

to infer one market vertical or industry per startup.

Do not use alphabetical buckets such as `A-F` or `M-R` as the final `Subcategory` unless the user explicitly wants navigation groups rather than semantic taxonomy.

## What good looks like

A good taxonomy is:

- understandable
- stable
- not overfit to one source
- not a raw tag dump
- balanced enough for navigation
- shaped so subcategories add detail rather than echoing categories
- checked against the full dataset
