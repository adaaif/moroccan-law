"""In development, a request that repeats one query shape says so in the server's log (S20 of the performance audit,
24 Oct 2026): a query inside a loop shows the first time its page is opened, with the line that asked."""
import logging
import re
import traceback
from collections import Counter

from django.db import connection

log = logging.getLogger('querylog')
REPEATS = 5         # one shape more often than this in one request is a loop
_LITERALS = re.compile(r"'(?:[^']|'')*'|\b\d+\b")


def shape(sql: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'IN \([^)]*\)', 'IN (…)', _LITERALS.sub('?', sql)))


class RepeatedQueries:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        seen: Counter = Counter()
        where: dict[str, str] = {}

        def watch(execute, sql, params, many, context):
            key = shape(sql)
            seen[key] += 1
            if seen[key] == REPEATS + 1:
                frames = [f for f in traceback.extract_stack() if '/apps/' in f.filename]
                where[key] = ' <- '.join(f"{f.filename.rsplit('/back/', 1)[-1]}:{f.lineno}" for f in reversed(frames[-3:]))
            return execute(sql, params, many, context)

        with connection.execute_wrapper(watch):
            response = self.get_response(request)
        for key, n in seen.items():
            if n > REPEATS:
                log.warning('%s %s: %d× %s — %s', request.method, request.get_full_path()[:120], n, key[:160], where.get(key, ''))
        return response
