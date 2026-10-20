"""CPU-only bounded JSON grammar compiler for the collaboration package."""
import argparse
import functools
import hashlib
import importlib.metadata
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import xgrammar


COMPILER_LOCK = threading.RLock()


@functools.lru_cache(maxsize=1024)
def compile_schema(text):
    with COMPILER_LOCK:
        return str(xgrammar.Grammar.from_json_schema(text, any_whitespace=False))


class QueuedCompiler(ThreadingHTTPServer):
    request_queue_size = 128
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            schema = json.loads(self.rfile.read(int(self.headers["Content-Length"])))['schema']
            text = json.dumps(schema, separators=(",", ":"))
            body = json.dumps({"grammar": compile_schema(text), "any_whitespace": False,
                               "schema_sha256": hashlib.sha256(text.encode()).hexdigest()}).encode()
            self.send_response(200)
        except Exception as exc:
            body = json.dumps({"error": str(exc)}).encode()
            self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=24410)
    parser.add_argument('--state-root', default='runs/grammar')
    args = parser.parse_args()
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise RuntimeError('Compiler requires CUDA_VISIBLE_DEVICES empty')
    server = QueuedCompiler(('127.0.0.1', args.port), Handler)
    state = Path(args.state_root)
    state.mkdir(parents=True, exist_ok=True)
    metadata = {'pid': os.getpid(), 'port': args.port, 'cuda_visible_devices': '',
                'xgrammar_version': importlib.metadata.version('xgrammar'),
                'request_queue_size': 128, 'cache_size': 1024, 'compiler_miss_serialized': True,
                'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (state/'grammar.json').write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata), flush=True)
    server.serve_forever()
