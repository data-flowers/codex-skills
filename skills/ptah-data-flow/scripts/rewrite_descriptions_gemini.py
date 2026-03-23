#!/usr/bin/env python3

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    class _TqdmFallback:
        def __init__(self, iterable=None, **_: object):
            self.iterable = iterable

        def __iter__(self):
            return iter(self.iterable or [])

        def update(self, _: int = 1) -> None:
            return None

        def close(self) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def tqdm(iterable=None, **kwargs: object):
        return _TqdmFallback(iterable=iterable, **kwargs)

from gemini_rewrite_common import (
    DEFAULT_MODEL,
    GeminiGenerationError,
    build_context_from_columns,
    call_gemini_json,
    choose_context_columns,
    in_shard,
    load_cached_result,
    load_csv,
    mentions_entity_name,
    normalize_whitespace,
    parse_csv_list,
    read_optional_text,
    require_api_key,
    row_cache_key,
    save_cached_result,
    word_count,
    write_csv,
)

PROMPT_VERSION = "generic-description-v1"

DEFAULT_SYSTEM = """You rewrite Airtable-style entity descriptions for a curated map.
Stay strictly grounded in the provided context.
Return valid JSON only."""

DEFAULT_PROMPT = """# Task
Rewrite the `{target_column}` field for one entity.

# Hard constraints
- Return exactly one JSON object with this shape: {{"description":"..."}}.
- Output exactly one sentence.
- Prefer 12 to 22 words. Hard max 28 words.
- Do not include the entity name, any URL, markdown, quotes, source notes, or emojis.
- Keep the sentence dense, neutral, polished, and visually consistent with other cards.
- Make it specific enough to differentiate the entity from nearby cards.
- Use only facts explicitly supported by the context. Do not guess.

# Notes
- Adapt this prompt if your dataset has a specific style policy.
- If your dataset distinguishes companies, investors, people, or projects, update the instructions accordingly.

# Entity context
{context}
"""


def validate_description(candidate: str, name: str) -> str:
    text = normalize_whitespace(candidate).strip("\"' ")
    if not text:
        raise ValueError("Description is empty.")
    if "http://" in text.lower() or "https://" in text.lower() or "www." in text.lower():
        raise ValueError("Description contains a URL.")
    if name and mentions_entity_name(text, name):
        raise ValueError("Description contains the entity name.")
    if "\n" in candidate:
        raise ValueError("Description contains a newline.")
    if word_count(text) < 8 or word_count(text) > 28:
        raise ValueError("Description is outside the target word range.")
    if len(text) > 180:
        raise ValueError("Description is too long.")
    sentence_breaks = sum(text.count(mark) for mark in [".", "!", "?"])
    if sentence_breaks > 1:
        raise ValueError("Description is not a single sentence.")
    if text[-1] not in ".!?":
        text = f"{text}."
    return text


def generate_description(
    *,
    row: dict[str, str],
    cache_key: str,
    name: str,
    api_key: str,
    model: str,
    system_instruction: str,
    prompt_template: str,
    context_columns: list[str],
    target_column: str,
    max_attempts: int,
    timeout_seconds: int,
) -> tuple[str, dict[str, object]]:
    context = build_context_from_columns(row, context_columns)
    feedback = ""
    last_error = ""

    for _ in range(max_attempts):
        prompt = prompt_template.format(
            context=context,
            target_column=target_column,
        )
        if feedback:
            prompt += f"\n# Fix required\n{feedback}\n"
        try:
            payload = call_gemini_json(
                api_key=api_key,
                model=model,
                system_instruction=system_instruction,
                prompt=prompt,
                timeout_seconds=timeout_seconds,
            )
            description = validate_description(payload.get("description", ""), name)
            return description, {
                "prompt_version": PROMPT_VERSION,
                "cache_key": cache_key,
                "name": name,
                "description": description,
                "raw_response": payload,
            }
        except (GeminiGenerationError, ValueError) as exc:
            last_error = str(exc)
            feedback = f"Previous output failed validation: {last_error}"

    raise GeminiGenerationError(f"Failed to rewrite Description for {name or cache_key}: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Template Gemini batch runner for a Description-like field. Copy and adapt into the active dataset working area before large runs."
    )
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--id-column", default="Id")
    parser.add_argument("--name-column", default="Name")
    parser.add_argument("--target-column", default="Description")
    parser.add_argument("--context-columns", default="")
    parser.add_argument("--prompt-file", type=Path, default=None)
    parser.add_argument("--system-file", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--flush-every", type=int, default=20)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    api_key = require_api_key(args.api_key)
    fieldnames, rows = load_csv(args.input_csv)

    if args.name_column not in fieldnames:
        raise SystemExit(f"Missing required name column: {args.name_column}")
    if args.target_column not in fieldnames:
        fieldnames.append(args.target_column)
        for row in rows:
            row[args.target_column] = ""

    requested_context_columns = parse_csv_list(args.context_columns)
    context_columns = choose_context_columns(fieldnames, requested_context_columns)
    if not context_columns:
        raise SystemExit("No context columns available for prompt construction.")

    system_instruction = read_optional_text(args.system_file) or DEFAULT_SYSTEM
    prompt_template = read_optional_text(args.prompt_file) or DEFAULT_PROMPT

    processed = 0
    pending = []

    with tqdm(total=len(rows if args.limit <= 0 else rows[: args.limit]), desc="Descriptions") as progress:
        selected_rows = rows[: args.limit] if args.limit > 0 else rows
        for row_index, row in enumerate(selected_rows):
            cache_key = row_cache_key(row, row_index, args.id_column, args.name_column)
            try:
                allowed = in_shard(cache_key, args.shard_count, args.shard_index)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            if not allowed:
                progress.update(1)
                continue

            cached = None if args.force else load_cached_result(args.cache_dir, cache_key)
            if cached is not None:
                row[args.target_column] = cached["description"]
                processed += 1
                progress.update(1)
                if processed % max(args.flush_every, 1) == 0:
                    write_csv(args.output_csv, fieldnames, rows)
                continue

            pending.append((row_index, row, cache_key))

        with ThreadPoolExecutor(max_workers=max(args.workers, 1)) as executor:
            future_map = {
                executor.submit(
                    generate_description,
                    row=row,
                    cache_key=cache_key,
                    name=normalize_whitespace(row.get(args.name_column, "")),
                    api_key=api_key,
                    model=args.model,
                    system_instruction=system_instruction,
                    prompt_template=prompt_template,
                    context_columns=context_columns,
                    target_column=args.target_column,
                    max_attempts=args.max_attempts,
                    timeout_seconds=args.timeout_seconds,
                ): (row, cache_key)
                for _, row, cache_key in pending
            }

            for future in as_completed(future_map):
                row, cache_key = future_map[future]
                try:
                    description, cache_payload = future.result()
                    row[args.target_column] = description
                    save_cached_result(args.cache_dir, cache_key, cache_payload)
                except Exception:
                    write_csv(args.output_csv, fieldnames, rows)
                    for other in future_map:
                        other.cancel()
                    raise

                processed += 1
                progress.update(1)
                if processed % max(args.flush_every, 1) == 0:
                    write_csv(args.output_csv, fieldnames, rows)

    write_csv(args.output_csv, fieldnames, rows)
    print(f"Wrote {len(rows)} rows -> {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
