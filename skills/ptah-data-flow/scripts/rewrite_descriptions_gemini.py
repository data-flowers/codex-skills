#!/usr/bin/env python3
"""Description policy; execution is shared with the AI Context runners."""
from gemini_rewrite_common import mentions_entity_name, normalize_whitespace, word_count
from rewrite_runtime import run_rewrite

PROMPT_VERSION = "generic-description-v2"

DEFAULT_SYSTEM = """You rewrite Airtable-style entity descriptions for a curated map.
Stay strictly grounded in the provided context.
Return valid JSON only."""

DEFAULT_PROMPT = """# Task
Rewrite the `{target_column}` field for one entity.

# Hard constraints
- Return exactly one JSON object with this shape: {{"description":"..."}}.
- Output exactly one sentence.
- Prefer 12 to 22 words. Hard max 28 words.
- Do not include the entity name, any URL, markdown, quotes, source notes, or emojis.
- Keep the sentence dense, neutral, polished, and visually consistent with other cards.
- Make it specific enough to differentiate the entity from nearby cards.
- Use only facts explicitly supported by the context. Do not guess.

# Notes
- Adapt this prompt if your dataset has a specific style policy.
- If your dataset distinguishes companies, investors, people, or projects, update the instructions accordingly.

# Entity context
{context}
"""


def validate_description(candidate: str, name: str) -> str:
    text = normalize_whitespace(candidate).strip("\"' ")
    if not text:
        raise ValueError("Description is empty.")
    if "http://" in text.lower() or "https://" in text.lower() or "www." in text.lower():
        raise ValueError("Description contains a URL.")
    if name and mentions_entity_name(text, name):
        raise ValueError("Description contains the entity name.")
    if "\n" in candidate:
        raise ValueError("Description contains a newline.")
    if word_count(text) < 8 or word_count(text) > 28:
        raise ValueError("Description is outside the target word range.")
    if len(text) > 180:
        raise ValueError("Description is too long.")
    sentence_breaks = sum(text.count(mark) for mark in [".", "!", "?"])
    if sentence_breaks > 1:
        raise ValueError("Description is not a single sentence.")
    if text[-1] not in ".!?":
        text = f"{text}."
    return text


def validate_result(payload, name, links):
    value = payload.get('description')
    if not isinstance(value, str):
        raise ValueError('description must be text')
    value = validate_description(value, name)
    return value, {'description': value}


def main(argv=None):
    return run_rewrite(target='Description', result_field='description', version=PROMPT_VERSION,
                       system=DEFAULT_SYSTEM, template=DEFAULT_PROMPT, validate=validate_result, argv=argv)


if __name__ == '__main__':
    raise SystemExit(main())
