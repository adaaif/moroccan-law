"""The OpenAPI file (apps/opendata/v1/openapi.yaml) cannot drift from the code: each read is called on a small made
corpus and its real answer, refusals included, is checked against the file's schema for that address and status (its
`$ref`s resolved here: there is no OpenAPI validator), every schema in it is a valid JSON Schema, and the file
describes every route of v1 and no other."""
import re
from unittest import mock

import pytest
import yaml
from jsonschema import Draft202012Validator

from apps.mcp.tests.conftest import labour  # noqa: F401  (a fixture)
from apps.opendata.models import Access
from apps.opendata.tests.helpers import accepted, keyed
from apps.opendata.tests.test_v1 import FOUND, ago, get, made, post, requests_open  # noqa: F401  (fixtures)
from apps.opendata.v1 import urls
from apps.opendata.v1.views import OPENAPI

pytestmark = pytest.mark.django_db
DOC = yaml.safe_load(OPENAPI.read_text(encoding='utf-8'))


def resolved(node):
    """`node` with each `$ref` replaced by what it names in the file (no schema in it refers to itself)."""
    if isinstance(node, dict):
        if '$ref' in node:
            target = DOC
            for part in node['$ref'].removeprefix('#/').split('/'):
                target = target[part]
            return resolved(target)
        return {key: resolved(value) for key, value in node.items()}
    if isinstance(node, list):
        return [resolved(value) for value in node]
    return node


def check(response, route: str, method: str = 'get') -> dict:
    """The answer against what the file says of `route`'s answer with that status: its schema, its required headers."""
    said = resolved(DOC['paths'][route][method]['responses'][str(response.status_code)])
    schema = said['content']['application/json']['schema']
    Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(response.json())
    for name, header in (said.get('headers') or {}).items():
        assert not header.get('required') or response.has_header(name), (route, name)
    return response.json()


def test_every_answer_is_what_the_file_says(api, made):
    _, key = keyed(accepted(size=Access.Size.PARTNER, minute=1000, calls=1000, articles=1000))
    with mock.patch('apps.search.services.search.search', return_value=FOUND):
        found = check(get(api, '/api/v1/search?q=المادة 51', key), '/search')
    assert len(found['results']) == 3
    nothing = {'jump': None, 'results': [], 'repaired': 'الضريبة'}
    with mock.patch('apps.search.services.search.search', return_value=nothing):
        assert set(check(get(api, '/api/v1/search?q=hgqvdfm', key), '/search')) == {'results', 'searched_as', 'note'}
    check(get(api, '/api/v1/search?q=', key), '/search')

    for path, kind in (('ma/loi/65-99/art_51', 'article'), ('ma/loi/65-99', 'text'), ('bo/7533', 'bulletin_issue'),
                       ('ma/loi/12-26/art_2', 'article')):
        assert check(get(api, f'/api/v1/texts/{path}', key), '/texts/{path}')['metadata']['kind'] == kind
    check(get(api, '/api/v1/texts/ma/loi/1-01', key), '/texts/{path}')
    check(get(api, '/api/v1/texts/nothing', key), '/texts/{path}')

    run = check(get(api, '/api/v1/articles/ma/loi/65-99?start=51&count=2&on=2004-01-01&french=1', key),
                '/articles/{path}')
    assert run['note'] and run['articles'][0]['french'] and run['articles'][0]['changes']
    assert check(get(api, '/api/v1/articles/ma/loi/12-26', key), '/articles/{path}')['next'] is None
    check(get(api, '/api/v1/articles/ma/loi/65-99?count=99', key), '/articles/{path}')
    check(get(api, '/api/v1/articles/ma/loi/65-99?start=700', key), '/articles/{path}')

    for since in (str(ago(60)), ''):
        refs = check(post(api, '/api/v1/references', {'references': ['المادة 51 من القانون رقم 65.99', 'ج.ر 7533', 'شكرا'],
                                                    'since': since}, key), '/references', 'post')
        assert (refs['references'][0]['found'][0]['changed_since'] is None) == (since == '')
    check(post(api, '/api/v1/references', {'references': []}, key), '/references', 'post')
    check(api.post('/api/v1/references', {'references': 'x'}, HTTP_X_API_KEY=key), '/references', 'post')

    check(get(api, '/api/v1/bulletin/', key), '/bulletin/')
    check(get(api, '/api/v1/bulletin/5167', key), '/bulletin/{issue}')
    check(get(api, '/api/v1/bulletin/9999', key), '/bulletin/{issue}')
    check(get(api, '/api/v1/bulletin/x-y-z', key), '/bulletin/{issue}')

    page = check(get(api, f'/api/v1/changes?since={ago(30)}', key), '/changes')
    assert page['published'] and page['amended']
    check(get(api, '/api/v1/changes?since=2001-01-01', key), '/changes')


def test_the_refusals_before_any_work_are_what_the_file_says(api, made, settings):
    _, data_only = keyed(api=False, data=True)
    _, key = keyed(accepted(size=Access.Size.PARTNER, minute=1, calls=10, articles=10, username='other'))
    check(get(api, '/api/v1/texts/ma/loi/65-99'), '/texts/{path}')
    check(get(api, '/api/v1/bulletin/', 'law_wrong'), '/bulletin/')
    check(get(api, '/api/v1/changes?since=2026-01-01', data_only), '/changes')
    check(get(api, '/api/v1/bulletin/5167', key), '/bulletin/{issue}')
    assert check(get(api, '/api/v1/bulletin/5167', key), '/bulletin/{issue}')['errors'][0]['code'] == 'minute'
    settings.OPEN_DATA = 'closed'
    check(post(api, '/api/v1/references', {'references': ['x']}, key), '/references', 'post')


def test_the_file_describes_every_route_of_v1_and_no_other():
    routes = {'/' + re.sub(r'<(?:\w+:)?(\w+)>', r'{\1}', str(p.pattern)) for p in urls.urlpatterns}
    assert routes == set(DOC['paths'])
    for route, methods in DOC['paths'].items():
        for operation in methods.values():
            if route == '/openapi.yaml':
                assert operation['security'] == []
                continue
            assert {'200', '401', '403', '429'} <= set(operation['responses']), route
            assert {'RateLimit-Policy', 'RateLimit', 'Deprecation', 'Sunset'} <= set(
                resolved(operation['responses']['200'])['headers']), route
    assert DOC['components']['securitySchemes']['key'] == {
        'type': 'apiKey', 'in': 'header', 'name': 'X-Api-Key',
        'description': DOC['components']['securitySchemes']['key']['description']}


def test_every_schema_is_valid_json_schema_and_no_name_was_read_as_a_yes_or_no():
    for schema in DOC['components']['schemas'].values():
        Draft202012Validator.check_schema(resolved(schema))

    def names(node):
        """Every key of the file, and every item of a `required` or `enum` list."""
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                if key in ('required', 'enum') and isinstance(value, list):
                    yield from value
                yield from names(value)
        elif isinstance(node, list):
            for value in node:
                yield from names(value)
    # YAML 1.1 reads a bare `on`, `yes` or `no` as a boolean: every name in the file is a string.
    assert all(isinstance(name, str) for name in names(DOC))


def test_the_description_says_what_the_api_gives_and_how_to_cite_it():
    said = DOC['info']['description']
    for words in ('Bulletin officiel prevails', 'is not law', 'To cite', 'issue and date', '`url`', 'X-Api-Key',
                  '/data', 'unofficial'):
        assert words in said, words
    assert DOC['openapi'] == '3.1.0' and DOC['servers'] == [{'url': '/api/v1'}]
