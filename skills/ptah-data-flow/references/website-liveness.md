# Website liveness and retirement

Use this reference when published entity URLs may be dead, moved, parked, or no longer representative of an operating entity.

## Contents

- [Decision standard](#decision-standard)
- [Run the mechanical pass](#run-the-mechanical-pass)
- [Review ambiguous rows](#review-ambiguous-rows)
- [Choose the outcome](#choose-the-outcome)
- [Apply a field-scoped delta](#apply-a-field-scoped-delta)
- [Verify Airtable and Ptah](#verify-airtable-and-ptah)

## Decision standard

Do not infer company status from one HTTP request. Keep three questions separate:

1. Does the stored URL work for a normal user?
2. Is there a verified current URL for the same entity?
3. Is the entity still operating as a standalone published record?

Website health, entity status, and logo attachment health are independent. A broken homepage alone is not enough to modify `Logo` or delete the record.

## Run the mechanical pass

Audit every in-scope URL with retry-safe requests and record evidence per row:

- original URL and stable row id
- redirect chain and final URL
- HTTPS and HTTP when relevant
- `www` and apex hostname variants
- response status, content type, title, and obvious parking language
- DNS result and TLS failure separately
- retry outcome for transient errors

Classify results into:

- `active`: a representative page works
- `correctable_url`: an official replacement or URL variant works
- `parked_suspect`: the domain is for sale or contains parking content
- `confirmed_broken`: repeated checks show a durable failure
- `manual_review`: the evidence is ambiguous or automation is blocked

Treat 401, 403, 429, bot challenges, intermittent 5xx responses, timeouts, and unusual TLS behavior as `manual_review` by default. A restricted execution environment can also produce false DNS failures; corroborate DNS before using it as retirement evidence.

## Review ambiguous rows

For every non-active result:

- use an independent DNS resolver or browser-backed check
- search for the official entity, product, rebrand, acquisition, or shutdown
- inspect official documentation, status pages, profiles, or successor notices
- verify that a candidate replacement domain represents the same entity
- reject same-name and similar-domain collisions
- check meaningful indexed paths when the root is intentionally sparse

Keep a decision log containing the row id, name, prior URL, evidence, outcome, reason, and replacement URL when applicable. Do not present automation-blocked rows as dead.

## Choose the outcome

Use the smallest defensible change:

- keep the row unchanged when it is active or only automation-blocked
- update `Website` when the same entity has a verified current official URL
- retire the row when the domain is durably broken or parked and evidence shows no active standalone entity
- leave the row in manual review when the evidence conflicts

An acquisition does not always require retirement. Preserve a standalone row when the product or brand remains meaningfully active; retire it when it has been absorbed and no longer has a distinct published presence.

## Apply a field-scoped delta

Keep retired rows in the canonical working dataset and underlying Airtable table. Preserve stable ids, original taxonomy, descriptions, context, and attachments.

Create two derived artifacts when needed:

- an archive/upload artifact containing every retained row and its publication controls
- a Ptah publish artifact containing only rows intended for the live view

Inspect the destination view and Airtable schema before patching. Use every control field required by the filter and only valid select choices. Do not assume that `Published=false` alone removes a row. Patch only `Website` for corrections and only the required publication-control fields for retirements; omit `Logo` and unrelated fields.

## Verify Airtable and Ptah

After the patch:

- verify total Airtable count is unchanged unless deletion was explicitly requested
- verify the published view count changed by exactly the intended amount
- verify retired ids remain in the table but not in the published view
- verify corrected URLs on the intended records
- compare untouched fields on every changed record
- call the exact provider endpoint saved by Ptah
- verify provider count, unique ids, corrected URLs, and retired-id absence
- test gateway change detection after view removals

If a filtered-view timestamp misses a removal, prefer an explicit cache refresh. Use a reversible signal-record update only as a last resort, restore it immediately, verify unrelated fields, and record the refreshed timestamp and provider result.
