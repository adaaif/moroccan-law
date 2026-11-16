"""A batch as the web would send it, and a browser's request headers, for the measures' tests."""
import json
from datetime import UTC, datetime

URL = '/api/measure/'
# A phone's browser, as Android's Chrome names itself.
BROWSER = 'Mozilla/5.0 (Linux; Android 14; SM-A146B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36'
MOMENT = datetime(2026, 11, 14, 14, 37, 52, 123456, tzinfo=UTC)


def event(name='page.shown', kind='article', path='/ma/loi/65-99/art_53', **more):
    return {'name': name, 'kind': kind, 'path': path, **more}


def batch(*events, **more):
    return {'lang': 'ar', 'screen': 'phone', 'build': 'abc1234', 'events': list(events) or [event()], **more}


def post(client, body, **headers):
    headers.setdefault('HTTP_USER_AGENT', BROWSER)
    raw = body if isinstance(body, str) else json.dumps(body)
    return client.post(URL, raw, content_type='application/json', **headers)
