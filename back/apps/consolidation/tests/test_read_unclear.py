"""`read_unclear` (row L12 of the links review): a model reads the amending articles the code could not, and its reading
is kept only where the article bears it out: the text it names is cited there, every quoted line stands in it."""
import datetime
from io import StringIO

import pytest
from django.core.management import call_command

from apps.consolidation.models import Change, Doubt
from apps.corpus.models import Article, Text, Version
from apps.corpus.tests import claude
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db
BY = '/akn/ma/act/loi/13-26'
ART_1 = ('تغير وتتمم أحكام المادة 8 من القانون رقم 2.00 كما يلي :\n'
         '«المادة 8. - لا تشمل الحماية ................ ما يلي.»')
ART_2 = 'تحل عبارة «منتج تسجيل صوتي» محل عبارة «منتج مسجل صوتي» في المادة 38 من القانون رقم 2.00.'
ART_4 = 'تنسخ أحكام القانون رقم 15.02 المتعلق بالموانئ.'
ART_6 = 'يدخل هذا القانون حيز التنفيذ ابتداء من فاتح يناير 2027.'


def amending(uri, number, day, articles, issue, suffix=''):
    issue, _ = Issue.objects.get_or_create(edition=Edition.GENERAL_AR, number=issue, suffix=suffix, defaults={'date': day})
    t = Text.objects.create(akn_uri=uri, type='law', number=number, title_ar=f'قانون رقم {number}',
                            first_published_in=issue)
    v = Version.objects.create(text=t, language='ar', valid_from=day, consolidation='as_published')
    Article.objects.bulk_create([Article(version=v, order=k, label=label, number=str(k), eid=f'art_{k}', body=body,
                                         printed_page=5140 + k) for k, (label, body) in enumerate(articles, 1)])
    return t


def unclear(by, label, why=''):
    return Change(text_uri='/akn/ma/act/loi/2-00', number='', verb='modified', source='reading', by_kind='law',
                  by_number='13-26', by_uri=by, by_article=label, state='unclear', detail={'why': why})


@pytest.fixture
def corpus():
    text = amending(BY, '13-26', datetime.date(2026, 8, 10),
                    [('المادة الأولى', ART_1), ('المادة 2', ART_2), ('المادة 3', 'تنسخ أحكام الملحق رقم 1 بالقانون رقم 2.00.'),
                     ('المادة 4', ART_4), ('المادة 5', 'نص.'), ('المادة 6', ART_6), ('المادة 7', 'تغير بعض الأحكام.'),
                     ('المادة 8', 'تتمم بعض الأحكام.')], 7533, suffix='bis')
    old = amending('/akn/ma/act/loi/34-05', '34-05', datetime.date(2006, 2, 20), [('المادة الأولى', ART_1)], 5397)
    Change.objects.bulk_create([
        unclear(BY, 'المادة الأولى', 'dots'), unclear(BY, 'المادة 2'), unclear(BY, 'المادة 8'), unclear(BY, 'المادة 7'),
        unclear(BY, 'المادة 3', 'annex'),                      # an annex: the site does not cut those into parts
        unclear(BY, 'المادة 9'),                               # no article so labelled
        unclear(old.akn_uri, 'المادة الأولى'),                 # published before 2019
        Change(text_uri='/akn/ma/act/loi/2-00', number='7', verb='modified', source='model', by_kind='law',
               by_number='13-26', by_uri=BY, by_article='المادة 5'),        # read by the model already
        unclear(BY, 'المادة 5')])
    Doubt.objects.bulk_create([
        Doubt(by_uri=BY, by_article='المادة 4', reason='target_unknown'),
        Doubt(by_uri=BY, by_article='المادة 3', reason='unclear', detail={'why': 'annex'}),
        Doubt(by_uri=BY, by_article='المادة 6', reason='unclear', status='resolved')])
    return text


def command(*args):
    out = StringIO()
    call_command('read_unclear', *args, stdout=out)
    return out.getvalue()


def test_without_write_it_counts_and_prices_and_sends_nothing(corpus, monkeypatch, settings, tmp_path):
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: {'changes': []})
    for args in ((), ('--write', '--dry-run')):
        said = command(*args)
        assert said.startswith('5 articles; worst case $0.') and said.count('\n') == 1
    assert sent.requests() == [] and not Change.objects.filter(source='model').exclude(by_article='المادة 5').exists()


