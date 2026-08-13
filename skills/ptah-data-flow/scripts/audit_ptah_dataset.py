#!/usr/bin/env python3
"""Audit Ptah canonical, publish-shaped, and Airtable upload datasets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PLACEHOLDER_NAMES = {
    "n a",
    "na",
    "none",
    "unknown",
    "not applicable",
    "no organisation",
    "no organization",
    "private",
    "privat",
    "student",
    "student innen",
}
NON_ENTITY_TYPE = re.compile(
    r"\b(individual|private|privat|student|no organisation|no organization|person)\b",
    re.IGNORECASE,
)
GENERIC_PLATFORM_TEXT = {
    "linkedin.com": (
        "manage your professional identity",
        "1 billion members",
        "build and engage with your professional network",
    ),
    "facebook.com": ("log into facebook", "connect with friends, family"),
    "instagram.com": ("create an account or log in to instagram",),
    "x.com": ("don’t miss what’s happening", "don't miss what's happening"),
}
TRUE_VALUES = {"1", "true", "yes", "y", "checked"}
FALSE_VALUES = {"", "0", "false", "no", "n", "unchecked"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--kind", choices=("auto", "canonical", "ptah", "upload"), default="auto")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-grounding-coverage", type=float, default=0.80)
    parser.add_argument("--require-gate", choices=("none", "taxonomy", "publication"), default="none")
    return parser.parse_args()


def load_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text())
        if isinstance(payload, dict):
            payload = payload.get("rows") or payload.get("records") or payload.get("data")
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise ValueError("JSON input must be a row array or contain rows/records/data")
        fields = sorted({key for row in payload for key in row})
        return payload, fields
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return ""


def text(row: dict[str, Any], *keys: str) -> str:
    item = value(row, *keys)
    if item is None:
        return ""
    if isinstance(item, list):
        return "; ".join(str(part) for part in item if part is not None)
    return str(item).strip()


def normalized_words(item: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", item.casefold()).strip()


def parse_bool(item: Any) -> tuple[bool | None, bool]:
    if isinstance(item, bool):
        return item, True
    normalized = str(item or "").strip().casefold()
    if normalized in TRUE_VALUES:
        return True, True
    if normalized in FALSE_VALUES:
        return False, True
    return None, False


def category_values(row: dict[str, Any]) -> tuple[str, list[str]]:
    category = text(row, "categoryId", "Category")
    raw = value(row, "subcategories", "Subcategory")
    if isinstance(raw, list):
        subs = [str(item).strip() for item in raw if str(item).strip()]
    else:
        subs = [item.strip() for item in re.split(r"\s*;\s*", str(raw or "")) if item.strip()]
    return category, subs


def source_type_text(row: dict[str, Any]) -> str:
    return text(row, "sourceTypes", "Source Types", "Type", "type")


def infer_kind(requested: str, fields: list[str]) -> str:
    if requested != "auto":
        return requested
    if "Published" in fields:
        return "upload"
    if any(field[:1].isupper() for field in fields):
        return "ptah"
    return "canonical"


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def state_drift(state_path: Path | None, counts: dict[str, int], input_hash: str) -> dict[str, Any]:
    if not state_path:
        return {"checked": False, "stale": False, "differences": []}
    state = json.loads(state_path.read_text())
    state_counts = state.get("counts") or {}
    differences = []
    for key in ("canonical", "websites", "descriptions", "aiContext", "categories", "subcategories"):
        if key in state_counts and state_counts[key] != counts[key]:
            differences.append({"field": f"counts.{key}", "state": state_counts[key], "actual": counts[key]})
    if state.get("canonicalHash") and state["canonicalHash"] != input_hash:
        differences.append({"field": "canonicalHash", "state": state["canonicalHash"], "actual": input_hash})
    return {"checked": True, "stale": bool(differences), "differences": differences}


def main() -> int:
    args = parse_args()
    rows, fields = load_rows(args.input)
    kind = infer_kind(args.kind, fields)
    if not 0.0 <= args.min_grounding_coverage <= 1.0:
        raise SystemExit("--min-grounding-coverage must be between 0 and 1")
    has_published_field = "Published" in fields or "published" in fields
    ids = [text(row, "id", "Id") for row in rows]
    names = [text(row, "name", "Name") for row in rows]
    descriptions = [text(row, "description", "Description") for row in rows]
    contexts = [text(row, "aiContext", "AI Context") for row in rows]
    websites = [text(row, "websiteUrl", "Website") for row in rows]

    duplicate_ids = sorted(item for item, count in Counter(ids).items() if item and count > 1)
    missing_ids = [index + 2 for index, item in enumerate(ids) if not item]
    non_text_ids = [
        index + 2
        for index, row in enumerate(rows)
        if ("id" in row or "Id" in row)
        and value(row, "id", "Id") is not None
        and not isinstance(value(row, "id", "Id"), str)
    ]
    missing_names = [index + 2 for index, item in enumerate(names) if not item]

    placeholder_rows = []
    published_placeholder_rows = []
    invalid_published_rows = []
    published_true = 0
    publication_flags: list[bool] = []
    for index, row in enumerate(rows):
        row_number = index + 2
        normalized_name = normalized_words(names[index])
        source_type = source_type_text(row)
        is_placeholder = normalized_name in PLACEHOLDER_NAMES or bool(NON_ENTITY_TYPE.search(source_type))
        published, valid_published = parse_bool(value(row, "Published", "published"))
        if "Published" in row or "published" in row:
            if not valid_published:
                invalid_published_rows.append(row_number)
            if published:
                published_true += 1
        publication_flags.append(bool(published) if has_published_field else True)
        if is_placeholder:
            record = {"row": row_number, "id": ids[index], "name": names[index], "sourceType": source_type}
            placeholder_rows.append(record)
            if published:
                published_placeholder_rows.append(record)

    orphan_context_rows = [index + 2 for index, (desc, ctx) in enumerate(zip(descriptions, contexts)) if ctx and not desc]
    pending_context_rows = [index + 2 for index, (desc, ctx) in enumerate(zip(descriptions, contexts)) if desc and not ctx]

    generic_description_rows = []
    generic_description_indexes = set()
    normalized_descriptions: defaultdict[str, list[int]] = defaultdict(list)
    for index, (website, description) in enumerate(zip(websites, descriptions)):
        if not description:
            continue
        normalized_descriptions[normalized_words(description)].append(index + 2)
        lowered_website = website.casefold()
        lowered_description = description.casefold()
        for host, fragments in GENERIC_PLATFORM_TEXT.items():
            if host in lowered_website and any(fragment in lowered_description for fragment in fragments):
                generic_description_rows.append(
                    {"row": index + 2, "id": ids[index], "name": names[index], "website": website, "host": host}
                )
                generic_description_indexes.add(index)
                break
    repeated_descriptions = [
        {"rows": row_numbers, "count": len(row_numbers)}
        for normalized, row_numbers in normalized_descriptions.items()
        if normalized and len(row_numbers) >= 3
    ]

    categories = Counter()
    subcategories = Counter()
    taxonomy_pairs = Counter()
    taxonomy_rows = 0
    for index, row in enumerate(rows):
        category, subs = category_values(row)
        if category and publication_flags[index]:
            categories[category] += 1
        if category and subs and publication_flags[index]:
            taxonomy_rows += 1
        if publication_flags[index]:
            subcategories.update(subs)
            taxonomy_pairs.update((category, sub) for sub in subs if category)

    eligible_rows = sum(publication_flags)
    grounded_eligible_rows = sum(
        bool(description) and index not in generic_description_indexes
        for index, (description, eligible) in enumerate(zip(descriptions, publication_flags))
        if eligible
    )
    published_generic_description_rows = [
        record for record in generic_description_rows if publication_flags[record["row"] - 2]
    ]

    counts = {
        "canonical": len(rows),
        "uniqueIds": len(set(item for item in ids if item)),
        "websites": sum(bool(item) for item in websites),
        "descriptions": sum(bool(item) for item in descriptions),
        "aiContext": sum(bool(item) for item in contexts),
        "categories": len(categories),
        "subcategories": len(taxonomy_pairs),
        "subcategoryLabels": len(subcategories),
        "publishedTrue": published_true,
        "eligibleRows": eligible_rows,
        "placeholderCandidates": len(placeholder_rows),
    }
    grounding_coverage = grounded_eligible_rows / eligible_rows if eligible_rows else 0.0
    taxonomy_coverage = taxonomy_rows / eligible_rows if eligible_rows else 0.0
    input_hash = sha256(args.input)
    drift = state_drift(args.state, counts, input_hash)

    forbidden_upload_fields = [field for field in ("Logo", "Updated At") if kind == "upload" and field in fields]
    structural_errors = bool(duplicate_ids or missing_ids or missing_names or non_text_ids)
    upload_errors = bool(forbidden_upload_fields or invalid_published_rows or published_placeholder_rows)
    taxonomy_ready = not structural_errors and grounding_coverage >= args.min_grounding_coverage
    publication_review_required = bool(placeholder_rows and not has_published_field)
    publication_ready = (
        not structural_errors
        and not upload_errors
        and taxonomy_ready
        and taxonomy_coverage == 1.0
        and not published_generic_description_rows
        and not drift["stale"]
        and not publication_review_required
    )

    report = {
        "version": 1,
        "input": str(args.input.resolve()),
        "kind": kind,
        "counts": counts,
        "coverage": {
            "grounding": round(grounding_coverage, 4),
            "minimumGrounding": args.min_grounding_coverage,
            "taxonomy": round(taxonomy_coverage, 4),
        },
        "checks": {
            "duplicateIds": duplicate_ids,
            "missingIdRows": missing_ids,
            "nonTextIdRows": non_text_ids,
            "missingNameRows": missing_names,
            "placeholderCandidates": placeholder_rows,
            "publishedPlaceholderRows": published_placeholder_rows,
            "invalidPublishedRows": invalid_published_rows,
            "genericPlatformDescriptionRows": generic_description_rows,
            "publishedGenericPlatformDescriptionRows": published_generic_description_rows,
            "repeatedDescriptions": repeated_descriptions,
            "orphanAIContextRows": orphan_context_rows,
            "pendingAIContextRows": pending_context_rows,
            "forbiddenUploadFields": forbidden_upload_fields,
            "stateFreshness": drift,
        },
        "gates": {
            "structurallyValid": not structural_errors,
            "taxonomyReady": taxonomy_ready,
            "publicationReviewRequired": publication_review_required,
            "publicationReady": publication_ready,
            "required": args.require_gate,
        },
        "categories": dict(categories),
        "subcategories": dict(subcategories),
        "taxonomyPairs": {f"{category} / {subcategory}": count for (category, subcategory), count in taxonomy_pairs.items()},
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
        summary = {
            "input": report["input"],
            "kind": kind,
            "counts": counts,
            "gates": report["gates"],
            "findings": {
                "duplicateIds": len(duplicate_ids),
                "placeholderCandidates": len(placeholder_rows),
                "publishedPlaceholders": len(published_placeholder_rows),
                "genericPlatformDescriptions": len(generic_description_rows),
                "publishedGenericPlatformDescriptions": len(published_generic_description_rows),
                "repeatedDescriptions": len(repeated_descriptions),
                "stateDifferences": len(drift["differences"]),
            },
            "report": str(args.output.resolve()),
        }
        sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(rendered)
    if structural_errors or upload_errors:
        return 2
    if args.require_gate == "taxonomy" and not taxonomy_ready:
        return 3
    if args.require_gate == "publication" and not publication_ready:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
