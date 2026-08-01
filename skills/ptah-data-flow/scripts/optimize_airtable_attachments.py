#!/usr/bin/env python3
"""Optimize Ptah CSV image sources and safely replace Airtable attachments."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://api.airtable.com/v0"
CONTENT_ROOT = "https://content.airtable.com/v0"
USER_AGENT = "PtahAttachmentOptimizer/1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:56] or "image"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def request_bytes(url: str, attempts: int = 4) -> tuple[bytes, str]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=60) as response:
                value = response.read()
                if not value:
                    raise RuntimeError("empty response")
                return value, response.headers.get_content_type()
        except (HTTPError, URLError, TimeoutError, RuntimeError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Unable to fetch {url}: {last_error}")


def request_json(
    url: str,
    token: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    attempts: int = 5,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = Request(
            url,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504}:
                detail = error.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"Airtable {method} failed ({error.code}): {detail}"
                ) from error
            last_error = error
        except (URLError, TimeoutError) as error:
            last_error = error
        if attempt + 1 < attempts:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Airtable {method} failed: {last_error}")


def identify(magick: str, path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            magick,
            "identify",
            "-format",
            "%m|%w|%h|%[opaque]|%[channels]",
            f"{path}[0]",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    image_format, width, height, opaque, channels = result.stdout.strip().split("|")
    return {
        "format": image_format,
        "width": int(width),
        "height": int(height),
        "opaque": opaque.casefold() == "true",
        "channels": channels.strip(),
    }


def source_bytes(source: str, source_root: Path) -> tuple[bytes, str]:
    if source.startswith(("https://", "http://")):
        return request_bytes(source)
    path = Path(source)
    if not path.is_absolute():
        path = source_root / path
    value = path.read_bytes()
    return value, mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def optimize_one(
    row: dict[str, str],
    *,
    id_field: str,
    name_field: str,
    source_field: str,
    source_root: Path,
    output_dir: Path,
    temp_dir: Path,
    magick: str,
    max_dimension: int,
    quality: int,
    require_opaque: bool,
) -> dict[str, Any]:
    stable_id = row[id_field].strip()
    name = row.get(name_field, "").strip() or stable_id
    source = row[source_field].strip()
    original, content_type = source_bytes(source, source_root)
    source_hash = sha256(original)
    input_path = temp_dir / f"{slugify(stable_id)}-{source_hash[:12]}.source"
    input_path.write_bytes(original)
    original_info = identify(magick, input_path)
    filename = (
        f"{slugify(stable_id)}-{slugify(name)}-{source_hash[:12]}.webp"
    )
    output_path = output_dir / filename
    subprocess.run(
        [
            magick,
            f"{input_path}[0]",
            "-auto-orient",
            "-colorspace",
            "sRGB",
            "-resize",
            f"{max_dimension}x{max_dimension}>",
            "-strip",
            "-quality",
            str(quality),
            "-define",
            "webp:method=6",
            output_path,
        ],
        check=True,
        capture_output=True,
    )
    optimized = output_path.read_bytes()
    optimized_info = identify(magick, output_path)
    if optimized_info["format"].upper() != "WEBP":
        raise RuntimeError("ImageMagick output is not WebP")
    if max(optimized_info["width"], optimized_info["height"]) > max_dimension:
        raise RuntimeError("ImageMagick output exceeds the configured maximum")
    if require_opaque and not optimized_info["opaque"]:
        raise RuntimeError(
            "Optimized image is not fully opaque; composite the mark onto a "
            "contrast-safe background before publishing"
        )
    return {
        "id": stable_id,
        "name": name,
        "source": source,
        "sourceContentType": content_type,
        "original": {
            **original_info,
            "bytes": len(original),
            "sha256": source_hash,
        },
        "optimized": {
            **optimized_info,
            "contentType": "image/webp",
            "bytes": len(optimized),
            "sha256": sha256(optimized),
            "filename": filename,
            "path": str(output_path.resolve()),
        },
        "savedBytes": len(original) - len(optimized),
        "compressionPercent": round(
            (1 - len(optimized) / len(original)) * 100,
            2,
        ),
    }


def prepare(args: argparse.Namespace, rows: list[dict[str, str]]) -> dict[str, Any]:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    targets = [row for row in rows if row.get(args.source_field, "").strip()]
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="ptah-images-") as temp_name:
        temp_dir = Path(temp_name)
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    optimize_one,
                    row,
                    id_field=args.id_field,
                    name_field=args.name_field,
                    source_field=args.source_field,
                    source_root=args.source_root,
                    output_dir=args.output_dir,
                    temp_dir=temp_dir,
                    magick=args.magick,
                    max_dimension=args.max_dimension,
                    quality=args.quality,
                    require_opaque=args.require_opaque,
                ): row
                for row in targets
            }
            for index, future in enumerate(as_completed(futures), start=1):
                row = futures[future]
                try:
                    results.append(future.result())
                except Exception as error:  # noqa: BLE001
                    errors.append(
                        {
                            "id": row.get(args.id_field, ""),
                            "name": row.get(args.name_field, ""),
                            "source": row.get(args.source_field, ""),
                            "error": str(error),
                        }
                    )
                if index % 10 == 0 or index == len(targets):
                    print(f"Prepared {index}/{len(targets)} images", flush=True)
    results.sort(key=lambda item: item["id"])
    original_bytes = sum(item["original"]["bytes"] for item in results)
    optimized_bytes = sum(item["optimized"]["bytes"] for item in results)
    manifest = {
        "generatedAt": now_iso(),
        "input": str(args.input.resolve()),
        "imageMagick": subprocess.run(
            [args.magick, "-version"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()[0],
        "policy": {
            "maximumWidth": args.max_dimension,
            "maximumHeight": args.max_dimension,
            "format": "WebP",
            "quality": args.quality,
            "autoOrient": True,
            "stripMetadata": True,
            "preserveAspectRatio": True,
            "upscale": False,
            "requireOpaque": args.require_opaque,
        },
        "sourceCount": len(targets),
        "processedCount": len(results),
        "errorCount": len(errors),
        "errors": errors,
        "originalBytes": original_bytes,
        "optimizedBytes": optimized_bytes,
        "savedBytes": original_bytes - optimized_bytes,
        "compressionPercent": round(
            (1 - optimized_bytes / original_bytes) * 100,
            2,
        )
        if original_bytes
        else 0,
        "images": results,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def reuse_manifest(
    args: argparse.Namespace,
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected = {
        row[args.id_field].strip()
        for row in rows
        if row.get(args.source_field, "").strip()
    }
    actual = {image["id"] for image in manifest.get("images", [])}
    if expected != actual or manifest.get("errorCount"):
        raise RuntimeError("Manifest does not cleanly match the input dataset")
    for image in manifest["images"]:
        path = Path(image["optimized"]["path"])
        value = path.read_bytes()
        if (
            len(value) != image["optimized"]["bytes"]
            or sha256(value) != image["optimized"]["sha256"]
        ):
            raise RuntimeError(f"Manifest integrity check failed: {path}")
        info = identify(args.magick, path)
        if (
            info["format"].upper() != "WEBP"
            or max(info["width"], info["height"]) > args.max_dimension
            or (args.require_opaque and not info["opaque"])
        ):
            raise RuntimeError(f"Manifest image check failed: {path}")
    return manifest


def fetch_records(args: argparse.Namespace, token: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = ""
    while True:
        query = {"pageSize": "100"}
        if args.view:
            query["view"] = args.view
        if offset:
            query["offset"] = offset
        payload = request_json(
            f"{API_ROOT}/{args.base}/{args.table}?{urlencode(query)}",
            token,
        )
        records.extend(payload.get("records", []))
        offset = str(payload.get("offset", ""))
        if not offset:
            return records


def fetch_record(
    args: argparse.Namespace,
    token: str,
    record_id: str,
) -> dict[str, Any]:
    return request_json(
        f"{API_ROOT}/{args.base}/{args.table}/{record_id}",
        token,
    )


def snapshot(args: argparse.Namespace, record: dict[str, Any]) -> dict[str, Any]:
    fields = dict(record.get("fields", {}))
    fields.pop(args.attachment_field, None)
    for field in args.ignore_field:
        fields.pop(field, None)
    return fields


def signature(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in ("id", "filename", "type", "size", "width", "height")
    }


def is_current(
    args: argparse.Namespace,
    attachments: list[dict[str, Any]],
    image: dict[str, Any],
) -> bool:
    if len(attachments) != 1:
        return False
    item = attachments[0]
    optimized = image["optimized"]
    return (
        item.get("filename") == optimized["filename"]
        and item.get("type") == "image/webp"
        and item.get("size") == optimized["bytes"]
        and int(item.get("width") or 0) <= args.max_dimension
        and int(item.get("height") or 0) <= args.max_dimension
    )


def verify_served_attachment(
    attachment: dict[str, Any],
    image: dict[str, Any],
    *,
    magick: str,
    require_opaque: bool,
) -> dict[str, Any]:
    url = str(attachment.get("url") or "")
    if not url:
        raise RuntimeError("Airtable attachment is missing its served URL")
    value, content_type = request_bytes(url)
    served_hash = sha256(value)
    optimized = image["optimized"]
    if served_hash != optimized["sha256"]:
        raise RuntimeError(
            "Airtable-served attachment bytes do not match the reviewed "
            f"optimized asset for {image['id']}"
        )
    result = {
        "bytes": len(value),
        "sha256": served_hash,
        "contentType": content_type,
        "matchesReviewedAsset": True,
    }
    thumbnail = (attachment.get("thumbnails") or {}).get("large") or {}
    thumbnail_url = str(thumbnail.get("url") or "")
    if thumbnail_url:
        thumbnail_value, thumbnail_type = request_bytes(thumbnail_url)
        with tempfile.TemporaryDirectory(prefix="ptah-thumbnail-") as temp_name:
            thumbnail_path = Path(temp_name) / "thumbnail"
            thumbnail_path.write_bytes(thumbnail_value)
            thumbnail_info = identify(magick, thumbnail_path)
        if require_opaque and not thumbnail_info["opaque"]:
            raise RuntimeError(
                "Airtable-served thumbnail retained transparency for a "
                f"contrast-backed asset: {image['id']}"
            )
        result["thumbnail"] = {
            **thumbnail_info,
            "bytes": len(thumbnail_value),
            "sha256": sha256(thumbnail_value),
            "contentType": thumbnail_type,
        }
    return result


def replace_one(
    args: argparse.Namespace,
    token: str,
    record: dict[str, Any],
    image: dict[str, Any],
) -> dict[str, Any]:
    record_id = record["id"]
    before = record.get("fields", {}).get(args.attachment_field) or []
    before_ids = {item.get("id") for item in before}
    optimized = image["optimized"]
    path = Path(optimized["path"])
    upload_url = (
        f"{CONTENT_ROOT}/{args.base}/{record_id}/"
        f"{quote(args.attachment_field, safe='')}/uploadAttachment"
    )
    request_json(
        upload_url,
        token,
        method="POST",
        payload={
            "contentType": "image/webp",
            "file": base64.b64encode(path.read_bytes()).decode("ascii"),
            "filename": optimized["filename"],
        },
    )
    uploaded = fetch_record(args, token, record_id)
    candidates = [
        item
        for item in uploaded.get("fields", {}).get(args.attachment_field) or []
        if item.get("id") not in before_ids
        and item.get("filename") == optimized["filename"]
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            f"Expected one new attachment, found {len(candidates)}"
        )
    request_json(
        f"{API_ROOT}/{args.base}/{args.table}/{record_id}",
        token,
        method="PATCH",
        payload={
            "fields": {
                args.attachment_field: [{"id": candidates[0]["id"]}]
            }
        },
    )
    final = fetch_record(args, token, record_id)
    final_attachments = (
        final.get("fields", {}).get(args.attachment_field) or []
    )
    if not is_current(args, final_attachments, image):
        raise RuntimeError(
            f"Final attachment mismatch: "
            f"{[signature(item) for item in final_attachments]}"
        )
    if snapshot(args, record) != snapshot(args, final):
        raise RuntimeError("An unrelated Airtable field changed")
    served = verify_served_attachment(
        final_attachments[0],
        image,
        magick=args.magick,
        require_opaque=args.require_opaque,
    )
    return {
        "id": image["id"],
        "name": image["name"],
        "airtableRecordId": record_id,
        "before": [signature(item) for item in before],
        "after": [signature(item) for item in final_attachments],
        "served": served,
        "status": "replaced",
    }


def sync(
    args: argparse.Namespace,
    token: str,
    rows: list[dict[str, str]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    before = fetch_records(args, token)
    remote_by_id: dict[str, dict[str, Any]] = {}
    for record in before:
        value = record.get("fields", {}).get(args.id_field)
        if value is not None:
            remote_by_id[str(value)] = record
    local_ids = {row[args.id_field].strip() for row in rows}
    if not local_ids.issubset(remote_by_id):
        missing = sorted(local_ids - set(remote_by_id))
        raise RuntimeError(f"Airtable is missing local ids: {missing[:10]}")

    images = list(manifest["images"])
    if args.only:
        needle = args.only.casefold()
        images = [
            image
            for image in images
            if image["id"] == args.only
            or needle in image["name"].casefold()
        ]
        if len(images) != 1:
            raise RuntimeError(f"--only matched {len(images)} images")

    before_snapshots = {
        record["id"]: snapshot(args, record) for record in before
    }
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for index, image in enumerate(images, start=1):
        record = remote_by_id[image["id"]]
        attachments = (
            record.get("fields", {}).get(args.attachment_field) or []
        )
        if not args.force and is_current(args, attachments, image):
            served = verify_served_attachment(
                attachments[0],
                image,
                magick=args.magick,
                require_opaque=args.require_opaque,
            )
            results.append(
                {
                    "id": image["id"],
                    "name": image["name"],
                    "airtableRecordId": record["id"],
                    "before": [signature(item) for item in attachments],
                    "after": [signature(item) for item in attachments],
                    "served": served,
                    "status": "already-current",
                }
            )
        else:
            try:
                results.append(replace_one(args, token, record, image))
            except Exception as error:  # noqa: BLE001
                failures.append(
                    {
                        "id": image["id"],
                        "name": image["name"],
                        "error": str(error),
                    }
                )
                break
        print(f"Synced {index}/{len(images)} attachments", flush=True)
        if index < len(images):
            time.sleep(0.25)

    after = fetch_records(args, token)
    after_snapshots = {
        record["id"]: snapshot(args, record) for record in after
    }
    preservation_mismatches = [
        record_id
        for record_id, value in before_snapshots.items()
        if value != after_snapshots.get(record_id)
    ]
    after_by_id = {
        str(record.get("fields", {}).get(args.id_field)): record
        for record in after
        if record.get("fields", {}).get(args.id_field) is not None
    }
    attachment_mismatches = []
    for image in images:
        attachments = (
            after_by_id.get(image["id"], {})
            .get("fields", {})
            .get(args.attachment_field)
            or []
        )
        if not is_current(args, attachments, image):
            attachment_mismatches.append(image["id"])

    report = {
        "verifiedAt": now_iso(),
        "baseId": args.base,
        "tableId": args.table,
        "viewId": args.view,
        "attachmentField": args.attachment_field,
        "recordCountBefore": len(before),
        "recordCountAfter": len(after),
        "targetCount": len(images),
        "replacedCount": sum(
            result["status"] == "replaced" for result in results
        ),
        "alreadyCurrentCount": sum(
            result["status"] == "already-current" for result in results
        ),
        "failureCount": len(failures),
        "failures": failures,
        "preservationMismatchCount": len(preservation_mismatches),
        "preservationMismatchRecordIds": preservation_mismatches,
        "attachmentMismatchCount": len(attachment_mismatches),
        "attachmentMismatchIds": attachment_mismatches,
        "results": results,
        "verified": (
            len(before) == len(after)
            and not failures
            and not preservation_mismatches
            and not attachment_mismatches
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Optimize Ptah CSV image sources and optionally replace only the "
            "matching Airtable attachment fields."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--id-field", default="Id")
    parser.add_argument("--name-field", default="Name")
    parser.add_argument("--source-field", default="Logo")
    parser.add_argument("--attachment-field", default="Logo")
    parser.add_argument("--max-dimension", type=int, default=512)
    parser.add_argument("--quality", type=int, default=84)
    parser.add_argument(
        "--require-opaque",
        action="store_true",
        help=(
            "Fail preparation or manifest reuse when an optimized image retains "
            "transparency; use for contrast-backed white or translucent marks."
        ),
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--magick", default=shutil.which("magick") or "")
    parser.add_argument("--reuse-manifest", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--only", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--base", default="")
    parser.add_argument("--table", default="")
    parser.add_argument("--view", default="")
    parser.add_argument("--token-env", default="AIRTABLE_TOKEN")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--ignore-field",
        action="append",
        default=["Updated At"],
        help="Field excluded from preservation comparison; repeat as needed.",
    )
    args = parser.parse_args()
    if not args.magick:
        parser.error("ImageMagick 'magick' was not found")
    if not 64 <= args.max_dimension <= 4096:
        parser.error("--max-dimension must be between 64 and 4096")
    if not 1 <= args.quality <= 100:
        parser.error("--quality must be between 1 and 100")
    if not 1 <= args.workers <= 12:
        parser.error("--workers must be between 1 and 12")
    if args.only and not args.execute:
        parser.error("--only requires --execute")
    if args.execute and (not args.base or not args.table):
        parser.error("--execute requires --base and --table")
    args.input = args.input.resolve()
    args.output_dir = args.output_dir.resolve()
    args.manifest = args.manifest.resolve()
    args.source_root = args.source_root.resolve()
    args.report = (
        args.report.resolve()
        if args.report
        else args.manifest.with_name(
            f"{args.manifest.stem}.airtable-verification.json"
        )
    )
    return args


def main() -> int:
    args = parse_args()
    with args.input.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    required = {args.id_field, args.name_field, args.source_field}
    if not rows or not required.issubset(rows[0]):
        raise SystemExit(
            f"Input must contain {sorted(required)} and at least one row"
        )
    ids = [row[args.id_field].strip() for row in rows]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise SystemExit("Input ids must be nonblank and unique")

    manifest = (
        reuse_manifest(args, rows)
        if args.reuse_manifest
        else prepare(args, rows)
    )
    summary = {
        key: manifest[key]
        for key in (
            "sourceCount",
            "processedCount",
            "errorCount",
            "originalBytes",
            "optimizedBytes",
            "savedBytes",
            "compressionPercent",
        )
    }
    print(json.dumps(summary, indent=2))
    if manifest["errorCount"]:
        return 1
    if not args.execute:
        return 0

    load_env(args.env_file)
    token = os.environ.get(args.token_env, "")
    if not token:
        raise SystemExit(
            f"{args.token_env} is missing from the environment or {args.env_file}"
        )
    report = sync(args, token, rows, manifest)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "results"},
            indent=2,
        )
    )
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
