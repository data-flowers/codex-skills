#!/usr/bin/env python3
"""Batched AI Context policy using the same runtime and validation as single rows."""
from rewrite_ai_context_gemini import DEFAULT_SYSTEM, validate_result
from rewrite_runtime import run_rewrite

PROMPT_VERSION = "generic-ai-context-batch-v2"
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


def main(argv=None):
    return run_rewrite(target='AI Context', result_field='ai_context', version=PROMPT_VERSION,
                       system=DEFAULT_SYSTEM, template=DEFAULT_BATCH_POLICY, validate=validate_result,
                       batched=True, argv=argv)


if __name__ == '__main__':
    raise SystemExit(main())
