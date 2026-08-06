#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from gemini_rewrite_common import (
    DEFAULT_MODEL,
    GeminiGenerationError,
    build_context_from_columns,
    call_gemini_json,
    choose_context_columns,
    load_cached_result,
    load_csv,
    parse_csv_list,
    read_optional_text,
    require_api_key,
    row_cache_key,
    row_source_fingerprint,
    save_cached_result,
    url_candidates_from_columns,
    write_csv,
)
from rewrite_ai_context_gemini import (
    DEFAULT_SYSTEM,
    normalize_source_links,
    render_ai_context,
    validate_markdown,
)


PROMPT_VERSION = "generic-ai-context-batch-v1"
DEFAULT_BATCH_POLICY = """Write one grounded structured markdown brief for every entity.

Return exactly one JSON object with this shape:
{{"results":[{{"id":"stable id","markdown":"...","source_links":["..."]}}]}}

Requirements for every result:
- Return each supplied id exactly once and do not invent ids.
- markdown must be at most 200 words and contain exactly these headings in order:
  what; why; who; for whom; in relation to; what's nice great and superb.
- Format headings as markdown headings. Use plain markdown and no code fences.
- Use only facts in that entity's context. Do not mix evidence across entities.
- Do not put raw URLs in markdown.
- source_links may contain at most four URLs and only from that entity's allowed links.
- If evidence for a section is absent, state "Not explicit in source." briefly.

Entities:
{entities}
"""


