"""B25 of the search plan: the model server, one process beside Django that holds the meaning model and embeds a
question for every worker (gunicorn's workers would each load 600 MB otherwise). POST /embed {texts: [...]} →
{vectors: [[...]]}; GET /health. Listens on 127.0.0.1 only.

    manage.py serve_models --port 8090 --threads 4"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from django.core.management.base import BaseCommand

from apps.search.services.meaning import Encoder

MAX_TEXTS = 32
MAX_CHARS = 4000


class Command(BaseCommand):
    help = 'Serve the meaning model on 127.0.0.1 (B25).'

    def add_arguments(self, parser):
        parser.add_argument('--port', type=int, default=8090)
        parser.add_argument('--threads', type=int, default=4)

    def handle(self, *args, port, threads, **opts):
        encoder = Encoder(threads=threads)
        log = self.stdout.write

        class Handler(BaseHTTPRequestHandler):
            def _send(self, status: int, payload: dict):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._send(200, {'ok': True}) if self.path == '/health' else self._send(404, {})

            def do_POST(self):
                if self.path != '/embed':
                    return self._send(404, {})
                try:
                    data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
                    texts = [str(t)[:MAX_CHARS] for t in data['texts']][:MAX_TEXTS]
                except (ValueError, KeyError, TypeError):
                    return self._send(400, {'errors': [{'field': 'texts', 'code': 'invalid'}]})
                started = time.perf_counter()
                vectors = encoder.encode(texts)
                self._send(200, {'vectors': [[round(float(x), 6) for x in v] for v in vectors],
                                 'ms': round(1000 * (time.perf_counter() - started), 1)})

            def log_message(self, *args):
                pass

        log(f'meaning model on http://127.0.0.1:{port} ({threads} threads)')
        ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
