"""Sequential development runner; fresh output directory and no inference retries."""
from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

import httpx

from .protocol import run_native_reference, run_team
from .runtime import TracedClient, public_case

METHODS = {
    'native_medagents': None,
    'generic_team': {'meaning_feedback': False, 'task_assistance': False},
    'meaning_only': {'meaning_feedback': True, 'task_assistance': False},
    'assistance_only': {'meaning_feedback': False, 'task_assistance': True},
    'teamstepps': {},
    'full_broadcast': {'broadcast': True},
    'unpooled_teamstepps': {'pool_messages': False},
}


def load_cases(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Input contains no cases')
    seen = set()
    cases = []
    for row in rows:
        case = public_case(row)
        if not isinstance(case.get('id'), str) or not case['id'] or case['id'] in seen:
            raise ValueError('Case IDs must be nonempty and unique')
        if not isinstance(case.get('question'), str) or not case['question'].strip():
            raise ValueError('Every case needs a question')
        options = case.get('options')
        if not isinstance(options, dict) or not 2 <= len(options) <= 5 or any(k not in 'ABCDE' or len(k) != 1 for k in options):
            raise ValueError('Options must have two to five labels from A through E')
        if any(not isinstance(v, str) or not v.strip() for v in options.values()):
            raise ValueError('Option texts must be nonempty strings')
        if 'context' in case and (not isinstance(case['context'], list) or any(not isinstance(x, str) for x in case['context'])):
            raise ValueError('Context must be a list of strings')
        seen.add(case['id'])
        cases.append(case)
    return cases


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


async def execute(args, cases, methods):
    # mkdir is exclusive: an existing run is never resumed or overwritten.
    args.out.mkdir(parents=True, exist_ok=False)
    jobs = [{'index': i, 'id': case['id'], 'method': method, 'status': 'pending'}
            for i, (case, method) in enumerate((c, m) for c in cases for m in methods)]
    metadata = {'created_utc': datetime.now(timezone.utc).isoformat(),
                'source_input_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
                'public_cases_sha256': hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
                'model': args.model, 'base_url': args.base_url, 'seed': args.seed,
                'temperature': args.temperature, 'planned_cases': len(cases),
                'planned_jobs': len(jobs), 'inference_retries': 0, 'jobs': jobs}
    save(args.out/'manifest.json', metadata)
    by_id = {c['id']: c for c in cases}
    interrupted = False
    for job in jobs:
        trace = args.out/'traces'/f'{job["index"]:06d}.jsonl'
        client = TracedClient(trace, base_url=args.base_url, model=args.model,
                              seed=args.seed, temperature=args.temperature)
        result = {'id': job['id'], 'method': job['method']}
        try:
            job['status'] = 'running'
            save(args.out/'manifest.json', metadata)
            if job['method'] == 'native_medagents':
                result['prediction'] = await run_native_reference(by_id[job['id']], client)
            else:
                result['prediction'] = await run_team(by_id[job['id']], client, **METHODS[job['method']])
            job['status'] = result['status'] = 'done'
        except Exception as error:
            job['status'] = result['status'] = 'error'
            result['error'] = {'type': type(error).__name__, 'message': str(error)}
            # A lost backend stops dispatch; remaining positions stay pending.
            interrupted = isinstance(error, (httpx.HTTPError, ConnectionError))
        finally:
            result['observed_usage'] = client.usage()
            result['provider_call_boundaries'] = len(client.records)
            await client.close()
            save(args.out/f'{job["index"]:06d}_{job["method"]}.json', result)
            save(args.out/'manifest.json', metadata)
        print(json.dumps({'index': job['index'], 'method': job['method'], 'status': job['status']}), flush=True)
        if interrupted:
            break
    counts = {status: sum(j['status'] == status for j in jobs) for status in ['done', 'error', 'pending', 'running']}
    completion = {'jobs': counts, 'infrastructure_interrupted': interrupted,
                  'dispatch_complete': not any(j['status'] in ['pending', 'running'] for j in jobs),
                  'clinical_quality_or_accuracy_evaluated': False,
                  'inference_retries': 0}
    save(args.out/'completion.json', completion)
    print(json.dumps(completion), flush=True)
    return 1 if interrupted or counts['error'] else 0


def main():
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument('--config', type=Path, help='Optional portable development JSON; CLI flags override it.')
    preliminary, _ = config_parser.parse_known_args()
    parser = argparse.ArgumentParser(description=__doc__, parents=[config_parser])
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--methods', default='teamstepps', help='Comma-separated names: ' + ','.join(METHODS))
    parser.add_argument('--base-url', default=os.environ.get('MODEL_BASE_URL', 'http://127.0.0.1:8000/v1'))
    parser.add_argument('--model', default=os.environ.get('MODEL_NAME', 'qwen3-8b'))
    parser.add_argument('--seed', type=int, default=111)
    parser.add_argument('--temperature', type=float, default=0.0)
    parser.add_argument('--dry-run', action='store_true', help='Validate inputs and plan; no files, services, or model calls.')
    if preliminary.config:
        try:
            values = json.loads(preliminary.config.read_text())
            if not isinstance(values, dict) or set(values) - {'base_url', 'model', 'seed', 'temperature', 'methods'}:
                raise ValueError('Config contains unsupported keys')
            if 'methods' in values:
                if not isinstance(values['methods'], list) or not all(isinstance(x, str) for x in values['methods']):
                    raise ValueError('Config methods must be a list of method names')
                values['methods'] = ','.join(values['methods'])
            parser.set_defaults(**values)
        except (OSError, ValueError) as error:
            parser.error(str(error))
    args = parser.parse_args()
    methods = args.methods.split(',')
    if not methods or len(methods) != len(set(methods)) or any(m not in METHODS for m in methods):
        parser.error('Methods must be unique supported names')
    cases = load_cases(args.input)
    if args.dry_run:
        print(json.dumps({'cases': len(cases), 'jobs': len(cases)*len(methods),
                          'methods': methods, 'model_calls': 0, 'files_written': 0}))
        return
    if args.out is None:
        parser.error('--out is required unless --dry-run is selected')
    sys.exit(asyncio.run(execute(args, cases, methods)))


if __name__ == '__main__':
    main()
