# Rewrite runners

Use for an authorized model-backed rewrite of `Description` or `AI Context`.
Enrich sparse evidence first; a rewrite cannot create missing facts.

## Entry points and configuration

The three entrypoints share [rewrite_runtime.py](../scripts/rewrite_runtime.py)
and [gemini_rewrite_common.py](../scripts/gemini_rewrite_common.py):

| Entrypoint | Policy | Default request size |
|---|---|---|
| [rewrite_descriptions_gemini.py](../scripts/rewrite_descriptions_gemini.py) | One compact sentence, no entity name or URLs | One row |
| [rewrite_ai_context_gemini.py](../scripts/rewrite_ai_context_gemini.py) | Validated Markdown with six headings | One row |
| [rewrite_ai_context_gemini_batched.py](../scripts/rewrite_ai_context_gemini_batched.py) | Same AI Context policy, one result per exact id | Eight rows |

Run the installed entrypoint directly. Keep dataset-specific paths, field
selection, model, and quota settings in a JSON config rather than copying the
runner. All command-line options can be set with underscore keys, except
`api_key` and `config`. CLI arguments override config values; paths inside a
config resolve relative to that file. Credentials come from the environment.

```json
{
  "input_csv": "entities.csv",
  "output_csv": "entities.rewritten.csv",
  "cache_dir": "cache/ai-context",
  "context_columns": "Name,Website,Description",
  "link_columns": "Website",
  "max_context_chars": 6000,
  "workers": 1,
  "request_delay_seconds": 4.5
}
```

```bash
python3 /path/to/ptah-data-flow/scripts/rewrite_ai_context_gemini_batched.py \
  --config ./rewrite.json --limit 3
```

Supply `--system-file` and `--prompt-file` for custom wording within the selected
validator's output contract. The batched runner also accepts the older
`--batch-policy-file` spelling. A prompt file uses Python format placeholders:
`{context}`, `{allowed_links}`, and `{target_column}` for single rows;
`{entities}` for batches. Escape literal JSON braces as `{{` and `}}`.
Changing heading order or output constraints requires a deliberate policy/validator
change. Copy code only for that exceptional customization and record its source
version; keep all needed shared modules together.

## Input and transmission checks

- Require nonblank, unique, opaque text ids. The same id must be returned exactly
  once per batch. Name-only fallback cache identities are no longer supported.
- `--context-columns` is required in every mode. An omitted or misspelled field
  selection fails before any request. Prefer only approved public fields.
- Link columns are separate. `--link-columns ''` means no links; it never scans
  other columns. Exclude private contacts, internal notes, raw evidence blobs,
  seed aliases, and unrelated columns from both selections.
- The default cap is 6,000 characters per row, including selected context and
  allowed links. Oversized rows fail locally. Curate a shorter source excerpt or
  explicitly choose a suitable `--max-context-chars`; the runner does not silently
  truncate decision-bearing evidence.
- The target field cannot also be a prompt input. Preserve prior text in a
  separate approved source column when needed.
- Confirm the sample's identity, grounding, and style before the full run.
  A successful structural validator does not prove factual quality.

## Output contract

`Description` uses one neutral sentence, normally 12–22 words, with validation
limits of 8–28 words and 180 characters. It excludes the entity name and URLs.

`AI Context` contains only the validated Markdown body, at most 200 words,
with headings in this order: `what`, `why`, `who`, `for whom`, `in relation to`,
and `what's nice great and superb`. Prefer much shorter text when evidence is
limited. Keep sources in the per-row cache/provenance, outside the published
field. The final stored string is the validated string.

## Rate, retry, and cost behavior

All runners support `--workers`, `--request-delay-seconds`, `--shard-count`,
`--shard-index`, `--force`, and incremental flushes. The batch runner supports
`--batch-size 1..12`; single-row entrypoints require size one.

Request delay now controls the minimum interval between request starts across
all workers in one process, including retries. Increasing workers overlaps slow
responses without multiplying that process's request-start budget. Set the delay
and concurrency from the actual quota; separate shards still share the account's
quota and need a combined budget. Defaults are one worker and 4.5 seconds.

Validation failures get bounded retries with feedback. Authentication, invalid
request/model, and quota errors stop the run so configuration can be corrected.
Do not restart a throttled run at the same rate. Successful rows are cached even
if another row later fails, and CSV/cache replacement is atomic.

Each API attempt has an event in a local JSONL journal, including model, prompt
version, prompt, response when available, retry number, and usage metadata.
Cache hits are separate events with zero new API usage. Missing usage is reported
as unavailable rather than zero. A compact run summary records totals and points
to the detailed journal; neither includes credentials.

Cache paths hash the exact id. Cache validity additionally depends on source
fields, model, and prompt policy. Corrupt or mismatched entries are regenerated.
Older slug-based caches are not trusted by the new runner; budget for one
regeneration pass after upgrading. Caches and outputs remain dataset-scoped.

## Narrow maintenance

Use `--missing-only` or repeat `--id` to select a bounded set; ids refer to the
configured input id column. Output CSVs retain unselected rows unchanged. Keep
`--force` off unless regeneration is intended.

Upload only selected ids and changed fields using
[the maintenance path](airtable-maintenance.md). Routine updates end with a
successful narrow PATCH. A publication-control change or another high-risk
operation uses the verification described in [the publication boundary](airtable-boundary.md).
