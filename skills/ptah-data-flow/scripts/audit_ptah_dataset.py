#!/usr/bin/env python3
"""Audit Ptah canonical, publish-shaped, and Airtable upload datasets."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from gemini_rewrite_common import atomic_write_text, load_csv

CONTRACT = json.loads(Path(__file__).with_name("ptah_contract.json").read_text())


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
TRUE_VALUES = set(CONTRACT["booleans"]["true"])
FALSE_VALUES = set(CONTRACT["booleans"]["false"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--kind", choices=("auto", "canonical", "ptah", "upload", "delta"), default="auto")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--taxonomy", type=Path, help="JSON with version: 1 and categories: {category: [subcategory]}")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-grounding-coverage", type=float, default=0.80)
    parser.add_argument("--require-gate", choices=("none", "taxonomy", "publication"), default="none")
    parser.add_argument(
        "--allow-current-year-founded",
        action="store_true",
        help="Confirm that all current-year founding values in this audited artifact were explicitly reviewed.",
    )
    return parser.parse_args()


def load_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text())
        if isinstance(payload, dict):
            payload = next((payload[key] for key in ("rows", "records", "data") if key in payload), None)
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise ValueError("JSON input must be a row array or contain rows/records/data")
        fields = sorted({key for row in payload for key in row})
        return payload, fields
    fields, rows = load_csv(path)
    return rows, fields


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
    if "id" in fields and "name" in fields:
        return "canonical"
    if "Id" in fields and "Name" in fields:
        return "ptah" if "Logo" in fields or "Updated At" in fields else "upload"
    return "canonical"


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def state_drift(state_path: Path | None, counts: dict[str, int], input_hash: str,
                *, kind: str = "canonical", input_path: Path | None = None) -> dict[str, Any]:
    if not state_path or kind == "delta":
        return {"checked": False, "stale": False, "differences": []}
    state = json.loads(state_path.read_text())
    if state.get("version", 1) not in (1, 2):
        raise ValueError("Unsupported state version")
    role, path_key = {"canonical": ("canonical", "sourceOfTruth"), "ptah": ("publishArtifact", "publishArtifact"),
                      "upload": ("uploadArtifact", "uploadArtifact")}[kind]
    recorded_path = state.get(path_key)
    if input_path and recorded_path and (state_path.parent / recorded_path).resolve() != input_path.resolve():
        return {"checked": False, "stale": False, "differences": [], "reason": "different-artifact", "role": role}
    expected_hash = (state.get("hashes") or {}).get(role)
    if role == "canonical" and expected_hash is None:
        expected_hash = state.get("canonicalHash")
    differences = []
    if kind == "canonical":
        state_counts = state.get("counts") or {}
        for key in ("canonical", "websites", "descriptions", "yearFounded", "aiContext", "categories", "subcategories"):
            if key in state_counts and key in counts and state_counts[key] != counts[key]:
                differences.append({"field": f"counts.{key}", "state": state_counts[key], "actual": counts[key]})
    if expected_hash and expected_hash != input_hash:
        differences.append({"field": f"hashes.{role}", "state": expected_hash, "actual": input_hash})
    return {"checked": True, "stale": bool(differences), "differences": differences,
            "role": role, "hashChecked": bool(expected_hash)}


def contract_shape(rows, fields, kind):
    required = [field["canonical"] if kind == "canonical" else field["name"]
                for field in CONTRACT["fields"] if kind not in ("upload", "delta") or field["upload"]]
    if kind == "delta":
        required = ["Id"]
    return {
        "missingFields": sorted(set(required) - set(fields)),
        "noChangedFields": kind == "delta" and not (set(fields) - {"Id"}),
        "missingFieldRows": [{"row": index + 2, "fields": sorted(set(required) - set(row))}
                             for index, row in enumerate(rows) if set(required) - set(row)],
    }


def load_taxonomy(path):
    if path is None:
        return None
    data = json.loads(path.read_text())
    categories = data.get("categories") if isinstance(data, dict) else None
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(categories, dict) or not categories:
        raise ValueError("Taxonomy requires version 1 and a nonempty categories object")
    for category, subs in categories.items():
        if not category.strip() or not isinstance(subs, list) or not subs or not all(isinstance(sub, str) and sub.strip() for sub in subs):
            raise ValueError("Each taxonomy category must contain nonblank text subcategories")
        if len(set(subs)) != len(subs):
            raise ValueError("Duplicate taxonomy subcategories")
    return {(category, sub) for category, subs in categories.items() for sub in subs}


def main() -> int:
    args = parse_args()
    rows, fields = load_rows(args.input)
    kind = infer_kind(args.kind, fields)
    if kind == "delta" and args.require_gate != "none":
        raise ValueError("Delta validation does not establish whole-dataset readiness")
    shape = contract_shape(rows, fields, kind)
    allowed_pairs = load_taxonomy(args.taxonomy)
    invalid_pairs = []
    for index, row in enumerate(rows):
        category, subs = category_values(row)
        if allowed_pairs is not None and (category or subs):
            if not category or not subs or any((category, sub) not in allowed_pairs for sub in subs):
                invalid_pairs.append({"row": index + 2, "id": text(row, "id", "Id"), "category": category, "subcategories": subs})
    if not 0.0 <= args.min_grounding_coverage <= 1.0:
        raise SystemExit("--min-grounding-coverage must be between 0 and 1")
    has_published_field = "Published" in fields or "published" in fields
    ids = [value(row, "id", "Id") if isinstance(value(row, "id", "Id"), str)
           else str(value(row, "id", "Id") or "") for row in rows]
    names = [text(row, "name", "Name") for row in rows]
    descriptions = [text(row, "description", "Description") for row in rows]
    contexts = [text(row, "aiContext", "AI Context") for row in rows]
    websites = [text(row, "websiteUrl", "Website") for row in rows]
    founding_years = [text(row, "yearFounded", "Year Founded") for row in rows]

    current_year = datetime.now(timezone.utc).year
    invalid_founding_year_rows = []
    future_founding_year_rows = []
    current_year_founding_rows = []
    unreviewed_current_year_founding_rows = []
    for index, raw_year in enumerate(founding_years):
        if not raw_year:
            continue
        record = {"row": index + 2, "id": ids[index], "name": names[index], "value": raw_year}
        if not re.fullmatch(r"\d{4}", raw_year):
            invalid_founding_year_rows.append({**record, "reason": "not-four-digits"})
            continue
        numeric_year = int(raw_year)
        if numeric_year < 1000 or numeric_year > current_year:
            invalid_founding_year_rows.append({**record, "reason": "out-of-range"})
            if numeric_year > current_year:
                future_founding_year_rows.append(record)
            continue
        if numeric_year == current_year:
            reviewed, valid_review = parse_bool(
                value(rows[index], "foundingYearReviewed", "Founding Year Reviewed")
            )
            reviewed = args.allow_current_year_founded or (valid_review and reviewed is True)
            current_record = {**record, "reviewed": reviewed}
            current_year_founding_rows.append(current_record)
            if not reviewed:
                unreviewed_current_year_founding_rows.append(current_record)

    duplicate_ids = sorted(item for item, count in Counter(ids).items() if item and count > 1)
    missing_ids = [index + 2 for index, item in enumerate(ids) if not item.strip()]
    non_text_ids = [
        index + 2
        for index, row in enumerate(rows)
        if ("id" in row or "Id" in row)
        and value(row, "id", "Id") is not None
        and not isinstance(value(row, "id", "Id"), str)
    ]
    missing_names = [index + 2 for index, item in enumerate(names) if not item and (kind != "delta" or "Name" in fields)]

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
        "yearFounded": sum(bool(item) for item in founding_years),
        "aiContext": sum(bool(item) for item in contexts),
        "categories": len(categories),
        "subcategories": len(taxonomy_pairs),
        "subcategoryLabels": len(subcategories),
        "publishedTrue": published_true,
        "eligibleRows": eligible_rows,
        "placeholderCandidates": len(placeholder_rows),
        "currentYearFoundingValues": len(current_year_founding_rows),
    }
    grounding_coverage = grounded_eligible_rows / eligible_rows if eligible_rows else 0.0
    taxonomy_coverage = taxonomy_rows / eligible_rows if eligible_rows else 0.0
    input_hash = sha256(args.input)
    drift = state_drift(args.state, counts, input_hash, kind=kind, input_path=args.input)

    forbidden_upload_fields = [field["name"] for field in CONTRACT["fields"] if kind in ("upload", "delta") and not field["upload"] and field["name"] in fields]
    structural_errors = bool(
        not rows or shape["noChangedFields"] or shape["missingFields"] or shape["missingFieldRows"] or duplicate_ids or missing_ids or missing_names or non_text_ids or invalid_founding_year_rows or invalid_pairs
    )
    upload_errors = bool(forbidden_upload_fields or invalid_published_rows or published_placeholder_rows)
    taxonomy_ready = not structural_errors and grounding_coverage >= args.min_grounding_coverage
    publication_review_required = bool(
        (placeholder_rows and not has_published_field) or unreviewed_current_year_founding_rows
    )
    publication_ready = (
        not structural_errors
        and not upload_errors
        and taxonomy_ready
        and taxonomy_coverage == 1.0
        and not published_generic_description_rows
        and allowed_pairs is not None
        and kind != "delta"
        and not publication_review_required
    )

    evidence_tiers = Counter(text(row, "evidenceTier", "Evidence Tier") or "unverified" for row in rows)
    report = {
        "version": 2,
        "input": str(args.input.resolve()),
        "kind": kind,
        "counts": counts,
        "coverage": {
            "grounding": round(grounding_coverage, 4),
            "descriptionCoverage": round(grounding_coverage, 4),
            "minimumGrounding": args.min_grounding_coverage,
            "taxonomy": round(taxonomy_coverage, 4),
        },
        "evidenceReview": {"status": "unverified" if "unverified" in evidence_tiers else "declared",
                           "tiers": dict(evidence_tiers), "note": "Description coverage and declared tiers do not verify source evidence."},
        "checks": {
            "contractShape": shape,
            "taxonomyDefinitionProvided": allowed_pairs is not None,
            "invalidTaxonomyPairs": invalid_pairs,
            "duplicateIds": duplicate_ids,
            "missingIdRows": missing_ids,
            "nonTextIdRows": non_text_ids,
            "missingNameRows": missing_names,
            "invalidFoundingYearRows": invalid_founding_year_rows,
            "futureFoundingYearRows": future_founding_year_rows,
            "currentYearFoundingRows": current_year_founding_rows,
            "unreviewedCurrentYearFoundingRows": unreviewed_current_year_founding_rows,
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
            "temporalReviewRequired": bool(unreviewed_current_year_founding_rows),
            "publicationReady": publication_ready,
            "taxonomyMembershipVerified": allowed_pairs is not None and not invalid_pairs and taxonomy_coverage == 1.0,
            "required": args.require_gate,
        },
        "categories": dict(categories),
        "subcategories": dict(subcategories),
        "taxonomyPairs": {f"{category} / {subcategory}": count for (category, subcategory), count in taxonomy_pairs.items()},
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(args.output, rendered)
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
                "invalidFoundingYears": len(invalid_founding_year_rows),
                "futureFoundingYears": len(future_founding_year_rows),
                "unreviewedCurrentYearFoundingYears": len(unreviewed_current_year_founding_rows),
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
