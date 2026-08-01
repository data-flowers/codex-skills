# Image attachment optimization

Read this reference when a Ptah dataset contains logos or other Airtable image
attachments that are oversized, need recurring refreshes, or must be replaced
without disturbing the rest of a published record.

## Contents

- [Default image policy](#default-image-policy)
- [Transparency and contrast policy](#transparency-and-contrast-policy)
- [Dual-background card builder](#dual-background-card-builder)
- [Bundled helper](#bundled-helper)
- [Safe Airtable replacement](#safe-airtable-replacement)
- [Batch sequence and second look](#batch-sequence-and-second-look)

## Default image policy

- Fetch the official source image retry-safely.
- Validate the decoded image, not the filename extension alone; an endpoint that
  ends in `.png` may still return HTML or an error document.
- Treat logo services such as Logo.dev as optional accelerators. Use them only
  with a valid key and verify the returned identity. If the service is missing,
  unauthorized, or returns a placeholder, fall back to the official site asset,
  published theme, or a relevant wordmark rather than blocking the workflow.
- Keep originals temporary unless the user explicitly wants an archive.
- Process the first frame only.
- Auto-orient from source metadata.
- Preserve aspect ratio and never upscale.
- Cap width and height at 512 pixels unless the viewer has a documented need
  for a different maximum.
- Convert to sRGB WebP, strip metadata, and start near quality 84.
- Use a source hash in the optimized filename so a changed image cannot be
  mistaken for an already-current attachment merely because its byte size is
  unchanged.
- Record original and optimized MIME type, dimensions, bytes, SHA-256, source,
  output path, and compression percentage in a local manifest.

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
- If no official icon exists, a concise identity wordmark is a valid fallback;
  do not substitute an unrelated parent-company or generic icon.
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
  -resize '512x512>' \
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
full-size and 36-pixel previews on white and black panels. Inspect both, then run
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
3. Require zero transform errors and inspect the largest originals, largest
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

After this workflow, derive a general Airtable upload artifact that omits
`Logo` or the optimized attachment field. Keep the canonical 12-field Ptah
artifact intact. This prevents a later full record upsert from restoring the
large source URLs over the optimized Airtable attachments.
