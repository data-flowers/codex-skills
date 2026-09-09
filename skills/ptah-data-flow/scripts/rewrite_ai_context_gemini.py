#!/usr/bin/env python3
"""AI Context policy; links remain in provenance rather than the published body."""
import re
from gemini_rewrite_common import normalize_whitespace, word_count
from rewrite_runtime import run_rewrite

PROMPT_VERSION = "generic-ai-context-v2"

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
    if "```" in text or re.search(r"\[[^\]]*\]\([^)]+\)", text):
        raise ValueError("Markdown body contains code fences or links.")
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


def render_ai_context(markdown, links):
    return validate_markdown(markdown)


def validate_result(payload, name, allowed_links):
    if not isinstance(payload.get('markdown'), str):
        raise ValueError('markdown must be text')
    markdown = validate_markdown(payload['markdown'])
    links = normalize_source_links(payload.get('source_links', []), allowed_links)
    return render_ai_context(markdown, links), {'markdown': markdown, 'source_links': links}


def main(argv=None):
    return run_rewrite(target='AI Context', result_field='ai_context', version=PROMPT_VERSION,
                       system=DEFAULT_SYSTEM, template=DEFAULT_PROMPT, validate=validate_result, argv=argv)


if __name__ == '__main__':
    raise SystemExit(main())
