"""The sample's fixture is written from a database's own rows (`load_sample --write-fixture`): loaded, then written
again, it holds every row with its fields, its keys counted again from 1 and each foreign key following its row."""
import json
from collections import Counter
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.corpus.management.commands import load_sample
from apps.corpus.models import Text
from apps.sources.models import Issue

pytestmark = pytest.mark.django_db


def test_the_sample_written_again_from_its_own_rows_is_the_fixture(tmp_path, monkeypatch):
    original = load_sample.FIXTURE.read_text(encoding='utf-8')
    call_command('load_sample', stdout=StringIO())
    # One more text of the issue, whose key is not the next one (a row was deleted before it): counted again.
    issue = Issue.objects.get(number=7278)
    Text.objects.create(akn_uri='/akn/ma/act/arrete/1-26', type='order', title_ar='قرار', first_published_in=issue).delete()
    Text.objects.create(akn_uri='/akn/ma/act/arrete/2-26', type='order', title_ar='قرار', first_published_in=issue)
    monkeypatch.setattr(load_sample, 'FIXTURE', tmp_path / 'fixtures' / 'sample.json')
    out = StringIO()
    call_command('load_sample', '--write-fixture', stdout=out)
    assert out.getvalue().startswith('sample.json: ') and '13 corpus.text' in out.getvalue()
    written = json.loads((tmp_path / 'fixtures' / 'sample.json').read_text(encoding='utf-8'))
    before = json.loads(original)
    extra = [o for o in written if o['fields'].get('akn_uri') == '/akn/ma/act/arrete/2-26']
    assert len(extra) == 1
    assert sorted(map(_fields, written)) == sorted(map(_fields, before + extra))
    for model in {o['model'] for o in written}:                # each model's keys run 1, 2, 3 …
        assert sorted(o['pk'] for o in written if o['model'] == model) == list(range(1, Counter(
            o['model'] for o in written)[model] + 1))
    assert _articles_by_text(written) == _articles_by_text(before)


LINKS = {'document', 'copy_of', 'first_published_in', 'text', 'source_document', 'version'}


def _fields(obj) -> str:
    """A row as the fixture writes it, without the keys the writer counts again."""
    return json.dumps([obj['model'], {k: v for k, v in obj['fields'].items() if k not in LINKS}], sort_keys=True)


def _articles_by_text(objects) -> dict:
    """{text address: article labels} through the fixture's own keys: article → version → text."""
    rows = {(o['model'], o['pk']): o['fields'] for o in objects}
    out = {}
    for o in objects:
        if o['model'] == 'corpus.article':
            version = rows[('corpus.version', o['fields']['version'])]
            uri = rows[('corpus.text', version['text'])]['akn_uri']
            out.setdefault((uri, version['language'], version['consolidation']), []).append(o['fields']['label'])
    return {k: sorted(v) for k, v in out.items()}


def test_without_its_fixture_the_sample_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(load_sample, 'FIXTURE', tmp_path / 'sample.json')
    with pytest.raises(CommandError, match=r'sample\.json: no such file'):
        call_command('load_sample')