def chunks(items: list[dict[str, object]], size: int) -> list[list[dict[str, object]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def usage_from_payload(payload: dict[str, object]) -> dict[str, int]:
    usage = payload.get("_usage_metadata") or {}
    return {key: value for key, value in usage.items() if isinstance(value, int)}


def generate_batch(
    batch: list[dict[str, object]],
    *,
    api_key: str,
    model: str,
    system_instruction: str,
    batch_policy: str,
    max_attempts: int,
    timeout_seconds: int,
    request_delay_seconds: float,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    expected_ids = [str(item["id"]) for item in batch]
    packets = [
        {
            "id": item["id"],
            "context": item["context"],
            "allowed_links": item["allowed_links"],
        }
        for item in batch
    ]
    feedback = ""
    last_error = ""
    for attempt in range(max_attempts):
        prompt = batch_policy.format(entities=json.dumps(packets, ensure_ascii=False))
        if feedback:
            prompt += f"\nFix required after validation failure: {feedback}\n"
        try:
            if request_delay_seconds > 0:
                time.sleep(request_delay_seconds)
            payload = call_gemini_json(
                api_key=api_key,
                model=model,
                system_instruction=system_instruction,
                prompt=prompt,
                timeout_seconds=timeout_seconds,
            )
            results = payload.get("results") or []
            returned_ids = [str(item.get("id", "")) for item in results]
            if (
                len(results) != len(expected_ids)
                or len(set(returned_ids)) != len(expected_ids)
                or set(returned_ids) != set(expected_ids)
            ):
                raise ValueError("Batch did not return every id exactly once")
            by_id = {str(item["id"]): item for item in batch}
            normalized = []
            for result in results:
                item = by_id[str(result["id"])]
                markdown = validate_markdown(str(result.get("markdown", "")))
                links = normalize_source_links(
                    result.get("source_links", []), item["allowed_links"]
                )
                normalized.append(
                    {
                        "id": str(result["id"]),
                        "ai_context": render_ai_context(markdown, links),
                        "raw_response": {
                            "markdown": markdown,
                            "source_links": links,
                        },
                    }
                )
            return normalized, usage_from_payload(payload)
        except (GeminiGenerationError, KeyError, TypeError, ValueError) as exc:
            last_error = str(exc)
            feedback = last_error
            if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error:
                time.sleep(max(request_delay_seconds, min(60, 2 ** attempt)))
    raise GeminiGenerationError(f"Batch failed after validation retries: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch Gemini AI Context rewrites while preserving per-row caches and validation."
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
    parser.add_argument("--system-file", type=Path, default=None)
    parser.add_argument("--batch-policy-file", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--request-delay-seconds", type=float, default=0)
    parser.add_argument("--flush-every-batches", type=int, default=5)
    parser.add_argument("--usage-report", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 12:
        parser.error("--batch-size must be between 1 and 12")
    if args.flush_every_batches < 1:
        parser.error("--flush-every-batches must be a positive integer")

    api_key = require_api_key(args.api_key)
    fieldnames, rows = load_csv(args.input_csv)
    if args.name_column not in fieldnames:
        raise SystemExit(f"Missing required name column: {args.name_column}")
    if args.target_column not in fieldnames:
        fieldnames.append(args.target_column)
        for row in rows:
            row[args.target_column] = ""

    context_columns = choose_context_columns(
        [column for column in fieldnames if column != args.target_column],
        parse_csv_list(args.context_columns),
    )
    link_columns = choose_context_columns(fieldnames, parse_csv_list(args.link_columns))
    if not context_columns:
        raise SystemExit("No context columns available for prompt construction")
    system_instruction = read_optional_text(args.system_file) or DEFAULT_SYSTEM
    batch_policy = read_optional_text(args.batch_policy_file) or DEFAULT_BATCH_POLICY
    selected = rows[: args.limit] if args.limit > 0 else rows
    pending: list[dict[str, object]] = []
    usage_events: list[dict[str, object]] = []
    cache_hits = 0

    for row_index, row in enumerate(selected):
        cache_key = row_cache_key(row, row_index, args.id_column, args.name_column)
        fingerprint = row_source_fingerprint(
            row,
            columns=[*context_columns, *link_columns],
            model=args.model,
            prompt_version=PROMPT_VERSION,
            system_instruction=system_instruction,
            prompt_template=batch_policy,
        )
        cached = None if args.force else load_cached_result(args.cache_dir, cache_key)
        if cached is not None and cached.get("input_fingerprint") == fingerprint:
            row[args.target_column] = cached["ai_context"]
            cache_hits += 1
            continue
        pending.append(
            {
                "id": cache_key,
                "row": row,
                "fingerprint": fingerprint,
                "context": build_context_from_columns(row, context_columns),
                "allowed_links": url_candidates_from_columns(row, link_columns),
            }
        )

    batches = chunks(pending, args.batch_size)
    for batch_index, batch in enumerate(batches, start=1):
        generated, usage = generate_batch(
            batch,
            api_key=api_key,
            model=args.model,
            system_instruction=system_instruction,
            batch_policy=batch_policy,
            max_attempts=args.max_attempts,
            timeout_seconds=args.timeout_seconds,
            request_delay_seconds=args.request_delay_seconds,
        )
        generated_by_id = {item["id"]: item for item in generated}
        for item in batch:
            result = generated_by_id[str(item["id"])]
            item["row"][args.target_column] = result["ai_context"]
            save_cached_result(
                args.cache_dir,
                str(item["id"]),
                {
                    "prompt_version": PROMPT_VERSION,
                    "cache_key": str(item["id"]),
                    "input_fingerprint": item["fingerprint"],
                    "model": args.model,
                    "ai_context": result["ai_context"],
                    "raw_response": result["raw_response"],
                },
            )
        usage_events.append(
            {"ids": [str(item["id"]) for item in batch], "cache_hit": False, "usage": usage}
        )
        if batch_index % args.flush_every_batches == 0 or batch_index == len(batches):
            write_csv(args.output_csv, fieldnames, rows)
            print(f"Generated {min(batch_index * args.batch_size, len(pending))}/{len(pending)} pending rows")

    write_csv(args.output_csv, fieldnames, rows)
    totals: dict[str, int] = {}
    for event in usage_events:
        for key, value in event["usage"].items():
            totals[key] = totals.get(key, 0) + value
    usage_report = args.usage_report or args.cache_dir / "usage-summary.json"
    usage_report.parent.mkdir(parents=True, exist_ok=True)
    usage_report.write_text(
        json.dumps(
            {
                "model": args.model,
                "prompt_version": PROMPT_VERSION,
                "rows": len(selected),
                "pending_rows": len(pending),
                "cache_hits": cache_hits,
                "api_calls": len(batches),
                "batch_size": args.batch_size,
                "usage": totals,
                "events": usage_events,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(selected), "pending": len(pending), "apiCalls": len(batches), "usage": totals}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
