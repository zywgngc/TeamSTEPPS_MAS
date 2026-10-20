import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from teamstepps_mas.cli import execute, load_cases
from teamstepps_mas.runtime import TracedClient


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_backend_failure_preserves_pending_without_retry(self):
        calls = []

        async def transport(request):
            calls.append(request)
            return httpx.Response(503, json={'error': 'synthetic backend failure'})

        def client_factory(*args, **kwargs):
            client = TracedClient(*args, **kwargs)
            # The unused original client has not opened a connection.
            client.http = httpx.AsyncClient(transport=httpx.MockTransport(transport))
            return client

        async def complete(case, client, **kwargs):
            return await client.complete('fixture', case['question'], tag='fixture', max_tokens=16)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root/'input.jsonl'
            input_path.write_text('{"id":"fixture","question":"fixture","options":{"A":"one","B":"two"}}\n')
            args = argparse.Namespace(out=root/'new-run', input=input_path, base_url='http://fixture/v1',
                                      model='fixture', seed=111, temperature=0.0)
            with patch('teamstepps_mas.cli.TracedClient', side_effect=client_factory), patch('teamstepps_mas.cli.run_team', side_effect=complete):
                code = await execute(args, load_cases(input_path), ['teamstepps', 'generic_team'])
            self.assertEqual(code, 1)
            self.assertEqual(len(calls), 1)
            completion = json.loads((args.out/'completion.json').read_text())
            self.assertEqual(completion['jobs'], {'done': 0, 'error': 1, 'pending': 1, 'running': 0})
            self.assertTrue(completion['infrastructure_interrupted'])
            self.assertFalse(completion['dispatch_complete'])
            trace = [json.loads(line) for line in (args.out/'traces/000000.jsonl').read_text().splitlines()]
            self.assertEqual(len(trace), 1)
            self.assertIn('error', trace[0])
            self.assertEqual(trace[0]['response_status_code'], 503)
            self.assertIn('synthetic backend failure', trace[0]['response_body'])

    async def test_input_drops_gold_and_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'input.jsonl'
            row = {'id': 'fixture', 'question': 'fixture', 'options': {'A': 'one', 'B': 'two'}, 'gold': 'SECRET'}
            path.write_text(json.dumps(row) + '\n')
            self.assertNotIn('gold', load_cases(path)[0])
            path.write_text((json.dumps(row) + '\n')*2)
            with self.assertRaises(ValueError):
                load_cases(path)


if __name__ == '__main__':
    unittest.main()
