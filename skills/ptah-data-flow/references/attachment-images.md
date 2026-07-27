# Image attachment optimization

Read this reference when a Ptah dataset contains logos or other Airtable image
attachments that are oversized, need recurring refreshes, or must be replaced
without disturbing the rest of a published record.

## Default image policy

- Fetch the official source image retry-safely.
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
   count, one attachment per intended row, maximum dimensions, and preservation.
8. Record the manifest, verification report, policy, and completion status in
   the progress log.

After this workflow, derive a general Airtable upload artifact that omits
`Logo` or the optimized attachment field. Keep the canonical 12-field Ptah
artifact intact. This prevents a later full record upsert from restoring the
large source URLs over the optimized Airtable attachments.
