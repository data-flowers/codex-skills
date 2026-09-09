"""Shared, restartable execution for the three Ptah rewrite entrypoints."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import threading
import time
import uuid

import gemini_rewrite_common as common


@dataclass
class Job:
    key: str
    row: dict
    fingerprint: str
    context: str
    links: list[str]


def parse_args(*, target: str, batched: bool, argv=None):
    parser = argparse.ArgumentParser(description=f"Rewrite {target} with explicit public fields and resumable caches")
    parser.add_argument('--config', type=Path)
    parser.add_argument('--input-csv', type=Path)
    parser.add_argument('--output-csv', type=Path)
    parser.add_argument('--cache-dir', type=Path)
    parser.add_argument('--api-key')
    parser.add_argument('--model', default=common.DEFAULT_MODEL)
    parser.add_argument('--id-column', default='Id')
    parser.add_argument('--name-column', default='Name')
    parser.add_argument('--target-column', default=target)
    parser.add_argument('--context-columns', default='')
    parser.add_argument('--link-columns', default='Website' if target == 'AI Context' else '')
    parser.add_argument('--max-context-chars', type=int, default=6000)
    parser.add_argument('--system-file', type=Path)
    parser.add_argument('--prompt-file', '--batch-policy-file', dest='prompt_file', type=Path)
    parser.add_argument('--batch-size', type=int, default=8 if batched else 1)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--shard-count', type=int, default=1)
    parser.add_argument('--shard-index', type=int, default=0)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--max-attempts', type=int, default=3)
    parser.add_argument('--timeout-seconds', type=int, default=120)
    parser.add_argument('--request-delay-seconds', type=float, default=4.5)
    parser.add_argument('--flush-every', type=int, default=20)
    parser.add_argument('--flush-every-batches', type=int)
    parser.add_argument('--usage-report', type=Path)
    parser.add_argument('--missing-only', action='store_true')
    parser.add_argument('--id', action='append', default=[])
    parser.add_argument('--force', action='store_true')
    initial, _ = parser.parse_known_args(argv)
    if initial.config:
        config = json.loads(initial.config.read_text(encoding='utf-8'))
        allowed = {a.dest: a for a in parser._actions if a.dest not in {'help', 'config', 'api_key'}}
        if not isinstance(config, dict) or set(config) - set(allowed):
            parser.error('Config must contain known argument names using underscores; secrets belong in the environment')
        for key, value in config.items():
            action = allowed[key]
            if isinstance(action, argparse._StoreTrueAction) and not isinstance(value, bool):
                parser.error(f'{key} must be a boolean')
            if key == 'id' and (not isinstance(value, list) or not all(isinstance(v, str) for v in value)):
                parser.error('id must be an array of text ids')
            if action.type is Path and value is not None:
                value = initial.config.resolve().parent / value
            elif action.type is not None and value is not None:
                value = action.type(value)
            elif not isinstance(action, (argparse._StoreTrueAction, argparse._AppendAction)) and value is not None and not isinstance(value, str):
                parser.error(f'{key} must be text')
            parser.set_defaults(**{key: value})
    args = parser.parse_args(argv)
    for name in ('input_csv', 'output_csv', 'cache_dir'):
        if getattr(args, name) is None:
            parser.error(f'--{name.replace("_", "-")} is required')
    for name in ('workers', 'shard_count', 'max_attempts', 'timeout_seconds', 'flush_every', 'max_context_chars'):
        if getattr(args, name) < 1:
            parser.error(f'{name} must be positive')
    if not 1 <= args.batch_size <= (12 if batched else 1):
        parser.error('batch_size must be 1 for a single-row runner or between 1 and 12 for batching')
    if args.limit < 0 or args.request_delay_seconds < 0 or not 0 <= args.shard_index < args.shard_count:
        parser.error('Invalid limit, delay, or shard index')
    if args.flush_every_batches is not None:
        if args.flush_every_batches < 1:
            parser.error('flush_every_batches must be positive')
        args.flush_every = args.flush_every_batches * args.batch_size
    return args


class RunLog:
    def __init__(self, report: Path, model: str, version: str, target: str):
        self.report = report
        self.journal = report.with_suffix('.events.jsonl')
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = str(uuid.uuid4())
        self.model, self.version, self.target = model, version, target
        self.events = []
        self.lock = threading.Lock()

    def record(self, **event):
        event = {'run_id': self.run_id, 'model': self.model, 'prompt_version': self.version, 'stage': 'rewrite', 'target_column': self.target, **event}
        with self.lock:
            with self.journal.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + '\n')
                handle.flush()
            self.events.append(event)

    def finish(self, *, status, rows):
        api_events = [e for e in self.events if e['type'] == 'api']
        totals = {}
        for event in api_events:
            for key, value in (event.get('usage') or {}).items():
                if isinstance(value, int) and not isinstance(value, bool):
                    totals[key] = totals.get(key, 0) + value
        summary = {'run_id': self.run_id, 'model': self.model, 'prompt_version': self.version,
                   'status': status, 'target_column': self.target, 'rows': rows, 'api_calls': len(api_events),
                   'retries': sum(e['attempt'] > 1 for e in api_events),
                   'cache_hits': sum(e['type'] == 'cache' for e in self.events),
                   'usage_unavailable_calls': sum(e.get('usage') is None for e in api_events),
                   'usage': totals, 'events_file': str(self.journal.resolve())}
        common.atomic_write_text(self.report, json.dumps(summary, indent=2) + '\n')
        return summary


class RequestPacer:
    """One request-start budget shared by all workers, including retries."""
    def __init__(self, delay):
        self.delay = delay
        self.next_start = 0.0
        self.lock = threading.Lock()

    def wait(self, stop):
        with self.lock:
            if stop.wait(max(0.0, self.next_start - time.monotonic())):
                raise common.GeminiGenerationError('Run cancelled')
            self.next_start = time.monotonic() + self.delay


def run_rewrite(*, target, result_field, version, system, template, validate, batched=False, argv=None):
    args = parse_args(target=target, batched=batched, argv=argv)
    fields, rows = common.load_csv(args.input_csv)
    for column in (args.id_column, args.name_column):
        if column not in fields:
            raise ValueError(f'Missing required column: {column}')
    contexts = common.choose_context_columns(fields, common.parse_csv_list(args.context_columns), required=True)
    links = common.choose_context_columns(fields, common.parse_csv_list(args.link_columns))
    if args.target_column in contexts or args.target_column in links:
        raise ValueError('Target column cannot also be an input; preserve prior text in a separate source column')
    if args.target_column not in fields:
        fields.append(args.target_column)
        for row in rows:
            row[args.target_column] = ''
    ids = [common.row_cache_key(row, i, args.id_column, args.name_column) for i, row in enumerate(rows)]
    if len(set(ids)) != len(ids):
        raise ValueError('Input ids must be unique')
    if set(args.id) - set(ids):
        raise ValueError('Requested ids are missing from input')
    system = common.read_optional_text(args.system_file) or system
    template = common.read_optional_text(args.prompt_file) or template
    selected = list(zip(ids, rows))
    selected = [(key, row) for key, row in selected
                if common.in_shard(key, args.shard_count, args.shard_index)
                and (not args.id or key in args.id)
                and (not args.missing_only or not row[args.target_column].strip())]
    selected = selected[:args.limit or None]
    jobs = []
    for key, row in selected:
        context = common.build_context_from_columns(row, contexts)
        allowed_links = common.url_candidates_from_columns(row, links)
        if len(key) + len(context) + sum(len(link) for link in allowed_links) > args.max_context_chars:
            raise ValueError(f'Context exceeds --max-context-chars for id {key}; curate a shorter source excerpt or explicitly raise the cap')
        fingerprint = common.row_source_fingerprint(row, columns=[*contexts, *links, args.id_column, args.name_column], model=args.model,
                    prompt_version=version, system_instruction=system, prompt_template=template)
        jobs.append(Job(key, row, fingerprint, context, allowed_links))
    log = RunLog(args.usage_report or args.cache_dir / 'usage-summary.json', args.model, version, args.target_column)
    pending = []
    for job in jobs:
        cached = None if args.force else common.load_cached_result(args.cache_dir, job.key)
        if cached and cached.get('input_fingerprint') == job.fingerprint:
            try:
                stored, _ = validate(cached['raw_response'], job.row[args.name_column], job.links)
                if stored != cached[result_field]:
                    raise ValueError('Cached output differs from its validated response')
                job.row[args.target_column] = stored
                log.record(type='cache', id=job.key, usage=None)
                continue
            except (ValueError, KeyError, TypeError):
                pass
        pending.append(job)
    api_key = common.require_api_key(args.api_key) if pending else None
    stop = threading.Event()
    pacer = RequestPacer(args.request_delay_seconds)
    groups = [pending[i:i + args.batch_size] for i in range(0, len(pending), args.batch_size)]

    def generate(group):
        feedback = ''
        for attempt in range(1, args.max_attempts + 1):
            packets = [{'id': job.key, 'context': job.context, 'allowed_links': job.links} for job in group]
            prompt = template.format(entities=json.dumps(packets, ensure_ascii=False), context=group[0].context,
                                     target_column=args.target_column, allowed_links='\n'.join(group[0].links) or '- none')
            if feedback:
                prompt += '\nFix required: ' + feedback
            pacer.wait(stop)
            try:
                payload = common.call_gemini_json(api_key=api_key, model=args.model, system_instruction=system,
                                                 prompt=prompt, timeout_seconds=args.timeout_seconds)
            except common.GeminiGenerationError as exc:
                log.record(type='api', ids=[job.key for job in group], attempt=attempt, usage=exc.usage,
                           status='api-error', prompt=prompt)
                # Authentication/quota failures require a changed configuration, not more queued calls.
                if exc.status in {400, 401, 403, 404, 429}:
                    stop.set()
                    raise
                feedback = 'Previous request failed; return the requested JSON object.'
                continue
            log.record(type='api', ids=[job.key for job in group], attempt=attempt,
                       usage=payload.get('_usage_metadata'), model_version=payload.get('_model_version'),
                       status='response', prompt=prompt, response=payload)
            try:
                outputs = payload.get('results') if batched else [payload]
                if not isinstance(outputs, list) or not all(isinstance(item, dict) for item in outputs):
                    raise ValueError('Results must be an array of objects')
                if batched:
                    returned = [item.get('id') for item in outputs]
                    if len(returned) != len(group) or any(not isinstance(key, str) for key in returned) or set(returned) != {job.key for job in group}:
                        raise ValueError('Return every supplied text id exactly once')
                    by_id = {item['id']: item for item in outputs}
                else:
                    by_id = {group[0].key: outputs[0]}
                normalized = []
                for job in group:
                    value, raw = validate(by_id[job.key], job.row[args.name_column], job.links)
                    normalized.append((job, value, raw))
            except (ValueError, TypeError, KeyError) as exc:
                feedback = str(exc)
                continue
            # Persist successes in the worker so another worker's failure cannot discard completed calls.
            for job, value, raw in normalized:
                common.save_cached_result(args.cache_dir, job.key, {'input_fingerprint': job.fingerprint,
                    'model': args.model, 'prompt_version': version, result_field: value, 'raw_response': raw})
            return normalized
        raise common.GeminiGenerationError(f'Failed after {args.max_attempts} attempts for {[j.key for j in group]}: {feedback}')

    status = 'failed'
    completed = 0
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(generate, group) for group in groups]
            try:
                for future in as_completed(futures):
                    results = future.result()
                    for job, value, _ in results:
                        job.row[args.target_column] = value
                        completed += 1
                    if completed // args.flush_every != (completed - len(results)) // args.flush_every:
                        common.write_csv(args.output_csv, fields, rows)
                    if completed % 25 < args.batch_size or completed == len(pending):
                        print(f'Generated {completed}/{len(pending)} rows', file=sys.stderr)
            except BaseException:
                stop.set()
                for future in futures:
                    future.cancel()
                raise
        status = 'complete'
    finally:
        common.write_csv(args.output_csv, fields, rows)
        summary = log.finish(status=status, rows=len(jobs))
        print(json.dumps({**summary, 'output': str(args.output_csv.resolve())}))
    return 0
