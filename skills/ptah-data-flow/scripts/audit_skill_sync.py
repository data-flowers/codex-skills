#!/usr/bin/env python3
"""Compare a version-controlled skill tree with its installed runtime copy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


IGNORED_DIRS = {"__pycache__"}
IGNORED_FILES = {".DS_Store"}
IGNORED_SUFFIXES = {".pyc"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="Canonical repository skill directory")
    parser.add_argument("--installed", type=Path, required=True, help="Installed runtime skill directory")
    return parser.parse_args()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest(root: Path) -> dict[str, str]:
    if not root.is_dir() or not (root / "SKILL.md").is_file():
        raise ValueError(f"Not a skill directory: {root}")

    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        if not path.is_file() or path.name in IGNORED_FILES or path.suffix in IGNORED_SUFFIXES:
            continue
        result[relative.as_posix()] = file_hash(path)
    return result


def main() -> int:
    args = parse_args()
    try:
        source = manifest(args.source.resolve())
        installed = manifest(args.installed.resolve())
    except ValueError as error:
        print(json.dumps({"error": str(error)}, indent=2))
        return 1

    source_paths = set(source)
    installed_paths = set(installed)
    source_only = sorted(source_paths - installed_paths)
    installed_only = sorted(installed_paths - source_paths)
    changed = sorted(path for path in source_paths & installed_paths if source[path] != installed[path])
    identical = not source_only and not installed_only and not changed

    print(
        json.dumps(
            {
                "identical": identical,
                "sourceFiles": len(source),
                "installedFiles": len(installed),
                "sourceOnly": source_only,
                "installedOnly": installed_only,
                "changed": changed,
            },
            indent=2,
        )
    )
    return 0 if identical else 2


if __name__ == "__main__":
    raise SystemExit(main())
