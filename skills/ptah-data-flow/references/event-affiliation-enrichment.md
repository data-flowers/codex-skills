# Event-affiliation enrichment

Use this reference when an event export names organizations but their web
presence is missing, ambiguous, or only reachable through authenticated attendee
profiles.

## Preserve the discovery graph

Before discarding attendee columns, keep a research-only sidecar linking:

- stable participant or registration id
- public attendee name and role when authorized for research
- stated organization label
- participation or profile URL
- location and public professional profile clues

Do not publish attendee details as organization fields. Use them only to resolve
the organization and retain the evidence path.

## Resolution sequence

For each unresolved organization:

1. Normalize its source label without destroying the original value.
2. Collect affiliated attendees and rank the strongest role, location, and public
   profile signals.
3. Search exact organization-plus-person combinations before broad name-only
   search.
4. Compare candidate domains against the attendee's role, employer wording,
   geography, products, and event context.
5. Reuse the user's authenticated event session when the public profile is gated
   by login. Record `authenticated-profile` as the access method; do not capture
   account credentials or session storage.
6. Route candidate websites through the scheme, hostname, bot-filter, rebrand,
   and successor checks in [website-liveness.md](website-liveness.md).
7. Promote a website only when the entity match is supported; leave ambiguous
   rows unresolved instead of selecting the best-looking domain.

## Candidate lifecycle

Track website and identity hypotheses separately from final values:

- `candidate`: found by search or name similarity
- `supported`: affiliation and contextual evidence agree
- `authenticated`: an authenticated source explicitly connects the attendee and
  organization
- `verified`: the domain and organization identity are corroborated strongly
  enough to publish

Keep the evidence URL, method, confidence, and reason for every promotion. When
a stronger authenticated or first-party source becomes available, retroactively
audit all earlier guesses rather than reviewing only unresolved rows.

## Description acceptance

Reject descriptions that describe the hosting platform rather than the entity.
Common failure modes include generic LinkedIn, Facebook, registry, login, cookie,
search, error, and directory text. Also flag:

- the same description repeated across three or more entities
- content whose named organization conflicts with the target
- recruitment or event boilerplate with no organization-specific facts
- descriptions derived only from an inaccessible page title or snippet

Keep platform pages as identity evidence when useful, but do not publish the
platform's metadata as the organization's description.

## Outputs

Produce:

- an attendee-to-organization research sidecar
- a candidate ledger with lifecycle state and evidence
- a recovered-website delta
- a retroactive audit of previously guessed websites
- description evidence with direct-source, supported-fallback, or limited tier

Merge only verified values into the canonical dataset. Preserve unresolved rows
and their strongest remaining evidence for later review.
