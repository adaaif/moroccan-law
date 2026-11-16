"""`link_eval` (row L11 of the links review): our readings measured against the SGG's notes and Adala's footnotes
(recall), against the SGG's later text (precision), its citations checked for the kind their words name, and a sample
of links written for a person to check."""
import datetime
import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.consolidation.models import Change
from apps.corpus.models import Mention, Text, Version
from apps.sources.models import Document

pytestmark = pytest.mark.django_db
CODE, AMENDER, OLD, UNREAD = '/akn/ma/act/loi/2-00', '/akn/ma/act/loi/13-26', '/akn/ma/act/loi/34-05', '/akn/ma/act/loi/66-19'
FINANCE = '/akn/ma/act/loi/50-24'
DAY = datetime.date(2026, 8, 10)


def text(uri, *consolidations, as_of=None):
    t = Text.objects.create(akn_uri=uri, type='law', number=uri.rsplit('/', 1)[-1], title_ar='نص')
    for k, consolidation in enumerate(consolidations):
        doc = None
        if as_of is not False and consolidation == 'sgg':
            doc = Document.objects.create(source='sgg_consolidated', kind='consolidated_text', sha256=uri[-8:].ljust(64, 'a'),
                                          path=f'{k}.pdf', mime='application/pdf', language='ar', bytes=1,
                                          fetched_at=timezone.now(), meta={'as_of': as_of} if as_of else {})
        Version.objects.create(text=t, language='ar', valid_from=datetime.date(2000 + k, 1, 1),
                               consolidation=consolidation, source_document=doc)
    return t


def change(source, number, by=AMENDER, on=DAY, state='', **kw):
    return Change(text_uri=kw.pop('text_uri', CODE), number=number, verb='modified', source=source, by_kind='law',
                  by_number=by.rsplit('/', 1)[-1], by_uri=by, published_on=on, state=state, issue=7533, page=5141,
                  effective_on=on, by_article='المادة الأولى', **kw)