def test_a_models_reading_is_kept_only_where_the_article_bears_it_out(corpus, monkeypatch, settings, tmp_path):
    arts = {a.label: a for a in Article.objects.filter(version__text=corpus)}
    modify = {'action': 'modify', 'target_kind': 'law', 'target_number': '2.00', 'article': '8', 'old_words': '',
              'new_words': '', 'new_wording': ['«المادة 8. - لا تشمل الحماية ................ ما يلي.»', '']}
    answers = {
        f'{corpus.pk}-{arts["المادة الأولى"].pk}': {'changes': [
            modify,
            {**modify, 'target_number': '5.96'},                                   # a text the article does not cite
            {**modify, 'new_wording': ['لا تشمل الحماية المصنفات الرسمية.']},      # words the article does not print
            {**modify, 'new_wording': []}]},                                        # a modification with no wording
        f'{corpus.pk}-{arts["المادة 2"].pk}': {'changes': [
            {'action': 'words', 'target_kind': 'law', 'target_number': '2.00', 'article': '38', 'new_wording': [],
             'old_words': 'منتج مسجل صوتي', 'new_words': 'منتج تسجيل صوتي'},
            {'action': 'words', 'target_kind': 'law', 'target_number': '2.00', 'article': '38', 'new_wording': [],
             'old_words': 'منتج مسجل صوتي', 'new_words': 'منتج سمعي'}]},          # words the article does not print
        f'{corpus.pk}-{arts["المادة 4"].pk}': {'changes': [
            {'action': 'repeal', 'target_kind': 'law', 'target_number': '15.02', 'article': '', 'new_wording': [],
             'old_words': '', 'new_words': ''},
            {'action': 'repeal', 'target_kind': 'other', 'target_number': '15.02', 'article': '', 'new_wording': [],
             'old_words': '', 'new_words': ''}]},                                   # no kind: no address
    }
    # Arts 7 and 8 the model reads as changing nothing it can say plainly.
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: answers.get(cid, {'changes': []}))
    said = command('--write')
    asked = {r['custom_id']: r['params'] for r in sent.requests()}
    # Asked in the order of their amending text and article, as printed.
    assert list(asked) == [f'{corpus.pk}-{arts[label].pk}'
                           for label in ('المادة 2', 'المادة 4', 'المادة 7', 'المادة 8', 'المادة الأولى')]
    first = asked[f'{corpus.pk}-{arts["المادة الأولى"].pk}']
    assert first['model'] == 'claude-haiku-5-5'
    assert first['messages'][0]['content'] == f'قانون رقم 13-26\n\nالمادة الأولى\n{ART_1}'
    kept = Change.objects.filter(source='model').exclude(by_article='المادة 5').order_by('page')
    assert list(kept.values_list('text_uri', 'number', 'verb', 'by_kind', 'by_number', 'by_uri', 'by_article', 'issue',
                                 'issue_bis', 'page', 'published_on', 'effective_on', 'effective_rule', 'wording')) == [
        ('/akn/ma/act/loi/2-00', '8', 'modified', 'law', '13-26', BY, 'المادة الأولى', 7533, True, 5141,
         datetime.date(2026, 8, 10), datetime.date(2027, 1, 1), 'stated', [modify['new_wording'][0]]),
        ('/akn/ma/act/loi/2-00', '38', 'words', 'law', '13-26', BY, 'المادة 2', 7533, True, 5142,
         datetime.date(2026, 8, 10), datetime.date(2027, 1, 1), 'stated', ['«منتج مسجل صوتي» ← «منتج تسجيل صوتي»']),
        ('/akn/ma/act/loi/15-02', '', 'repealed', 'law', '13-26', BY, 'المادة 4', 7533, True, 5144,
         datetime.date(2026, 8, 10), datetime.date(2027, 1, 1), 'stated', [])]
    assert [c.detail for c in kept] == [
        {'by_model': True, 'dotted': True, 'label': '8'},
        {'by_model': True, 'dotted': False, 'label': '38', 'pairs': [['منتج مسجل صوتي', 'منتج تسجيل صوتي']]},
        {'by_model': True, 'dotted': False, 'label': ''}]
    assert kept[0].effective_words == ART_6
    assert said.splitlines()[-2:] == [
        "kept 3 changes the article bears out; set aside {'words': 1, 'repeal': 1, 'modify': 3}",
        '{"texts": ["/akn/ma/act/loi/13-26"]}']
