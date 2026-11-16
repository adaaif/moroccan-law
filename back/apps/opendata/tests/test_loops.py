"""The open data's dump reads the same number of queries for a few texts as for ten times as many (no query inside a
loop): each chunk of texts brings its versions, the chosen versions' articles, the changes the texts make and the texts
they cite in a few queries, each other file a chunk of its rows in one or two, and the files say what they said when
each text was read alone."""
import gzip
import json
import zipfile
from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.consolidation.models import Change
from apps.corpus.models import Alias, Article, Consolidation, Mention, Text, Version
from apps.opendata.services import dump
from apps.sources.models import Document, Edition, Issue
from apps.translations.models import FrenchArticle, FrenchText

pytestmark = pytest.mark.django_db


def texts(start: int, end: int):
    """Texts `start` to `end`: each printed in an issue with three articles, every other one with a newer machine
    consolidation, each amending its neighbour's articles and citing two texts (once twice)."""
    issue, _ = Issue.objects.get_or_create(edition=Edition.GENERAL_AR, number=7533, defaults={'date': date(2026, 8, 10)})
    for i in range(start, end):
        uri = f'/akn/ma/act/loi/{i}-26'
        text = Text.objects.create(akn_uri=uri, type='law', number=f'{i}-26', number_as_printed=f'{i}.26',
                                   title_ar=f'قانون رقم {i}.26', first_published_in=issue, signed_on=date(2026, 7, 1))
        kinds = [Consolidation.AS_PUBLISHED] + ([Consolidation.MACHINE] if i % 2 else [])
        for k, kind in enumerate(kinds):
            v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 8 + k, 10), consolidation=kind)
            for n in (1, 2, 3):
                Article.objects.create(version=v, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}',
                                       body=f'نص {i} {kind} {n}.\nفقرة ثانية.')
        for n, state in (('2', 'read'), ('3', 'checked'), ('1', 'unclear')):
            Change.objects.create(text_uri=f'/akn/ma/act/loi/{i + 1}-26', number=n, verb='modified', state=state,
                                  source=Change.Source.READING, by_uri=uri, by_kind='law', by_number=f'{i}-26',
                                  effective_on=date(2026, 9, 1) if n == '2' else None)
        for to in (f'/akn/ma/act/loi/{i + 2}-26', f'/akn/ma/act/loi/{i + 3}-26', f'/akn/ma/act/loi/{i + 2}-26'):
            Mention.objects.create(from_uri=uri, words='القانون', kind=Mention.Kind.CITES, to_uri=to,
                                   state=Mention.State.RESOLVED)
        # The other files' rows: a change an official consolidation states and one a model read (left out), an issue with
        # its file, the text's official French with two articles, and an older address.
        for source in (Change.Source.SGG, Change.Source.MODEL):
            Change.objects.create(text_uri=uri, number='1', verb='modified', source=source, by_kind='law',
                                  by_number=f'{i + 1}-26')
        document = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{i:064x}', path=f'fr/{i}.pdf',
                                           mime='application/pdf', language='fr', bytes=10, page_count=4,
                                           fetched_at=timezone.now())
        Issue.objects.create(edition=Edition.TRANSLATION_FR, number=5000 + i, date=date(2026, 8, 12), document=document)
        FrenchText.objects.create(text_uri=uri, type='law', number=f'{i}-26', title=f'Loi n° {i}-26', issue_number=5000 + i,
                                  issue_date=date(2026, 8, 12), document_sha=document.sha256, pages='1-2')
        for n in (1, 2):
            FrenchArticle.objects.create(text_uri=uri, order=n, label=f'Article {n}', number=str(n), body=f'Texte {i} {n}.')
        Alias.objects.create(alias=f'/akn/ma/act/loi/2026/{i}-26', uri=uri, reason=Alias.Reason.MOVED)


def files(out) -> tuple[list[str], dict]:
    lines = gzip.open(out / 'texts.jsonl.gz', 'rt', encoding='utf-8').read().splitlines()
    with zipfile.ZipFile(out / 'akn.zip') as zf:
        xml = {name: zf.read(name) for name in zf.namelist()}
    return lines, xml


def records(out, name: str) -> list[dict]:
    return [json.loads(line) for line in gzip.open(out / name, 'rt', encoding='utf-8')]


def test_the_dump_costs_the_same_whatever_its_texts(settings, tmp_path):
    settings.OPEN_DATA_DIR = tmp_path
    costs, made = [], []
    for start, end in ((0, 3), (3, 30)):
        texts(start, end)
        with CaptureQueriesContext(connection) as queries:
            out = dump.write_dump(log=lambda m: None)
        costs.append(len(queries))
        made.append(files(out))
    lines, xml = made[1]
    assert len(lines) == len(xml) == 30
    assert costs[0] == costs[1], costs
    # Every file grew with the texts: 15 machine versions besides the 30 newest, 30 French texts, 120 changes (the
    # model's left out), 31 issues, 30 older addresses.
    found = {name: len(records(out, name)) for name in ('versions.jsonl.gz', 'french.jsonl.gz', 'changes.jsonl.gz',
                                                         'issues.jsonl.gz', 'aliases.jsonl.gz')}
    assert found == {'versions.jsonl.gz': 15, 'french.jsonl.gz': 30, 'changes.jsonl.gz': 120, 'issues.jsonl.gz': 31,
                     'aliases.jsonl.gz': 30}


def test_a_chunk_of_texts_is_read_as_each_text_alone(settings, tmp_path, monkeypatch):
    """Two texts a chunk, and the records they make are those each text made read on its own."""
    import json
    settings.OPEN_DATA_DIR = tmp_path
    texts(0, 7)
    monkeypatch.setattr(dump, 'CHUNK', 2)
    monkeypatch.setattr(dump, 'VERSIONS', 1)
    out = dump.write_dump(log=lambda m: None)
    lines, xml = files(out)
    for line in lines:
        record = json.loads(line)
        text = Text.objects.select_related('first_published_in').get(akn_uri=record['akn_uri'])
        version = text.latest_version()
        assert record['articles'] == [{'eid': a.eid, 'label': a.label, 'number': a.number, 'heading_path': a.heading_path,
                                       'path': f"{record['path']}/{a.eid}", 'page': a.printed_page, 'body': a.body}
                                      for a in version.articles.all()]
        assert [c['article'] for c in record['amends']] == ['2', '3']
        assert record['cites'] == sorted({m.to_uri for m in Mention.objects.filter(from_uri=text.akn_uri)})
        assert xml[text.akn_uri.strip('/').replace('/', '_') + '.xml'] == dump.akn_xml(text, version)
    # Each text's other versions, whole, the oldest first, and never the one its own line carries.
    others = records(out, 'versions.jsonl.gz')
    assert [r['akn_uri'] for r in others] == [f'/akn/ma/act/loi/{i}-26' for i in (1, 3, 5)]
    for record in others:
        version = Version.objects.get(text__akn_uri=record['akn_uri'], consolidation=Consolidation.AS_PUBLISHED)
        assert record['version']['kind'] == 'as_published' and record['version']['valid_from'] == '2026-08-10'
        assert [a['body'] for a in record['articles']] == [a.body for a in version.articles.all()]
    # Every file's rows, two a chunk, as many as there are.
    assert len(records(out, 'french.jsonl.gz')) == len(records(out, 'aliases.jsonl.gz')) == 7
    assert [len(r['articles']) for r in records(out, 'french.jsonl.gz')] == [2] * 7
    assert len(records(out, 'changes.jsonl.gz')) == 7 * 4 and len(records(out, 'issues.jsonl.gz')) == 8
