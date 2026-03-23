#!/usr/bin/env python3

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
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
    normalize_whitespace,
    parse_csv_list,
    read_optional_text,
    require_api_key,
    row_cache_key,
    save_cached_result,
    url_candidates_from_columns,
    word_count,
    write_csv,
)

PROMPT_VERSION = "generic-ai-context-v1"

DEFAULT_SYSTEM = """You write compact grounded entity briefs for an AI context field.
Stay strictly grounded in the provided context.
Return valid JSON only."""

DEFAULT_PROMPT = """# Task
Write a max-200-word structured markdown brief for one entity.

# Hard constraints
- Return exactly one JSON object with this shape: {{"markdown":"...","source_links":["..."]}}.
- markdown must contain exactly these six section headings, in this order:
  1. what
  2. why
  3. who
  4. for whom
  5. in relation to
  6. what's nice great and superb
- Keep the markdown body at or below 200 words.
- Use plain markdown only. No code fences.
- Do not include raw URLs inside the markdown body.
- Keep each section compact.
- Use only facts explicitly supported by the context. Do not guess.
- source_links may include up to 4 links and must be chosen only from the allowed source links in the context.
- If a section is not explicit in the source, use a very short grounded fallback such as "Not explicit in source."

# Entity context
{context}

# Allowed source links
{allowed_links}
"""

EXPECTED_HEADINGS = [
    "what",
    "why",
    "who",
    "for whom",
    "in relation to",
    "what's nice great and superb",
]


def validate_markdown(markdown: str) -> str:
    text = (markdown or "").strip()
    if not text:
        raise ValueError("Markdown body is empty.")
    if "http://" in text.lower() or "https://" in text.lower() or "www." in text.lower():
        raise ValueError("Markdown body contains a URL.")

    heading_labels = []
    for line in text.splitlines():
        line = line.strip()
        match = re.match(r"^#{1,6}\s*(.+?)\s*$", line)
        if match:
            heading_labels.append(match.group(1).strip().lower())

    if heading_labels != EXPECTED_HEADINGS:
        raise ValueError("Markdown headings do not match the required section order.")
    if word_count(text) > 200:
        raise ValueError("Markdown body exceeds 200 words.")
    return text


def normalize_source_links(generated: object, allowed: list[str]) -> list[str]:
    if not isinstance(generated, list):
        raise ValueError("source_links must be a JSON array.")
    allowed_set = set(allowed)
    output: list[str] = []
    for value in generated:
        if not isinstance(value, str):
            continue
        value = normalize_whitespace(value)
        if not value or value not in allowed_set or value in output:
            continue
        output.append(value)
    return output[:4]


def render_ai_context(markdown: str, links: list[str]) -> str:
    if not links:
        return markdown
    return f"{markdown}\n\nSources:\n" + "\n".join(links)


def generate_ai_context(
    *,
    row: dict[str, str],
    cache_key: str,
    api_key: str,
    model: str,
    system_instruction: str,
    prompt_template: str,
    context_columns: list[str],
    link_columns: list[str],
    max_attempts: int,
    timeout_seconds: int,
) -> tuple[str, dict[str, object]]:
    context = build_context_from_columns(row, context_columns)
    allowed_links = url_candidates_from_columns(row, link_columns)
    allowed_links_text = "\n".join(f"- {link}" for link in allowed_links) or "- none"
    feedback = ""
    last_error = ""

    for _ in range(max_attempts):
        prompt = prompt_template.format(
            context=context,
            allowed_links=allowed_links_text,
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
            markdown = validate_markdown(payload.get("markdown", ""))
            links = normalize_source_links(payload.get("source_links", []), allowed_links)
            ai_context = render_ai_context(markdown, links)
            return ai_context, {
                "prompt_version": PROMPT_VERSION,
                "cache_key": cache_key,
                "ai_context": ai_context,
                "raw_response": payload,
            }
        except (GeminiGenerationError, ValueError) as exc:
            last_error = str(exc)
            feedback = f"Previous output failed validation: {last_error}"

    raise GeminiGenerationError(f"Failed to rewrite AI Context for {cache_key}: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Template Gemini batch runner for an AI Context-like field. Copy and adapt into the active dataset working area before large runs."
    )
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--id-column", default="Id")
    parser.add_argument("--name-column", default="Name")
    parser.add_argument("--target-column", default="AI Context")
    parser.add_argument("--context-columns", default="")
    parser.add_argument("--link-columns", default="Website")
    parser.add_argument("--prompt-file", type=Path, default=None)
    parser.add_argument("--system-file", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--flush-every", type=int, default=10)
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
    requested_link_columns = parse_csv_list(args.link_columns)
    context_columns = choose_context_columns(fieldnames, requested_context_columns)
    link_columns = choose_context_columns(fieldnames, requested_link_columns)
    if not context_columns:
        raise SystemExit("No context columns available for prompt construction.")

    system_instruction = read_optional_text(args.system_file) or DEFAULT_SYSTEM
    prompt_template = read_optional_text(args.prompt_file) or DEFAULT_PROMPT

    processed = 0
    pending = []

    with tqdm(total=len(rows if args.limit <= 0 else rows[: args.limit]), desc="AI Context") as progress:
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
                row[args.target_column] = cached["ai_context"]
                processed += 1
                progress.update(1)
                if processed % max(args.flush_every, 1) == 0:
                    write_csv(args.output_csv, fieldnames, rows)
                continue

            pending.append((row_index, row, cache_key))

        with ThreadPoolExecutor(max_workers=max(args.workers, 1)) as executor:
            future_map = {
                executor.submit(
                    generate_ai_context,
                    row=row,
                    cache_key=cache_key,
                    api_key=api_key,
                    model=args.model,
                    system_instruction=system_instruction,
                    prompt_template=prompt_template,
                    context_columns=context_columns,
                    link_columns=link_columns,
                    max_attempts=args.max_attempts,
                    timeout_seconds=args.timeout_seconds,
                ): (row, cache_key)
                for _, row, cache_key in pending
            }

            for future in as_completed(future_map):
                row, cache_key = future_map[future]
                try:
                    ai_context, cache_payload = future.result()
                    row[args.target_column] = ai_context
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
