#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"


class GeminiGenerationError(RuntimeError):
    pass


def require_api_key(cli_value: str | None = None) -> str:
    api_key = normalize_whitespace(cli_value or os.environ.get("GEMINI_API_KEY", ""))
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY or pass --api-key.")
    return api_key


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalized_phrase(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize_whitespace(value).lower()).strip()


def mentions_entity_name(text: str, name: str) -> bool:
    text_norm = normalized_phrase(text)
    name_norm = normalized_phrase(name)
    if not text_norm or not name_norm:
        return False
    if len(name_norm) <= 3:
        return re.search(rf"\b{re.escape(name_norm)}\b", text_norm) is not None
    return name_norm in text_norm


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"&", " and ", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-") or "row"


def row_cache_key(row: dict[str, str], row_index: int, id_column: str, name_column: str) -> str:
    row_id = normalize_whitespace(row.get(id_column, ""))
    if row_id:
        return row_id
    row_name = normalize_whitespace(row.get(name_column, ""))
    if row_name:
        return slugify(row_name)
    return f"row-{row_index + 1}"


def parse_csv_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [normalize_whitespace(part) for part in raw.split(",") if normalize_whitespace(part)]


def choose_context_columns(fieldnames: list[str], requested: list[str]) -> list[str]:
    if requested:
        return [column for column in requested if column in fieldnames]
    return list(fieldnames)


def build_context_from_columns(row: dict[str, str], columns: list[str]) -> str:
    lines: list[str] = []
    for column in columns:
        value = normalize_whitespace(row.get(column, ""))
        if not value:
            continue
        lines.append(f"- {column}: {value}")
    return "\n".join(lines)


def url_candidates_from_columns(row: dict[str, str], columns: list[str]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for column in columns:
        value = normalize_whitespace(row.get(column, ""))
        if not value:
            continue
        for match in re.findall(r"https?://[^\s<>\"]+|www\.[^\s<>\"]+", value):
            candidate = match.rstrip(".,);")
            if candidate.startswith("www."):
                candidate = f"https://{candidate}"
            if candidate not in seen:
                seen.add(candidate)
                urls.append(candidate)
    return urls


def read_optional_text(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.read_text(encoding="utf-8")


def extract_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def call_gemini_json(
    *,
    api_key: str,
    model: str,
    system_instruction: str,
    prompt: str,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GeminiGenerationError(f"Gemini HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise GeminiGenerationError(f"Gemini request failed: {exc}") from exc

    data = json.loads(body)
    candidates = data.get("candidates") or []
    if not candidates:
        raise GeminiGenerationError(f"No candidates returned: {body}")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise GeminiGenerationError(f"Empty text response: {body}")

    try:
        return json.loads(extract_json_text(text))
    except json.JSONDecodeError as exc:
        raise GeminiGenerationError(f"Model did not return valid JSON: {text}") from exc


def cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{slugify(key)}.json"


def load_cached_result(cache_dir: Path, key: str) -> dict[str, Any] | None:
    path = cache_path(cache_dir, key)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_cached_result(cache_dir: Path, key: str, payload: dict[str, Any]) -> None:
    path = cache_path(cache_dir, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def in_shard(key: str, shard_count: int, shard_index: int) -> bool:
    if shard_count < 1:
        raise ValueError("shard_count must be at least 1.")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("shard_index must be between 0 and shard_count - 1.")
    digits = re.sub(r"[^0-9]", "", key)
    numeric = int(digits or "0")
    return numeric % shard_count == shard_index
