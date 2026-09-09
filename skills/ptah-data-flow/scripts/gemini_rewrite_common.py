#!/usr/bin/env python3

from __future__ import annotations

import csv
import io
import tempfile
import warnings
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"


class GeminiGenerationError(RuntimeError):
    def __init__(self, message: str, *, usage=None, status=None):
        super().__init__(message)
        self.usage = usage
        self.status = status


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding=encoding, newline="", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)



def require_api_key(cli_value: str | None = None) -> str:
    api_key = normalize_whitespace(cli_value or os.environ.get("GEMINI_API_KEY", ""))
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY or pass --api-key.")
    return api_key


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        if not fields or any(not field for field in fields) or len(set(fields)) != len(fields):
            raise ValueError("CSV headers must be nonblank and unique")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError("CSV row width does not match its header")
        return fields, rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    atomic_write_text(path, buffer.getvalue(), encoding="utf-8-sig")


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
    row_id = row.get(id_column, "")
    if not isinstance(row_id, str) or not row_id.strip():
        raise ValueError(f"Row {row_index + 1} requires a nonblank text {id_column}")
    return row_id


def row_source_fingerprint(
    row: dict[str, str],
    *,
    columns: list[str],
    model: str,
    prompt_version: str,
    system_instruction: str,
    prompt_template: str,
) -> str:
    payload = {
        "model": model,
        "prompt_version": prompt_version,
        "system_instruction": system_instruction,
        "prompt_template": prompt_template,
        "fields": {
            column: row.get(column, "")
            for column in sorted(set(columns))
        },
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_csv_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [normalize_whitespace(part) for part in raw.split(",") if normalize_whitespace(part)]


def choose_context_columns(fieldnames: list[str], requested: list[str], *, required: bool = False) -> list[str]:
    if required and not requested:
        raise ValueError("--context-columns is required; select approved public fields explicitly")
    missing = sorted(set(requested) - set(fieldnames))
    if missing:
        raise ValueError("Columns not found in input: " + ", ".join(missing))
    return list(dict.fromkeys(requested))


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
        raise GeminiGenerationError(f"Gemini HTTP {exc.code}: {detail}", status=exc.code) from exc
    except (error.URLError, TimeoutError) as exc:
        raise GeminiGenerationError(f"Gemini request failed: {exc}") from exc

    try:
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Response is not an object")
    except ValueError as exc:
        raise GeminiGenerationError("Gemini returned an invalid response envelope") from exc
    usage = data.get("usageMetadata")
    candidates = data.get("candidates") or []
    if not candidates:
        raise GeminiGenerationError("No candidates returned", usage=usage)

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise GeminiGenerationError("Empty text response", usage=usage)

    try:
        parsed = json.loads(extract_json_text(text))
    except json.JSONDecodeError as exc:
        raise GeminiGenerationError("Model did not return valid JSON", usage=usage) from exc
    if not isinstance(parsed, dict):
        raise GeminiGenerationError("Model returned JSON, but the top level was not an object.", usage=usage)
    parsed["_usage_metadata"] = usage
    parsed["_model_version"] = data.get("modelVersion") or model
    parsed["_response_id"] = data.get("responseId") or ""
    return parsed


def cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}.json"


def load_cached_result(cache_dir: Path, key: str) -> dict[str, Any] | None:
    path = cache_path(cache_dir, key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("cache_key") != key:
            raise ValueError("Cache identity mismatch")
        return payload
    except (ValueError, OSError):
        warnings.warn(f"Ignoring invalid cache file: {path}")
        return None


def save_cached_result(cache_dir: Path, key: str, payload: dict[str, Any]) -> None:
    payload = {**payload, "cache_key": key}
    atomic_write_text(cache_path(cache_dir, key), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def in_shard(key: str, shard_count: int, shard_index: int) -> bool:
    if shard_count < 1:
        raise ValueError("shard_count must be at least 1.")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("shard_index must be between 0 and shard_count - 1.")
    numeric = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest(), "big")
    return numeric % shard_count == shard_index