def report(*args):
    out = StringIO()
    call_command('link_eval', *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def corpus(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    (tmp_path / 'reports').mkdir()
    return tmp_path


def test_recall_counts_the_notes_our_reading_also_has_and_precision_what_the_sggs_later_text_bears_out(corpus):
    text(CODE, 'as_published', 'sgg', as_of='2026-09-01')
    text('/akn/ma/act/loi/9-88', 'as_published', 'sgg', as_of=False)     # an SGG version with no file: no date to judge by
    text('/akn/ma/act/loi/5-96', 'sgg', as_of='')                         # a file whose date was not read
    text(AMENDER, 'as_published')
    text(OLD, 'as_published')
    text(FINANCE, 'as_published')
    Change.objects.bulk_create([
        # The SGG's notes: three found (one as «7-1» where the site reads «1-7», one on the whole text), one missed; a
        # change of 2006 and one by a text the site has not read from the BO are not counted.
        change('sgg', '1'), change('sgg', '7-1'), change('sgg', ''), change('sgg', '9'),
        change('sgg', '3', by=OLD, on=datetime.date(2006, 2, 20)), change('sgg', '4', by=UNREAD),
        # Adala's footnotes: one found; one with no date is not counted.
        change('adala', '1'), change('adala', '2', on=None),
        change('sgg', '12', by=FINANCE, on=datetime.date(2025, 3, 5)),      # of 2025, missed
        # Our readings.
        change('reading', '1', state='confirmed'), change('reading', '1-7', state='read'),
        change('reading', '', state='read'),
        change('reading', '5', state='read', verdict='agrees'),            # the SGG's later wording holds it
        change('reading', '6', state='read', witnesses={'wording': True}),
        change('reading', '8', state='conflict', verdict='disagrees'),
        change('reading', '10', state='read', verdict='absent'),
        *[change('reading', str(20 + k), state='read') for k in range(9)],          # nothing to judge by
        change('reading', '30', state='read', on=datetime.date(2026, 10, 1)),       # after the SGG's text
        change('reading', '31', state='read', on=datetime.date(2018, 5, 1)),        # before 2019
        change('reading', '32', state='read', on=None),
        change('reading', '1', state='read', text_uri='/akn/ma/act/loi/77-15'),    # a text the SGG does not keep
    ])
    said = report()
    data = json.loads((corpus / 'reports' / 'link_eval.json').read_text())
    assert data['from'] == '2019-01-01'
    sgg, adala, precision = data['changes']['sgg'], data['changes']['adala'], data['changes']['precision']
    assert (sgg['notes'], sgg['found'], sgg['recall']) == (5, 3, 60.0)
    assert sgg['states'] == {'confirmed': 1, 'read': 2, 'missed': 2}
    assert list(sgg['by_year'].items()) == [('2025', {'found': 0, 'notes': 1, 'recall': 0.0}),
                                            ('2026', {'found': 3, 'notes': 4, 'recall': 75.0})]
    assert (adala['notes'], adala['found'], adala['recall'], adala['states']) == (1, 1, 100.0, {'confirmed': 1})
    assert precision['texts'] == 1
    assert precision['by_state'] == {
        'confirmed': {'note': 1, 'precision': 100.0},
        'read': {'note': 2, 'wording': 2, 'against': 1, 'silent': 9, 'precision': 80.0},
        'conflict': {'against': 1, 'precision': 0.0}}
    assert precision['shown'] == {'note': 3, 'wording': 2, 'against': 1, 'silent': 9, 'precision': 83.3}
    # At most eight examples a kind, each with where to check it.
    assert len(precision['examples']['read:silent']) == 8
    assert precision['examples']['read:against'] == [{'text': '/ma/loi/2-00', 'article': '10', 'by': '/ma/loi/13-26',
                                                      'issue': 7533, 'page': 5141, 'verb': 'modified'}]
    assert said.splitlines() == [
        f"sgg: 3 of 5 notes found (recall 60.0 %), {sgg['states']}",
        f"adala: 1 of 1 notes found (recall 100.0 %), {adala['states']}",
        f"precision of what is shown: {precision['shown']}",
        *[f'  {state:>10}: {row}' for state, row in precision['by_state'].items()],
        "citations: {}; linked 0 (0 to a text the site holds); kind checked 0, wrong kind 0"]
    assert not (corpus / 'reports' / 'link_sample.json').exists()


def mention(words, to_uri, state='resolved', kind='cites', from_uri=AMENDER, from_eid='art_1'):
    return Mention(from_uri=from_uri, from_eid=from_eid, words=words, kind=kind, to_uri=to_uri, state=state)


def test_citations_are_counted_by_state_and_checked_for_the_kind_their_words_name_and_a_sample_is_drawn(corpus):
    text(AMENDER, 'as_published')
    text('/akn/ma/act/loi/31-13', 'as_published')
    text('/akn/ma/act/dahir/1-77-340', 'as_published')
    long = 'المرسوم رقم 2.18.500 ' + 'الصادر في 5 أكتوبر 2018 بتطبيق القانون رقم 31.13 المتعلق بالحق في الحصول على المعلومات ' * 2
    Mention.objects.bulk_create([
        mention('القانون رقم 31.13', '/akn/ma/act/loi/31-13'),
        # «قانون رقم 1.77.340» is a dahir having force of law, numbered as a dahir is: its own kind.
        mention('قانون رقم 1.77.340', '/akn/ma/act/dahir/1-77-340'),
        # A decree linked to a law's address: the wrong kind. Ten examples at most, their words cut at 120.
        mention(long, '/akn/ma/act/loi/2-18-500'),
        *[mention(f'المرسوم رقم 2.18.{k}', f'/akn/ma/act/loi/2-18-{k}') for k in range(501, 511)],
        mention('الدستور', '/akn/ma/act/dahir/1-11-91'),                  # names no kind: not checked
        mention('القانون رقم 31.13', '/akn/ma/act/loi/31-13', from_eid=''),           # the title's: not in the sample
        mention('القانون رقم 13.26', AMENDER),                                           # itself: not in the sample
        mention('قانون', '', state='unresolved'),
        mention('بتطبيق القانون رقم 31.13', '/akn/ma/act/loi/31-13', kind='applies'),
    ])
    Change.objects.bulk_create([change('reading', n, state=s) for n, s in (('1', 'read'), ('2', 'checked'),
                                                                             ('3', 'conflict'))]
                               + [change('reading', '4', state='read', on=datetime.date(2018, 1, 1))])
    said = report('--sample', '4')
    m = json.loads((corpus / 'reports' / 'link_eval.json').read_text())['mentions']
    assert m['states'] == {'resolved': 17, 'unresolved': 1} and m['kinds'] == {'cites': 17, 'applies': 1}
    assert (m['resolved'], m['resolved_in_corpus'], m['kind_checked'], m['wrong_kind']) == (16, 4, 15, 11)
    assert len(m['wrong_kind_examples']) == 10
    assert m['wrong_kind_examples'][0] == {'words': long[:120], 'to': '/ma/loi/2-18-500'}
    assert said.splitlines()[-1] == (f"citations: {m['states']}; linked 16 (4 to a text the site holds); kind checked 15, "
                                     "wrong kind 11")
    sample = json.loads((corpus / 'reports' / 'link_sample.json').read_text())
    # Half changes shown as fact since 2019, half citations of an article to another text the site holds.
    changes = sorted((s for s in sample if s['kind'] == 'change'), key=lambda s: s['article'])
    assert changes == [{'kind': 'change', 'state': state, 'verb': 'modified', 'text': '/ma/loi/2-00', 'article': n,
                        'by': '/ma/loi/13-26', 'by_article': 'المادة الأولى', 'issue': 7533, 'bis': False, 'page': 5141,
                        'takes_effect': '2026-08-10', 'check': ''} for n, state in (('1', 'read'), ('2', 'checked'))]
    cited = sorted((s for s in sample if s['kind'] == 'citation'), key=lambda s: s['to'])
    assert cited == [
        {'kind': 'citation', 'words': 'قانون رقم 1.77.340', 'from': '/ma/loi/13-26', 'eid': 'art_1',
         'to': '/ma/dahir/1-77-340', 'article': '', 'check': ''},
        {'kind': 'citation', 'words': 'القانون رقم 31.13', 'from': '/ma/loi/13-26', 'eid': 'art_1', 'to': '/ma/loi/31-13',
         'article': '', 'check': ''}]
