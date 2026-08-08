# Image attachment optimization

Read this reference only when the user explicitly asks to fetch, populate,
refresh, repair, or synchronize logos or other Airtable image attachments. Do
not enter this workflow merely because the dataset contains a `Logo` field or
some rows have blank attachments.

## Contents

- [Default image policy](#default-image-policy)
- [Official asset discovery](#official-asset-discovery)
- [Logo.dev candidate discovery](#logodev-candidate-discovery)
- [Unsupported source formats](#unsupported-source-formats)
- [Transparency and contrast policy](#transparency-and-contrast-policy)
- [Dual-background card builder](#dual-background-card-builder)
- [Bundled helper](#bundled-helper)
- [Safe Airtable replacement](#safe-airtable-replacement)
- [Batch sequence and second look](#batch-sequence-and-second-look)
- [Completeness and gateway acceptance](#completeness-and-gateway-acceptance)

## Default image policy

- Fetch the official source image retry-safely.
- Validate the decoded image, not the filename extension alone; an endpoint that
  ends in `.png` may still return HTML or an error document.
- Treat direct SVG and ICO attachments as unsupported at the publish boundary.
  Convert them locally before upload; never send the original SVG/ICO URL as an
  Airtable attachment value.
- Treat logo services such as Logo.dev as optional accelerators. Use them only
  with a valid key and verify the returned identity. If the service is missing,
  unauthorized, or returns a placeholder, fall back to the official site asset
  or leave the field blank with a reviewed exception. Do not invent a wordmark.
- Keep originals temporary unless the user explicitly wants an archive.
- Process the first frame for ordinary multi-frame images; apply the adaptive
  frame-selection rule below for ICO sources.
- Auto-orient from source metadata.
- Preserve aspect ratio and never upscale.
- Use a 256-pixel maximum dimension by default. A simple logo displayed only on
  small cards may use 128 pixels. Treat 512 pixels as a ceiling, not a target,
  and use it only when the viewer or logo detail justifies the larger asset.
- Convert to sRGB WebP, strip metadata, and start near quality 84.
- Use a source hash in the optimized filename so a changed image cannot be
  mistaken for an already-current attachment merely because its byte size is
  unchanged.
- Record original and optimized MIME type, dimensions, bytes, SHA-256, source,
  output path, and compression percentage in a local manifest.

## Official asset discovery

Do not treat the first visible favicon or a common root path as the complete
asset inventory. Before generating a fallback or using a third-party logo
service:

1. Inspect the homepage and relevant product/about pages for `rel="icon"`,
   `apple-touch-icon`, web-manifest, structured-data, and brand/logo metadata.
2. Inspect same-origin HTML, CSS, and JavaScript references for explicit logo,
   icon, mark, favicon, app-icon, and wordmark assets.
3. Check reasonable first-party asset locations and siblings suggested by the
   site's own paths, including directories such as `/assets/logo/`, `/icons/`,
   and `/images/`, plus alternate raster or animated formats. Candidate names
   can include `logo`, `favicon`, `mark`, `icon`, and product-specific symbols.
4. Use retry-safe `HEAD` or `GET` requests, but validate decoded content rather
   than trusting status, suffix, or MIME headers. Record every candidate URL and
   result so a hidden but usable official asset is not silently skipped.
5. Render and compare every plausible candidate at full and card-thumbnail size.
   A file living in a logo directory is evidence, not proof: reject unrelated
   UI glyphs, generic controls, decorative images, and stale identities.
6. Rank a verified explicit brand/logo asset first, then official app/site icons
   and favicons. Use Logo.dev or another identity-verified service only after the
   first-party pass, and only when acceptable for the task.

If no candidate is suitable, leave `Logo` blank and report the exhausted sources.
Create a text wordmark or other non-official fallback only with explicit user
approval, label it as non-official in provenance, and never present it as
retrieved brand artwork.

## Logo.dev candidate discovery

For an explicit logo-completeness or repair request, Logo.dev is a discovery
source, not an identity authority.

1. Resolve and verify the current company-owned website before requesting a
   logo. Reject parked, for-sale, generic-directory, and unrelated redirect
   domains. Use location, category, source profile, and description evidence to
   disambiguate common company names.
2. Prefer Logo.dev domain lookup against the registrable current domain. Request
   a raster result at the intended maximum size and disable placeholder or
   monogram fallback, such as with `fallback=404`, so absence stays observable.
3. Keep the API token in the working area's ignored `.env`. Never write the
   token into source URLs, manifests, CSVs, reports, or progress logs.
4. Decode the response and reject HTML, empty files, screenshots, social-preview
   cards, generic monograms, and visually unrelated marks even when the request
   succeeds.
5. Compare the candidate with the current official site and available first-party
   assets. Acquisitions and rebrands require special care: do not assign an
   acquirer's logo to a distinct historical row, and do not keep both old and
   rebranded duplicate rows published merely to increase coverage.
6. Use Logo.dev name lookup only after domain and first-party discovery fail.
   Treat every name result as quarantined until a visual and entity-identity
   review proves it belongs to the intended organization.
7. Record a discovery ledger with stable row id, company name, current website,
   domain, candidate source, HTTP/decode result, identity decision, and rejection
   reason. Keep approved candidates separate from quarantines and approved blank
   exceptions.

A visually plausible response is not enough. Logo services can return a social
image, an acquired company's new parent identity, or another organization with
the same name. Prefer a verified company-issued asset when the service result is
wrong. If no trustworthy mark exists, preserve the blank explicitly rather than
publishing a guess.

## Unsupported source formats

SVG and ICO may be valid source assets, but they are not valid final Ptah/Airtable
attachments. Normalize them during the local prepare phase, before any attachment
upload or URL-based PATCH:

- For SVG, rasterize at twice the intended final maximum for antialiasing, capped
  at a 1024-pixel intermediate, then downsample and encode as PNG or WebP. With
  the 256-pixel default output, the normal SVG intermediate is 512 pixels.
- For ICO, inspect every embedded frame and select the smallest frame that meets
  the final target. If no frame is large enough, use the largest available frame
  without upscaling it. Do not assume frame zero is the best representation.
- Validate the decoded source format and the converted output MIME type. Do not
  trust a URL suffix or response header alone.
- Run the normal transparency, contrast, opacity, dimensions, hash, and thumbnail
  checks against the converted raster asset.
- Upload or PATCH only the converted raster bytes. Preserve the original SVG/ICO
  URL in provenance or the local manifest when useful, never in the final
  attachment field.

`scripts/optimize_airtable_attachments.py` performs this conversion to WebP in
its prepare phase. It rasterizes SVG inputs adaptively and selects the smallest
sufficient ICO frame before applying the normal output policy. Review the manifest
before execution and confirm that `sourceConversion.required` is true for these
inputs.

## Transparency and contrast policy

An image is not publishable merely because it downloads and has valid dimensions.
Logo visibility is a required attachment-quality check.

- Inspect the source and optimized image for an alpha channel, transparent pixels,
  and near-white foreground pixels.
- Preview the candidate at realistic card sizes on both a near-white surface and
  a dark surface. A metadata-only check cannot detect a white-on-white failure.
- For a white or translucent official mark, prefer an official square icon or
  colored-background variant. If none exists, composite the official mark onto
  a background taken from the site's published `theme-color`, documented brand
  palette, or the mark's own official dark presentation.
- If no official icon exists, leave the attachment blank by default. Create a
  concise identity wordmark only after explicit user approval; record that it is
  a non-official fallback and never substitute an unrelated parent-company or
  generic icon.
- If an opaque card can still blend into either pure white or pure black, add
  opposite-color keylines around it. Default to a white outer keyline and black
  inner keyline so at least one edge remains visible on either surface.
- Once a contrast background is added, flatten the result and require a fully
  opaque final image (`opaque=True` or no alpha channel). Use a new content hash
  and filename so downstream caches cannot retain the transparent predecessor.
- Run the optimizer with `--require-opaque` for these contrast-backed assets so
  preparation and reviewed-manifest reuse both fail if transparency returns.
- After Airtable replacement, download or render the Airtable-served full image
  and available thumbnails, including the smallest card-sized thumbnail around
  36 pixels. Repeat the pure-white/pure-black visibility check. Attachment
  count, dimensions, and MIME type alone are insufficient.
- Keep general upload artifacts from resending the original transparent URL.
  The optimized Airtable attachment or another durable contrast-safe asset must
  remain the authoritative published logo.

Use ImageMagick for the deterministic transform:

```sh
magick 'source-image[0]' \
  -auto-orient \
  -colorspace sRGB \
  -resize '256x256>' \
  -strip \
  -quality 84 \
  -define webp:method=6 \
  output.webp
```

Pass arguments as a subprocess list when scripting so `>` remains ImageMagick
geometry syntax instead of shell redirection.

## Dual-background card builder

Use [`scripts/build_contrast_logo_card.py`](../scripts/build_contrast_logo_card.py)
when the official mark or its opaque brand card can lose its edge on an all-white
or all-black surface. This deterministic helper preserves the supplied mark,
adds a brand/site background, flattens transparency, and surrounds the card with
dual white/black keylines.

For a transparent official mark:

```sh
python3 scripts/build_contrast_logo_card.py \
  --input ./logo.png \
  --output ./logo-contrast.webp \
  --background '#f5572a' \
  --qa-output ./logo-contrast-qa.png
```

For an existing square brand card, add `--input-mode card`. The QA image includes
full-size and 36-pixel previews on white and black panels. The builder defaults
to a 256-pixel card; use `--size 512` only for a verified high-density or detailed
mark requirement. Inspect both previews, then run
the attachment optimizer with `--require-opaque`. Do not use this helper to
invent a mark or replace a real logo with a generic glyph.

## Bundled helper

Use [`scripts/optimize_airtable_attachments.py`](../scripts/optimize_airtable_attachments.py)
with a canonical Ptah CSV. Its defaults expect `Id`, `Name`, and `Logo`.

Prepare and inspect locally:

```sh
python3 scripts/optimize_airtable_attachments.py \
  --input ./data/entities.ptah.csv \
  --output-dir ./data/logos/optimized \
  --manifest ./data/logos/manifest.json
```

After reviewing the manifest, synchronize the attachments:

```sh
python3 scripts/optimize_airtable_attachments.py \
  --input ./data/entities.ptah.csv \
  --output-dir ./data/logos/optimized \
  --manifest ./data/logos/manifest.json \
  --execute \
  --base app... \
  --table tbl... \
  --view viw...
```

Use `--reuse-manifest` only for a reviewed upload from the same prepared asset
set. Omit it during scheduled refreshes so changed source images are fetched
and reprocessed. Use `--only` to pilot one row by stable id or name.

Adapt a dataset-scoped copy when the canonical artifact is JSON, image sources
need custom authentication, a local dead-link placeholder needs special
handling, or the remote mapping differs materially from the default fields.

## Safe Airtable replacement

For every record:

1. Resolve the live Airtable record id through the stable local `Id`.
2. Snapshot every remote field except the target attachment and Airtable-owned
   last-modified fields.
3. Upload the optimized bytes through Airtable's content attachment endpoint.
   Do not clear the existing attachment first.
4. Identify exactly one new attachment id.
5. PATCH only the target attachment field, retaining only the new attachment
   id. This prunes the old file after the new one is safely present.
6. Read the record back and require exactly one intended attachment with the
   expected filename, WebP type, byte size, and dimensions at or below the
   configured maximum.
7. Compare the untouched-field snapshot before and after.
8. Stop the batch on the first upload, attachment, or preservation mismatch.

Do not send full-row payloads. Do not clear old attachments before a successful
upload. Airtable attachment URLs may rotate, so verify stable metadata and
attachment ids rather than treating URL changes as corruption.

## Batch sequence and second look

Use this order:

1. Refresh the canonical source dataset.
2. Fetch and transform all image-bearing rows locally.
3. Require zero transform errors, confirm that every SVG/ICO source was converted
   before upload, and inspect the largest originals, largest
   outputs, maximum dimensions, aggregate compression, and any file that grew.
4. Pilot the largest source image against Airtable.
5. Verify the pilot's attachment count and all unrelated fields.
6. Run the remaining attachment-only replacements.
7. Re-export or re-read the full view and verify record count, expected logo
   count, one attachment per intended row, maximum dimensions, opacity/contrast
   at full and smallest-thumbnail sizes on pure-white and pure-black surfaces,
   and preservation.
8. Record the manifest, verification report, policy, and completion status in
   the progress log.

Do not limit the second look to rows that already have a `Logo` value. A filter
such as `rows.filter(row => row.logoUrl)` can prove that existing files decode
while silently allowing every blank to pass. Audit the full published id set.

## Completeness and gateway acceptance

Maintain a small, reviewed blank-logo exception artifact. Each entry must include
the stable id, name, official website, evidence sources checked, and a concrete
reason no publishable mark exists. Acceptance requires:

- every published id is present exactly once
- every non-exempt published row has one intended logo
- every blank is in the exception artifact
- every exception is still blank; a newly populated exception fails until the
  stale exemption is removed
- every served image decodes, is WebP unless the target contract says otherwise,
  and stays within the configured dimension ceiling
- every gateway logo URL is a durable local storage path; no expiring Airtable,
  Logo.dev, or other external URL remains in the live provider feed
- zero legacy, failed, empty, or externally hosted assets remain

Use four separate counts in the machine report: published rows, source attachment
rows, durable gateway asset rows, and reviewed source blanks. Require source
attachments to equal durable gateway assets; never infer success from the number
of nonblank rendered cards because website and Logo.dev fallbacks can hide loss.
After one mismatch, run the same source-versus-gateway reconciliation across all
related maps or connections rather than treating the incident as local.

Classify every gap before repair. Check sanitized gateway cache status and the
source attachment metadata, never expiring delivery URLs:

- SVG or ICO attachments indicate a local-normalization omission; convert and
  re-upload raster WebP before refreshing.
- A large refresh that publishes an initial prefix and then reports many fetch,
  optimizer, or unknown failures indicates a likely per-request operation-budget
  exhaustion. Preserve the last complete generation and rerun only through a
  bounded resumable refresh.
- A few scattered failures require attachment-specific MIME, byte-size, decode,
  redirect, and optimizer inspection.

Do not accept a refresh merely because records, categories, or some assets were
published. Store the coverage report beside the attachment manifest and make the
regular audit exit nonzero on unexplained loss, stale exceptions, or inaccessible
map targets.

After machine checks pass, use the real viewer to inspect a labeled sample on
its actual light and dark surfaces. Always include user-reported companies,
common names, redirects, rebrands, acquisitions, Logo.dev name matches, manually
cropped sources, and contrast-card outputs. Verify manually cropped captures
immediately after writing them; dimensions and MIME type can still describe a
blank crop. If the viewer is canvas-based, use screenshots or pixel checks
rather than relying only on the accessibility tree.

After this workflow, derive a general Airtable upload artifact that omits
`Logo` or the optimized attachment field. Keep the canonical 12-field Ptah
artifact intact. This prevents a later full record upsert from restoring the
large source URLs over the optimized Airtable attachments.
