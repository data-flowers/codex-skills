#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def identify(magick: str, path: Path) -> dict[str, object]:
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


def build_card(args: argparse.Namespace, source: Path, output: Path) -> None:
    frame_width = args.outer_keyline_width + args.inner_keyline_width
    interior = args.size - (2 * frame_width)
    if interior <= 0:
        raise SystemExit("Keylines leave no room for the logo card interior.")
    if args.mark_size <= 0 or args.mark_size > interior:
        raise SystemExit(f"--mark-size must be between 1 and {interior}.")

    output.parent.mkdir(parents=True, exist_ok=True)
    outer_end = args.size - args.outer_keyline_width - 1
    interior_end = args.size - frame_width - 1
    source_geometry = (
        f"{interior}x{interior}>"
        if args.input_mode == "card"
        else f"{args.mark_size}x{args.mark_size}>"
    )
    command = [
        args.magick,
        "-size",
        f"{args.size}x{args.size}",
        f"xc:{args.outer_keyline}",
        "-fill",
        args.inner_keyline,
        "-draw",
        (
            f"rectangle {args.outer_keyline_width},{args.outer_keyline_width} "
            f"{outer_end},{outer_end}"
        ),
        "-fill",
        args.background,
        "-draw",
        f"rectangle {frame_width},{frame_width} {interior_end},{interior_end}",
        "(",
        f"{source}[0]",
        "-auto-orient",
        "-colorspace",
        "sRGB",
        "-resize",
        source_geometry,
        ")",
        "-gravity",
        "center",
        "-compose",
        "over",
        "-composite",
        "-alpha",
        "off",
        "-colorspace",
        "sRGB",
        "-strip",
    ]
    if output.suffix.casefold() == ".webp":
        command.extend(["-quality", str(args.quality), "-define", "webp:method=6"])
    command.append(str(output))
    subprocess.run(command, check=True)


def build_qa(args: argparse.Namespace, output: Path, qa_output: Path) -> None:
    qa_output.parent.mkdir(parents=True, exist_ok=True)
    preview = min(args.qa_preview_size, args.size)
    panel_width = preview + 128
    panel_height = preview + args.thumbnail_size + 176
    thumbnail_x = (panel_width - args.thumbnail_size) // 2
    thumbnail_y = preview + 112
    command = [
        args.magick,
        "-size",
        f"{panel_width * 2}x{panel_height}",
        "xc:#ffffff",
        "-fill",
        "#000000",
        "-draw",
        f"rectangle {panel_width},0 {panel_width * 2 - 1},{panel_height - 1}",
        "(",
        str(output),
        "-resize",
        f"{preview}x{preview}",
        ")",
        "-geometry",
        "+64+64",
        "-composite",
        "(",
        str(output),
        "-resize",
        f"{preview}x{preview}",
        ")",
        "-geometry",
        f"+{panel_width + 64}+64",
        "-composite",
        "(",
        str(output),
        "-resize",
        f"{args.thumbnail_size}x{args.thumbnail_size}",
        ")",
        "-geometry",
        f"+{thumbnail_x}+{thumbnail_y}",
        "-composite",
        "(",
        str(output),
        "-resize",
        f"{args.thumbnail_size}x{args.thumbnail_size}",
        ")",
        "-geometry",
        f"+{panel_width + thumbnail_x}+{thumbnail_y}",
        "-composite",
        str(qa_output),
    ]
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a fully opaque logo card with dual white/black keylines so "
            "its edge remains visible on either white or black surfaces."
        )
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--background", required=True)
    parser.add_argument("--input-mode", choices=["mark", "card"], default="mark")
    parser.add_argument("--size", type=int, default=256)
    parser.add_argument("--mark-size", type=int)
    parser.add_argument("--outer-keyline", default="#ffffff")
    parser.add_argument("--inner-keyline", default="#000000")
    parser.add_argument("--outer-keyline-width", type=int)
    parser.add_argument("--inner-keyline-width", type=int)
    parser.add_argument("--quality", type=int, default=84)
    parser.add_argument("--qa-output")
    parser.add_argument("--qa-preview-size", type=int)
    parser.add_argument("--thumbnail-size", type=int, default=36)
    parser.add_argument("--magick", default=shutil.which("magick") or "")
    args = parser.parse_args()

    if not args.magick:
        raise SystemExit("ImageMagick `magick` was not found.")
    if args.size <= 0:
        raise SystemExit("--size must be positive.")
    if args.mark_size is None:
        args.mark_size = round(args.size * 0.625)
    if args.outer_keyline_width is None:
        args.outer_keyline_width = max(1, round(args.size * 0.047))
    if args.inner_keyline_width is None:
        args.inner_keyline_width = max(1, round(args.size * 0.047))
    if args.qa_preview_size is None:
        args.qa_preview_size = min(args.size, 320)
    if args.outer_keyline_width <= 0 or args.inner_keyline_width <= 0:
        raise SystemExit("Both keyline widths must be positive.")
    if args.qa_preview_size <= 0:
        raise SystemExit("--qa-preview-size must be positive.")
    if args.thumbnail_size <= 0 or args.thumbnail_size > args.size:
        raise SystemExit("--thumbnail-size must be positive and no larger than --size.")

    source = Path(args.input).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Input image not found: {source}")

    build_card(args, source, output)
    output_info = identify(args.magick, output)
    if output_info["width"] != args.size or output_info["height"] != args.size:
        raise SystemExit("Output dimensions do not match --size.")
    if not output_info["opaque"]:
        raise SystemExit("Output is not fully opaque.")

    qa_output = None
    if args.qa_output:
        qa_output = Path(args.qa_output).expanduser().resolve()
        build_qa(args, output, qa_output)

    print(
        json.dumps(
            {
                "input": str(source),
                "output": str(output),
                "outputInfo": output_info,
                "qaOutput": str(qa_output) if qa_output else None,
                "policy": {
                    "size": args.size,
                    "markSize": args.mark_size,
                    "background": args.background,
                    "outerKeyline": args.outer_keyline,
                    "innerKeyline": args.inner_keyline,
                    "outerKeylineWidth": args.outer_keyline_width,
                    "innerKeylineWidth": args.inner_keyline_width,
                    "inputMode": args.input_mode,
                    "qaPreviewSize": args.qa_preview_size,
                    "thumbnailSize": args.thumbnail_size,
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
