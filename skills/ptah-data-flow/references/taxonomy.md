# Taxonomy protocol

Use this reference whenever `Category` or `Subcategory` is under discussion.

## Default model

Unless the user has a strong and defensible alternative, default to:

- `Category = entity type`
- `Subcategory = one normalized class`

Examples:

- `Category = Startups & Companies`
- `Subcategory = DevTools & Cloud`

- `Category = Investors & VCs`
- `Subcategory = Venture Capital`

This default is strong because it survives onboarding, maintenance, and mixed-source datasets better than raw source tags.

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
- inspect membership inside large buckets, not only counts

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

### 7. Do a second look

After assigning or proposing labels, review:

- bucket sizes
- bucket membership for the largest labels
- overly broad buckets
- tiny buckets that should merge
- long labels that can be compressed
- noisy labels that should normalize

Revise once if needed.

Emit a small taxonomy diagnostics artifact when practical. It should include at least row id, name, final `Category`, final `Subcategory`, and the signal or source value that drove the assignment. Counts alone are not enough when labels are broad.

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

### Pattern: homogeneous directory with topic navigation

Sometimes every row already shares one entity type, such as organizations, institutions, or agencies, and the user explicitly wants meaningful topic navigation.

In that case, you may use:

- `Category = broad topical area`
- `Subcategory = narrower topical focus`

This is an exception to the default entity-type model. Record the reason in the progress log and verify the taxonomy by reviewing both label counts and the membership of large buckets.

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
- checked against the full dataset
